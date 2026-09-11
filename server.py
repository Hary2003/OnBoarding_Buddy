import os
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

@app.get("/api/graph")
async def get_graph(session_id: str = "default"):
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        return {"nodes": [], "edges": []}
    
    return session.dependency_graph

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
