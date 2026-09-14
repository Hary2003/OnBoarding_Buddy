from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

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
    resolved_path: Optional[str] = Field(None, description="Resolved relative file path within repo if internal")
    import_type: str = Field("unknown", description="Type of import: relative, package, header, framework")

class CycleDetail(BaseModel):
    cycle_id: str = Field(..., description="Unique cycle identifier")
    path: List[str] = Field(..., description="Ordered list of relative file paths forming the cycle")
    cycle_length: int = Field(..., description="Number of hops in cycle")

class GraphNode(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Display label (filename or package name)")
    path: str = Field(..., description="Relative file path or package string")
    language: str = Field(..., description="Language group: python, javascript, go, web, external")
    in_degree: int = Field(0, description="Incoming dependency count (core module centrality)")
    out_degree: int = Field(0, description="Outgoing dependency count")
    is_entry_point: bool = Field(False, description="True if entry point file")
    is_circular: bool = Field(False, description="True if part of circular dependency cycle")
    activity_score: float = Field(0.0, description="Git activity score")
    symbols_count: int = Field(0, description="Extracted symbol count")
    node_type: str = Field("internal", description="node_type: internal or external_package")
    module_category: str = Field("standard", description="Category: core, leaf, utility, entry_point, isolated, standard")

class GraphEdge(BaseModel):
    from_id: str = Field(..., description="Source node ID")
    to_id: str = Field(..., description="Target node ID")
    statement: Optional[str] = Field("", description="Raw import statement")
    edge_type: str = Field("internal_import", description="Edge type: internal_import or external_package")

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
    in_degree: int = Field(0, description="Number of files importing this file")
    out_degree: int = Field(0, description="Number of imports declared by this file")
    is_circular: bool = Field(False, description="True if part of circular dependency loop")
    module_category: str = Field("standard", description="Category: core, leaf, utility, entry_point, isolated, standard")
    symbols: List[Symbol] = Field(default_factory=list, description="List of extracted functions, classes, and methods")
    dependencies: List[Dependency] = Field(default_factory=list, description="List of imported dependencies")
    is_entry_point: bool = Field(False, description="Flag indicating whether file is a likely application entry point")
    entry_point_confidence: float = Field(0.0, description="Confidence score (0.0-1.0) for entry point detection")

class ArchitectureSummary(BaseModel):
    architecture_type: str = Field("Modular", description="Architecture pattern detected: Layered, MVC, Monolithic, Modular API, microservice, etc.")
    entry_points_summary: List[str] = Field(default_factory=list, description="Primary application entry points")
    core_modules: List[str] = Field(default_factory=list, description="Highly connected core modules (high in-degree)")
    leaf_utility_modules: List[str] = Field(default_factory=list, description="Leaf / utility modules (low out-degree, reused)")
    circular_dependencies_count: int = Field(0, description="Number of detected circular dependency cycles")
    overview_narrative: str = Field("", description="Detailed summary narrative of repository architecture")

class RepositoryIndex(BaseModel):
    repo_name: str = Field(..., description="Repository folder or GitHub repo name")
    repo_path: str = Field(..., description="Absolute path to cloned/analyzed repository root")
    total_files: int = Field(0, description="Total number of analyzed source files")
    total_lines: int = Field(0, description="Total line count across all source files")
    languages_breakdown: Dict[str, int] = Field(default_factory=dict, description="File counts grouped by language")
    entry_points: List[str] = Field(default_factory=list, description="List of detected entry point relative paths")
    circular_cycles: List[CycleDetail] = Field(default_factory=list, description="Detailed circular dependency chains")
    module_counts: Dict[str, int] = Field(default_factory=dict, description="Counts by module category (core, leaf, utility, entry_point, isolated, standard)")
    architecture_summary: Optional[ArchitectureSummary] = Field(None, description="Generated architectural overview of codebase")
    files: List[FileInfo] = Field(default_factory=list, description="List of FileInfo objects for all files")
    dependency_graph: Dict[str, Any] = Field(default_factory=dict, description="Nodes and edges payload for visual graph")
    indexed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp of indexing execution")

# --- M3 Context Retrieval Models ---

class QueryAnalysis(BaseModel):
    original_query: str = Field(..., description="Original user natural language query")
    normalized_terms: List[str] = Field(default_factory=list, description="Normalized tokens extracted from query")
    expanded_concepts: List[str] = Field(default_factory=list, description="Domain synonym & concept expansions")

class RetrievalMatch(BaseModel):
    signal_type: str = Field(..., description="Type of signal: filename_exact, filename_token, symbol_exact, symbol_token, docstring, dependency, content, entry_point, centrality, git_activity")
    score: float = Field(..., description="Score points added by this signal")
    matched_term: str = Field("", description="Matched query term or concept")
    details: str = Field("", description="Explainable description of match")

class ScoredFile(BaseModel):
    relative_path: str = Field(..., description="Relative file path in repository")
    file_name: str = Field(..., description="File name")
    language: str = Field(..., description="Language group")
    module_category: str = Field("standard", description="Module category")
    total_score: float = Field(0.0, description="Total relevance score")
    matched_terms: List[str] = Field(default_factory=list, description="Unique matched query terms/concepts")
    signals: List[str] = Field(default_factory=list, description="List of signal types triggered")
    match_explanations: List[RetrievalMatch] = Field(default_factory=list, description="Detailed signal breakdown for explainability")
    is_expanded_dependency: bool = Field(False, description="True if included via dependency graph expansion")
    expansion_reason: Optional[str] = Field(None, description="Reason for inclusion via expansion")
    matched_symbols: List[str] = Field(default_factory=list, description="Names of matched symbols")

class RetrievedContextPayload(BaseModel):
    repo_name: str = Field(..., description="Repository name")
    query: str = Field(..., description="Original developer question")
    query_analysis: QueryAnalysis = Field(..., description="Query analysis tokenization breakdown")
    scored_files: List[ScoredFile] = Field(default_factory=list, description="Ranked list of relevant scored files")
    formatted_context: str = Field("", description="LLM-ready structured Markdown context string")
    total_files_retrieved: int = Field(0, description="Number of files included in context")
    estimated_tokens: int = Field(0, description="Estimated token count of formatted context")

# --- M4 Grounded AI Onboarding Assistant Models ---

class SourceAttribution(BaseModel):
    file_path: str = Field(..., description="Relative file path")
    symbol_name: Optional[str] = Field(None, description="Matched symbol or function name if applicable")
    line_number: Optional[int] = Field(None, description="1-indexed line number if available")
    relevance_reason: str = Field("", description="Why this source file/symbol was cited")

class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Raw text message content")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp")

class ChatResponse(BaseModel):
    answer: str = Field(..., description="Grounded AI response narrative")
    sources: List[SourceAttribution] = Field(default_factory=list, description="Structured source attributions")
    relevant_files: List[str] = Field(default_factory=list, description="List of relevant relative file paths")
    dependency_paths: List[str] = Field(default_factory=list, description="Related dependency paths included in context")
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata: confidence, has_sufficient_context, files_count, tokens")
