import os
from typing import Optional, Dict, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from config import settings
from services.groq_service import groq_service
from services.repo_service import repo_service
from models.repository_index import RepositoryIndex

app = FastAPI(
    title="OnBoarding Buddy API",
    description="Enterprise-grade repository onboarding API powered by Groq AI and AST Code Intelligence.",
    version="2.0.0"
)

# Enable CORS for decoupled frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- API Endpoints ---
@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "groq_configured": settings.is_groq_configured,
        "groq_model": settings.GROQ_MODEL,
        "host": settings.HOST,
        "port": settings.PORT
    }

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
    return repo_index

@app.get("/api/index", response_model=RepositoryIndex)
async def get_repository_index(session_id: str = "default"):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No active repository index found. Please analyze a repo first.")
    return session

@app.get("/api/file-content")
async def get_file_content(file_path: str = Query(...)):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {
            "file_path": file_path,
            "content": content,
            "lines": len(content.splitlines())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

@app.post("/api/summarize")
async def summarize_file(req: SummarizeRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail="File path does not exist.")
    
    try:
        with open(req.file_path, "r", encoding="utf-8", errors="ignore") as f:
            code_content = f.read()
        rel_path = os.path.basename(req.file_path)
        if session:
            rel_path = os.path.relpath(req.file_path, session.repo_path).replace("\\", "/")
            
        summary_result = groq_service.summarize_code(rel_path, code_content)
        return summary_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization error: {str(e)}")

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

@app.post("/api/chat")
async def repo_chat(req: ChatRequest):
    session = ACTIVE_SESSIONS.get(req.session_id)
    repo_context = "No repo loaded yet."
    if session:
        top_files = [f.relative_path for f in sorted(session.files, key=lambda f: f.activity_score, reverse=True)[:15]]
        entry_pts = session.entry_points
        repo_context = f"Repo: {session.repo_name}\nEntry Points: {', '.join(entry_pts)}\nKey Files: {', '.join(top_files)}"
    
    answer = groq_service.chat_with_repository(req.question, repo_context)
    return {"answer": answer}

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
    print(f"[OnBoarding Buddy] Starting Backend Server at http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("server:app", host=settings.HOST, port=settings.PORT, reload=True)
