from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

class Symbol(BaseModel):
    name: str = Field(..., description="Name of the function, class, method, or symbol")
    type: str = Field(..., description="Symbol type: function, class, method, variable")
    line_number: int = Field(..., description="1-indexed line number where symbol starts")
    end_line: Optional[int] = Field(None, description="1-indexed line number where symbol ends")
    parameters: List[str] = Field(default_factory=list, description="Argument / parameter list")
    docstring: Optional[str] = Field("", description="Docstring or comment summary associated with symbol")
    return_type: Optional[str] = Field(None, description="Return type hint if available")

class Dependency(BaseModel):
    source_path: str = Field(..., description="Relative path of file declaring the import")
    target_path: str = Field(..., description="Relative path of target imported file or package name")
    import_statement: str = Field(..., description="Raw import string")
    is_internal: bool = Field(True, description="True if dependency points to an internal repository file")

class FileInfo(BaseModel):
    full_path: str = Field(..., description="Absolute filesystem path")
    relative_path: str = Field(..., description="Normalized relative path from repository root")
    file_name: str = Field(..., description="Base filename")
    language: str = Field(..., description="Programming language or file extension group")
    size_bytes: int = Field(0, description="File size in bytes")
    line_count: int = Field(0, description="Total number of lines in file")
    last_modified: str = Field(..., description="Last Git commit date or file modification date")
    commit_count: int = Field(0, description="Number of Git commits touching this file")
    activity_score: float = Field(0.0, description="Normalized Git activity score between 0.0 and 100.0")
    symbols: List[Symbol] = Field(default_factory=list, description="List of extracted functions, classes, and methods")
    dependencies: List[Dependency] = Field(default_factory=list, description="List of imported dependencies")
    is_entry_point: bool = Field(False, description="Flag indicating whether file is a likely application entry point")
    entry_point_confidence: float = Field(0.0, description="Confidence score (0.0-1.0) for entry point detection")

class RepositoryIndex(BaseModel):
    repo_name: str = Field(..., description="Repository folder or GitHub repo name")
    repo_path: str = Field(..., description="Absolute path to cloned/analyzed repository root")
    total_files: int = Field(0, description="Total number of analyzed source files")
    total_lines: int = Field(0, description="Total line count across all source files")
    languages_breakdown: Dict[str, int] = Field(default_factory=dict, description="File counts grouped by language")
    entry_points: List[str] = Field(default_factory=list, description="List of detected entry point relative paths")
    files: List[FileInfo] = Field(default_factory=list, description="List of FileInfo objects for all files")
    dependency_graph: Dict[str, Any] = Field(default_factory=dict, description="Nodes and edges payload for visual graph")
    indexed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp of indexing execution")
