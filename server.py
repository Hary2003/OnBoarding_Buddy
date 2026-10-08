import os
import secrets
import logging
from pathlib import Path
from typing import Optional, Dict, List
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
import uvicorn

from config import settings
from database import init_db, check_db_health
from services.repository_persistence import repository_persistence
from services.groq_service import groq_service
from services.repo_service import repo_service
from services.retrieval_service import retrieval_engine
from services.conversation_service import conversation_service
from services.contribution_service import contribution_service
from services.audit_service import audit_service
from services.agent.agent import agent_service
from services.pr_service import pr_service
from services.export_service import export_service
from models.repository_index import (
    RepositoryIndex, RetrievedContextPayload, ChatResponse,
    ContributionPlan, AuditReport, ContributionOpportunity,
    AgentExploreResponse, PullRequestAnalysis, PRReviewResponse, PRSummary
)
from services.security_guard import is_safe_repo_path, MAX_VIEWABLE_FILE_SIZE, rate_limiter

logger = logging.getLogger("onboarding_buddy.server")

# FastAPI App Configuration
app = FastAPI(
    title="OnBoarding Buddy API",
    description="Enterprise-grade repository onboarding API powered by Groq AI and AST Code Intelligence.",
    version="2.0.0",
    debug=settings.DEBUG,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

# Production-Grade CORS Configuration
cors_origins = settings.get_cors_origins()
if settings.is_production:
    # In production: strictly allow only configured origins, forbid wildcard with credentials
    allow_credentials = bool(cors_origins and "*" not in cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins else [],
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
        max_age=600,
    )
else:
    # Development / testing mode: allow local origins or development fallback
    allow_credentials = bool(cors_origins and "*" not in cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins else ["*"],
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Security Middlewares ---

@app.middleware("http")
async def api_auth_middleware(request: Request, call_next):
    """
    Optional API Authentication gate.
    When API_AUTH_ENABLED is True and API_KEY is configured, validates callers
    provide a valid Bearer token or X-API-Key header on /api/* routes,
    excluding unauthenticated health probes and CORS preflights.
    """
    if settings.API_AUTH_ENABLED and settings.API_KEY:
        path = request.url.path
        if path.startswith("/api/") and path not in ("/api/health", "/api/db/status") and request.method != "OPTIONS":
            auth_header = request.headers.get("Authorization", "").strip()
            x_api_key = request.headers.get("X-API-Key", "").strip()

            token = ""
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
            elif x_api_key:
                token = x_api_key

            if not token or not secrets.compare_digest(token, settings.API_KEY):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: Invalid or missing API key."},
                    headers={"WWW-Authenticate": "Bearer"}
                )

    return await call_next(request)


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """
    Sliding-window IP rate limiter to defend against DoS, brute-force, and quota exhaustion.
    Protects /api/* endpoints while allowing health probes and static files.
    """
    if settings.RATE_LIMIT_ENABLED and request.method != "OPTIONS":
        path = request.url.path
        if path.startswith("/api/") and path not in ("/api/health", "/api/db/status"):
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            elif request.client and request.client.host:
                client_ip = request.client.host
            else:
                client_ip = "127.0.0.1"

            is_allowed, remaining, retry_after = rate_limiter.check_rate_limit(
                client_ip=client_ip,
                path=path,
                limit=settings.RATE_LIMIT_PER_MINUTE
            )

            if not is_allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down and try again later."},
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(settings.RATE_LIMIT_PER_MINUTE),
                        "X-RateLimit-Remaining": "0"
                    }
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_MINUTE)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response

    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    Enforces defense-in-depth HTTP security headers on all responses:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY (clickjacking protection)
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: restricts browser hardware APIs
    - Strict-Transport-Security: HSTS in production
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return response


# --- Centralized Secure Error Handling ---

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Sanitize 5xx error responses in production to prevent leaking internal stack/paths."""
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code} error on {request.method} {request.url.path}: {exc.detail}")
        if not settings.DEBUG:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": "An internal server error occurred while processing the request."},
                headers=exc.headers
            )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )

@app.exception_handler(Exception)
@app.exception_handler(500)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler ensuring no raw unhandled stack traces are leaked to clients."""
    logger.exception(f"Unhandled exception during {request.method} {request.url.path}: {exc}")
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Internal Server Error: {str(exc)}",
                "type": type(exc).__name__
            }
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please contact the administrator or check server logs."}
    )

# --- Startup Lifecycle ---
@app.on_event("startup")
async def on_startup():
    """Initializes database schema and restores active session from PostgreSQL."""
    try:
        init_db()
        persisted = repository_persistence.load_repository("default")
        if persisted:
            ACTIVE_SESSIONS["default"] = persisted
            logger.info(f"Restored persisted repository '{persisted.repo_name}' for session 'default'.")
    except Exception as e:
        logger.warning(f"Database startup check note: {e}")


# Active session cache (session_id -> RepositoryIndex)
ACTIVE_SESSIONS: dict[str, RepositoryIndex] = {}

# --- Request Schemas ---
class CloneRequest(BaseModel):
    url_or_path: str

class SummarizeRequest(BaseModel):
    file_path: str
    session_id: str = "default"

class GenerateGuideRequest(BaseModel):
    session_id: str = "default"

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

class RetrieveRequest(BaseModel):
    query: str
    session_id: str = "default"
    max_files: int = 8
    expand_dependencies: bool = True

class IssueRequest(BaseModel):
    title: str
    description: str = ""
    session_id: str = "default"
    max_files: int = 10
    max_impact_depth: int = 2

class AuditRequest(BaseModel):
    session_id: str = "default"

class AgentExploreRequest(BaseModel):
    query: str
    session_id: str = "default"
    max_iterations: int = 8
    max_tool_calls: int = 15
    max_files: int = 20

class PRAnalyzeRequest(BaseModel):
    diff: str
    session_id: str = "default"
    title: str = ""
    description: str = ""

class PRReviewRequest(BaseModel):
    diff: str
    session_id: str = "default"
    title: str = ""
    description: str = ""

class PRSummaryRequest(BaseModel):
    diff: str
    session_id: str = "default"
    title: str = ""
    description: str = ""

# --- API Endpoints ---
@app.get("/api/health")
async def health_check():
    db_health = check_db_health()
    return {
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "groq_configured": settings.is_groq_configured,
        "groq_model": settings.GROQ_MODEL,
        "database": db_health,
        "host": settings.HOST,
        "port": settings.PORT,
        "rate_limiting_enabled": settings.RATE_LIMIT_ENABLED,
        "auth_configured": settings.is_auth_configured,
    }

@app.get("/api/db/status")
async def db_status():
    """Returns detailed database connectivity and table counts without leaking secrets."""
    return check_db_health()

@app.get("/api/repositories")
async def list_repositories():
    """Returns list of persisted repositories from PostgreSQL."""
    return repository_persistence.list_repositories()

@app.post("/api/clone", response_model=RepositoryIndex)
async def clone_repository(req: CloneRequest):
    target = req.url_or_path.strip()
    if not target:
        raise HTTPException(status_code=400, detail="Repository URL or local path is required.")
    
    success, repo_index, err_msg = repo_service.parse_repository(target)
    if not success or not repo_index:
        raise HTTPException(status_code=400, detail=err_msg)
    
    session_id = "default"
    ACTIVE_SESSIONS[session_id] = repo_index
    # Persist repository metadata and AST structure to PostgreSQL
    repository_persistence.save_repository(session_id, repo_index)
    return repo_index

@app.get("/api/index", response_model=RepositoryIndex)
async def get_repository_index(session_id: str = "default"):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        # Fallback: attempt restoring from PostgreSQL
        session = repository_persistence.load_repository(session_id)
        if session:
            ACTIVE_SESSIONS[session_id] = session

    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    return session

def get_allowed_repo_roots(session_id: str = "default") -> List[str]:
    """Retrieves all valid repository root paths for boundary checks."""
    roots: List[str] = []
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        session = repository_persistence.load_repository(session_id)
        if session:
            ACTIVE_SESSIONS[session_id] = session

    if session and session.repo_path:
        roots.append(session.repo_path)

    for s in ACTIVE_SESSIONS.values():
        if s.repo_path and s.repo_path not in roots:
            roots.append(s.repo_path)

    # Allow current project directory as fallback root (for local inspections and tests)
    project_root = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in roots:
        roots.append(project_root)

    return roots


def validate_file_within_boundary(file_path: str, session_id: str = "default") -> str:
    """
    Validates that file_path strictly resides within an allowed repository boundary.
    Raises HTTPException(403) on path traversal attempts or symlinks escaping the boundary,
    and HTTPException(404) if the file does not exist.
    """
    if not file_path or not str(file_path).strip():
        raise HTTPException(status_code=404, detail="File not found.")

    allowed_roots = get_allowed_repo_roots(session_id)

    any_safe_candidate = False
    for root in allowed_roots:
        is_safe, canonical_target, _ = is_safe_repo_path(root, file_path)
        if is_safe:
            any_safe_candidate = True
            if os.path.exists(canonical_target) and os.path.isfile(canonical_target):
                return canonical_target

    # If the file path was structurally safe in at least one repository boundary but not found on disk
    if any_safe_candidate:
        raise HTTPException(status_code=404, detail="File not found.")

    # Target path escapes all allowed repository boundaries
    raise HTTPException(status_code=403, detail="Access denied: Requested path is outside the repository security boundary.")


@app.get("/api/file-content")
async def get_file_content(file_path: str = Query(...), session_id: str = Query("default")):
    canonical_path = validate_file_within_boundary(file_path, session_id)
    try:
        size_bytes = os.path.getsize(canonical_path) if os.path.exists(canonical_path) else 0
        truncated = False
        with open(canonical_path, "r", encoding="utf-8", errors="ignore") as f:
            if size_bytes > MAX_VIEWABLE_FILE_SIZE:
                content = f.read(MAX_VIEWABLE_FILE_SIZE)
                content += "\n\n/* [Content truncated: File exceeds maximum display limit of 3 MB] */"
                truncated = True
            else:
                content = f.read()

        return {
            "file_path": canonical_path,
            "content": content,
            "lines": len(content.splitlines()),
            "truncated": truncated
        }
    except Exception as e:
        logger.error(f"Failed to read file {canonical_path}: {e}")
        if settings.DEBUG:
            raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to read the requested file.")

@app.post("/api/summarize")
async def summarize_file(req: SummarizeRequest):
    canonical_path = validate_file_within_boundary(req.file_path, req.session_id)
    session = ACTIVE_SESSIONS.get(req.session_id)

    try:
        with open(canonical_path, "r", encoding="utf-8", errors="ignore") as f:
            code_content = f.read(MAX_VIEWABLE_FILE_SIZE)
        rel_path = os.path.basename(canonical_path)
        if session and session.repo_path:
            try:
                rel_path = os.path.relpath(canonical_path, session.repo_path).replace("\\", "/")
            except ValueError:
                pass
            
        summary_result = groq_service.summarize_code(rel_path, code_content)
        return summary_result
    except Exception as e:
        logger.error(f"Summarization error for {canonical_path}: {e}", exc_info=True)
        if settings.DEBUG:
            raise HTTPException(status_code=500, detail=f"Summarization error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to summarize the requested file.")

@app.post("/api/generate-guide")
async def generate_guide(req: GenerateGuideRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active repository session found. Please analyze a repo first.")
    
    repo_name = session.repo_name
    ranked_files = sorted(session.files, key=lambda f: f.activity_score, reverse=True)
    file_list = [f.relative_path for f in ranked_files[:15]]
    file_tree_str = "\n".join(file_list)
    
    key_files_meta = [{"rel_path": f.relative_path, "activity_score": f.activity_score, "is_entry_point": f.is_entry_point} for f in ranked_files[:10]]
    
    guide_markdown = groq_service.generate_onboarding_guide(repo_name, file_tree_str, key_files_meta)
    return {
        "repo_name": repo_name,
        "guide": guide_markdown
    }

# --- Onboarding & Architecture Export Endpoints ---

@app.get("/api/export/guide")
async def export_guide(session_id: str = "default", download: bool = Query(False)):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        session = repository_persistence.load_repository(session_id)
        if session:
            ACTIVE_SESSIONS[session_id] = session
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")

    guide_markdown = export_service.export_onboarding_guide_markdown(session)
    filename = f"{session.repo_name}_ONBOARDING_GUIDE.md"
    if download:
        return Response(
            content=guide_markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    return {"repo_name": session.repo_name, "filename": filename, "markdown": guide_markdown}

@app.get("/api/export/architecture")
async def export_architecture(session_id: str = "default", download: bool = Query(False)):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        session = repository_persistence.load_repository(session_id)
        if session:
            ACTIVE_SESSIONS[session_id] = session
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")

    arch_markdown = export_service.export_architecture_markdown(session)
    filename = f"{session.repo_name}_ARCHITECTURE_SPEC.md"
    if download:
        return Response(
            content=arch_markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    return {"repo_name": session.repo_name, "filename": filename, "markdown": arch_markdown}

@app.get("/api/export/audit")
async def export_audit(session_id: str = "default", download: bool = Query(False)):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        session = repository_persistence.load_repository(session_id)
        if session:
            ACTIVE_SESSIONS[session_id] = session
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")

    audit_report = audit_service.run_audit(session)
    audit_markdown = export_service.export_audit_markdown(audit_report)
    filename = f"{session.repo_name}_AUDIT_REPORT.md"
    if download:
        return Response(
            content=audit_markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    return {
        "repo_name": session.repo_name,
        "filename": filename,
        "total_opportunities": audit_report.total_opportunities,
        "markdown": audit_markdown
    }

@app.post("/api/retrieve", response_model=RetrievedContextPayload)
async def retrieve_context(req: RetrieveRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    
    context_payload = retrieval_engine.process_query(
        repo_index=session,
        query=req.query,
        max_files=req.max_files,
        expand_dependencies=req.expand_dependencies
    )
    return context_payload

@app.post("/api/chat", response_model=ChatResponse)
async def repo_chat(req: ChatRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    chat_response = conversation_service.process_chat(
        question=req.question,
        session_id=req.session_id,
        repo_index=session
    )
    return chat_response

@app.post("/api/agent/explore", response_model=AgentExploreResponse)
async def agent_explore(req: AgentExploreRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")

    try:
        return agent_service.explore(
            query=req.query,
            repo_index=session,
            conversation_history=conversation_service.get_history(req.session_id),
            max_iterations=req.max_iterations,
            max_tool_calls=req.max_tool_calls,
            max_files=req.max_files
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# --- M7 Pull Request Intelligence Endpoints ---

@app.post("/api/pr/analyze", response_model=PullRequestAnalysis)
async def analyze_pr(req: PRAnalyzeRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    diff_text = req.diff.strip() if req.diff else ""
    if not diff_text:
        raise HTTPException(status_code=400, detail="Pull request diff is required.")
    try:
        return pr_service.analyze_pr(
            diff_text=diff_text,
            repo_index=session,
            title=req.title,
            description=req.description
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/pr/review", response_model=PRReviewResponse)
async def review_pr(req: PRReviewRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    diff_text = req.diff.strip() if req.diff else ""
    if not diff_text:
        raise HTTPException(status_code=400, detail="Pull request diff is required.")
    try:
        review_result = pr_service.review_pr(
            diff_text=diff_text,
            repo_index=session,
            title=req.title,
            description=req.description
        )
        repository_persistence.save_pr_review(req.session_id, review_result, title=req.title)
        return review_result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/pr/summary", response_model=PRSummary)
async def summarize_pr(req: PRSummaryRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    diff_text = req.diff.strip() if req.diff else ""
    if not diff_text:
        raise HTTPException(status_code=400, detail="Pull request diff is required.")
    try:
        return pr_service.summarize_pr(
            diff_text=diff_text,
            repo_index=session,
            title=req.title,
            description=req.description
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/pr/sample-diffs")
async def get_sample_diffs():
    """Provides sample PR diffs for interactive demo reviews from fixture files."""
    fixtures_dir = Path(__file__).parent / "tests" / "fixtures"
    feature_file = fixtures_dir / "sample_feature_diff.txt"
    vuln_file = fixtures_dir / "sample_vulnerable_diff.txt"
    arch_file = fixtures_dir / "sample_architecture_diff.txt"

    def read_fixture(p: Path) -> str:
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    return {
        "feature": read_fixture(feature_file),
        "vulnerable": read_fixture(vuln_file),
        "architecture": read_fixture(arch_file),
    }

@app.delete("/api/chat/history")
async def clear_chat_history(session_id: str = Query("default")):
    cleared = conversation_service.clear_history(session_id)
    return {"session_id": session_id, "cleared": cleared}

@app.post("/api/contribution/analyze", response_model=ContributionPlan)
async def analyze_contribution(req: IssueRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    
    plan = contribution_service.generate_plan(
        title=req.title,
        description=req.description,
        session_id=req.session_id,
        repo_index=session,
        max_files=req.max_files,
        max_impact_depth=req.max_impact_depth
    )
    return plan

@app.post("/api/contribution/audit", response_model=AuditReport)
async def audit_repository_opportunities(req: AuditRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    if not session:
        session = repository_persistence.load_repository(req.session_id)
        if session:
            ACTIVE_SESSIONS[req.session_id] = session
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    
    report = audit_service.run_audit(session)
    repository_persistence.save_audit_report(req.session_id, report)
    return report

@app.get("/api/dependencies")
@app.get("/api/graph")
async def get_dependencies(
    session_id: str = "default",
    include_external: bool = Query(True),
    filter_type: str = Query("all")  # all, core, leaf, utility, entry, circular, isolated
):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        return {"nodes": [], "edges": []}
    
    graph_data = repo_service.extract_dependency_graph(session.repo_path, session.files, include_external=include_external)
    
    if filter_type == "core":
        valid_node_ids = {n["id"] for n in graph_data["nodes"] if n.get("module_category") == "core" or n["in_degree"] >= 1 or n["node_type"] == "external_package"}
        graph_data["nodes"] = [n for n in graph_data["nodes"] if n["id"] in valid_node_ids]
        graph_data["edges"] = [e for e in graph_data["edges"] if e["from"] in valid_node_ids and e["to"] in valid_node_ids]
    elif filter_type in ["leaf", "utility"]:
        valid_node_ids = {n["id"] for n in graph_data["nodes"] if n.get("module_category") in ["leaf", "utility"]}
        graph_data["nodes"] = [n for n in graph_data["nodes"] if n["id"] in valid_node_ids]
        graph_data["edges"] = [e for e in graph_data["edges"] if e["from"] in valid_node_ids and e["to"] in valid_node_ids]
    elif filter_type == "entry":
        valid_node_ids = {n["id"] for n in graph_data["nodes"] if n["is_entry_point"]}
        downstream_ids = {e["to"] for e in graph_data["edges"] if e["from"] in valid_node_ids}
        valid_node_ids.update(downstream_ids)
        graph_data["nodes"] = [n for n in graph_data["nodes"] if n["id"] in valid_node_ids]
        graph_data["edges"] = [e for e in graph_data["edges"] if e["from"] in valid_node_ids and e["to"] in valid_node_ids]
    elif filter_type == "circular":
        valid_node_ids = {n["id"] for n in graph_data["nodes"] if n["is_circular"]}
        graph_data["nodes"] = [n for n in graph_data["nodes"] if n["id"] in valid_node_ids]
        graph_data["edges"] = [e for e in graph_data["edges"] if e["from"] in valid_node_ids and e["to"] in valid_node_ids]
    elif filter_type == "isolated":
        valid_node_ids = {n["id"] for n in graph_data["nodes"] if n.get("module_category") == "isolated"}
        graph_data["nodes"] = [n for n in graph_data["nodes"] if n["id"] in valid_node_ids]
        graph_data["edges"] = [e for e in graph_data["edges"] if e["from"] in valid_node_ids and e["to"] in valid_node_ids]

    return graph_data

@app.get("/api/dependencies/modules")
async def get_dependency_modules(session_id: str = "default", category: Optional[str] = Query(None)):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    
    files = session.files
    if category:
        files = [f for f in files if f.module_category.lower() == category.lower()]
    
    categorized_summary = {
        "repo_name": session.repo_name,
        "total_files": len(files),
        "module_counts": session.module_counts,
        "modules": [
            {
                "file_name": f.file_name,
                "relative_path": f.relative_path,
                "module_category": f.module_category,
                "in_degree": f.in_degree,
                "out_degree": f.out_degree,
                "is_entry_point": f.is_entry_point,
                "is_circular": f.is_circular,
                "dependencies_count": len(f.dependencies)
            }
            for f in files
        ]
    }
    return categorized_summary

@app.get("/api/dependencies/cycles")
async def get_circular_dependency_cycles(session_id: str = "default"):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    
    return {
        "repo_name": session.repo_name,
        "total_cycles": len(session.circular_cycles),
        "cycles": session.circular_cycles
    }

@app.get("/api/architecture")
async def get_architecture_summary(session_id: str = "default", use_llm: bool = Query(False)):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    
    arch_summary = session.architecture_summary or repo_service.generate_architecture_summary(session)
    
    if use_llm and settings.is_groq_configured:
        llm_narrative = groq_service.generate_architecture_insight(
            repo_name=session.repo_name,
            total_files=session.total_files,
            total_lines=session.total_lines,
            entry_points=session.entry_points,
            core_modules=arch_summary.core_modules,
            leaf_modules=arch_summary.leaf_utility_modules,
            circular_count=arch_summary.circular_dependencies_count,
            languages=session.languages_breakdown
        )
        arch_summary.overview_narrative = llm_narrative

    return {
        "repo_name": session.repo_name,
        "architecture_summary": arch_summary
    }

# Mount frontend static files
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if not os.path.exists(frontend_path):
    os.makedirs(frontend_path, exist_ok=True)

app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def serve_frontend():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "OnBoarding Buddy FastAPI Backend is running. Frontend static index.html not found."}

if __name__ == "__main__":
    print(f"[OnBoarding Buddy] Starting Backend Server at http://{settings.HOST}:{settings.PORT} (env={settings.ENVIRONMENT}, debug={settings.DEBUG})")
    uvicorn.run("server:app", host=settings.HOST, port=settings.PORT, reload=settings.RELOAD, log_level=settings.LOG_LEVEL.lower())
