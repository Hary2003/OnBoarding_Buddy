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

# --- M5 Issue-to-Code Contribution Intelligence Models ---

class IssueAnalysis(BaseModel):
    title: str = Field(..., description="Issue or feature request title")
    summary: str = Field(..., description="Concise issue requirement summary")
    keywords: List[str] = Field(default_factory=list, description="Extracted technical keywords")
    technologies: List[str] = Field(default_factory=list, description="Detected technology stack terms")
    actions: List[str] = Field(default_factory=list, description="Action verbs (e.g. add, configure, update, fix)")
    domains: List[str] = Field(default_factory=list, description="Functional domain areas (e.g. database, api, auth, config)")

class ContributionCandidate(BaseModel):
    file_path: str = Field(..., description="Relative file path")
    file_name: str = Field(..., description="Filename")
    base_retrieval_score: float = Field(0.0, description="Base score from M3 retrieval engine")
    contribution_score: float = Field(0.0, description="Final explainable contribution score")
    module_category: str = Field("standard", description="Module category (core, leaf, utility, entry_point)")
    matched_symbols: List[str] = Field(default_factory=list, description="Matched function/class symbols")
    scoring_explanations: List[str] = Field(default_factory=list, description="Explainable scoring rules triggered")

class ImpactAnalysis(BaseModel):
    directly_affected: List[str] = Field(default_factory=list, description="Files directly requiring modification")
    downstream_impact: List[str] = Field(default_factory=list, description="Files dependent on directly affected modules")
    upstream_context: List[str] = Field(default_factory=list, description="Files called/used by directly affected modules")
    dependency_chains: List[str] = Field(default_factory=list, description="Formatted dependency impact chains (A -> B -> C)")

class TestImpact(BaseModel):
    directly_related_tests: List[str] = Field(default_factory=list, description="Direct matching test files")
    potentially_related_tests: List[str] = Field(default_factory=list, description="Indirect or module-related test files")
    evidence: List[str] = Field(default_factory=list, description="Evidence connecting source modules to test files")

class ConfigImpact(BaseModel):
    configuration_files: List[str] = Field(default_factory=list, description="Detected project configuration files")
    evidence: List[str] = Field(default_factory=list, description="Evidence connecting issue requirements to configs")

class ContributionPlan(BaseModel):
    repo_name: str = Field(..., description="Repository name")
    issue_analysis: IssueAnalysis = Field(..., description="Structured issue requirement analysis")
    relevant_files: List[ContributionCandidate] = Field(default_factory=list, description="Ranked candidate files")
    relevant_symbols: List[str] = Field(default_factory=list, description="Key symbols implicated in issue")
    directly_affected_files: List[str] = Field(default_factory=list, description="Files requiring modification")
    impacted_files: List[str] = Field(default_factory=list, description="Potentially impacted downstream files")
    configuration_files: List[str] = Field(default_factory=list, description="Implicated configuration files")
    test_files: List[str] = Field(default_factory=list, description="Associated test files for verification")
    dependency_paths: List[str] = Field(default_factory=list, description="Formatted dependency impact chains")
    recommended_changes: List[str] = Field(default_factory=list, description="Step-by-step implementation recommendations")
    risks: List[str] = Field(default_factory=list, description="Implementation risks and considerations")
    confidence: str = Field("Medium", description="Deterministic confidence level: High, Medium, or Low")
    evidence: List[str] = Field(default_factory=list, description="Repository evidence supporting the plan")
    plan_narrative: str = Field("", description="Complete grounded Markdown contribution analysis report")

# --- Audit & Open-Source Contribution Scanner Models ---

class ContributionOpportunity(BaseModel):
    opportunity_id: str = Field(..., description="Unique opportunity identifier")
    title: str = Field(..., description="Short title describing the open source contribution opportunity")
    category: str = Field(..., description="Category: security, test_coverage, architecture_refactor, documentation")
    severity: str = Field("Medium", description="Severity or Impact level: Critical, High, Medium, Low")
    target_files: List[str] = Field(default_factory=list, description="Target repository file paths implicated")
    description: str = Field("", description="Detailed explanation of vulnerability, risk, or debt found")
    remediation_plan: str = Field("", description="Recommended open source contribution fix or pull request plan")
    suggested_issue_title: str = Field("", description="Pre-formulated issue title for one-click analysis")
    suggested_issue_desc: str = Field("", description="Pre-formulated issue description for one-click analysis")

class AuditReport(BaseModel):
    repo_name: str = Field(..., description="Repository name")
    total_opportunities: int = Field(0, description="Total number of detected contribution opportunities")
    critical_count: int = Field(0, description="Critical severity opportunities")
    high_count: int = Field(0, description="High severity opportunities")
    medium_count: int = Field(0, description="Medium severity opportunities")
    low_count: int = Field(0, description="Low severity opportunities")
    opportunities: List[ContributionOpportunity] = Field(default_factory=list, description="Ranked contribution opportunities")
    summary_narrative: str = Field("", description="Markdown summary of repository health and contribution potential")

# --- M6 Agentic Repository Exploration Models ---

class ToolCall(BaseModel):
    call_id: str = Field(..., description="Unique tool call identifier")
    tool_name: str = Field(..., description="Registered read-only repository tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Validated tool arguments")

class ToolResult(BaseModel):
    call_id: str = Field(..., description="Matching tool call identifier")
    tool_name: str = Field(..., description="Executed tool name")
    success: bool = Field(..., description="True when tool execution succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured tool result payload")
    error: Optional[str] = Field(None, description="Error message when execution failed")

class AgentTraceEvent(BaseModel):
    step: int = Field(..., description="1-indexed public investigation step number")
    tool: Optional[str] = Field(None, description="Tool used for this event, if applicable")
    status: str = Field(..., description="Trace status: planned, running, success, error, skipped, complete")
    description: str = Field(..., description="Short user-visible action or observation summary")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp")

class AgentFinding(BaseModel):
    finding: str = Field(..., description="Concise grounded finding collected during exploration")
    source: Optional[SourceAttribution] = Field(None, description="Repository source supporting the finding")

class AgentState(BaseModel):
    user_query: str = Field(..., description="Developer question being investigated")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="Relevant prior chat turns")
    investigation_plan: List[str] = Field(default_factory=list, description="Current high-level investigation plan")
    current_step: Optional[str] = Field(None, description="Current public plan step")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Executed tool calls")
    observations: List[ToolResult] = Field(default_factory=list, description="Tool observations")
    discovered_files: List[str] = Field(default_factory=list, description="Repository files discovered or inspected")
    discovered_symbols: List[str] = Field(default_factory=list, description="Symbols discovered or inspected")
    dependency_paths: List[str] = Field(default_factory=list, description="Dependency paths established during exploration")
    findings: List[AgentFinding] = Field(default_factory=list, description="Grounded findings with sources")
    sources: List[SourceAttribution] = Field(default_factory=list, description="Source attributions collected")
    trace: List[AgentTraceEvent] = Field(default_factory=list, description="Observable investigation trace")
    iteration: int = Field(0, description="Current loop iteration count")
    token_usage: Dict[str, Any] = Field(default_factory=dict, description="LLM or context token usage metadata")
    final_answer: Optional[str] = Field(None, description="Final grounded answer")

class AgentExploreResponse(BaseModel):
    answer: str = Field(..., description="Grounded final answer")
    sources: List[SourceAttribution] = Field(default_factory=list, description="Source attributions")
    findings: List[AgentFinding] = Field(default_factory=list, description="Grounded investigation findings")
    files_inspected: List[str] = Field(default_factory=list, description="Files inspected or discovered")
    symbols_inspected: List[str] = Field(default_factory=list, description="Symbols inspected or discovered")
    dependency_paths: List[str] = Field(default_factory=list, description="Dependency paths found")
    tools_used: List[str] = Field(default_factory=list, description="Tool names executed during exploration")
    trace: List[AgentTraceEvent] = Field(default_factory=list, description="Public agent trace")
    iterations: int = Field(0, description="Loop iterations completed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Agent limits and execution metadata")

# --- M7 Pull Request Intelligence & Code Review Models ---

class CodeChange(BaseModel):
    file_path: str = Field(..., description="File path of the change")
    change_type: str = Field(..., description="Change type: added, removed, context")
    old_line_number: Optional[int] = Field(None, description="Line number in base file")
    new_line_number: Optional[int] = Field(None, description="Line number in modified file")
    content: str = Field(..., description="Source code text line")

class DiffHunk(BaseModel):
    old_start: int = Field(0, description="Starting line in old version")
    old_lines: int = Field(0, description="Line count in old version")
    new_start: int = Field(0, description="Starting line in new version")
    new_lines: int = Field(0, description="Line count in new version")
    header: str = Field("", description="Hunk header context (e.g., function definition)")
    lines: List[str] = Field(default_factory=list, description="Raw lines inside this hunk")

class FileChange(BaseModel):
    file_path: str = Field(..., description="Target file path in repository")
    old_path: Optional[str] = Field(None, description="Previous file path if renamed or moved")
    status: str = Field(..., description="Change status: added, modified, deleted, renamed")
    additions: int = Field(0, description="Number of added lines")
    deletions: int = Field(0, description="Number of removed lines")
    modified_symbols: List[str] = Field(default_factory=list, description="Functions, classes, or methods affected")
    hunks: List[DiffHunk] = Field(default_factory=list, description="Parsed diff hunks")
    patch: str = Field("", description="Unified diff patch chunk for this file")

class PRSummary(BaseModel):
    title: str = Field("", description="Pull request title or inferred topic")
    executive_summary: str = Field("", description="High-level business & risk overview of what changed and why")
    developer_summary: str = Field("", description="Technical summary of modified components, symbols, and tests")
    change_type: str = Field("feature", description="Classification: feature, bug_fix, refactor, test_update, configuration_change, documentation_update")
    risk_level: str = Field("Low", description="Overall risk level: Critical, High, Medium, Low")
    files_changed: int = Field(0, description="Total count of files modified")
    lines_added: int = Field(0, description="Total additions")
    lines_removed: int = Field(0, description="Total deletions")
    author: Optional[str] = Field(None, description="PR or commit author")
    commit_references: List[str] = Field(default_factory=list, description="Commit hashes or references")

class ArchitectureImpact(BaseModel):
    affected_entry_points: List[str] = Field(default_factory=list, description="Application entry points impacted")
    affected_modules: List[str] = Field(default_factory=list, description="Core and standard modules affected")
    affected_services: List[str] = Field(default_factory=list, description="Service layer components impacted")
    affected_apis: List[str] = Field(default_factory=list, description="API endpoints or route definitions impacted")
    upstream_impact: List[str] = Field(default_factory=list, description="Upstream callers or dependents impacted")
    downstream_impact: List[str] = Field(default_factory=list, description="Downstream dependencies imported by changed files")
    architectural_layers: List[str] = Field(default_factory=list, description="Architectural layers touched (api, service, model, utility, config, test)")
    layer_violations: List[str] = Field(default_factory=list, description="Detected architectural layer violations")
    circular_dependency_risks: List[str] = Field(default_factory=list, description="Risks of new circular dependencies")
    god_module_risks: List[str] = Field(default_factory=list, description="Modules growing excessively large or complex")
    coupling_increase_score: float = Field(0.0, description="Heuristic score for increased system coupling")

class TestRecommendation(BaseModel):
    related_tests: List[str] = Field(default_factory=list, description="Existing test files mapped to changed files")
    missing_tests: List[str] = Field(default_factory=list, description="Files with logic changes that lack corresponding tests")
    outdated_tests: List[str] = Field(default_factory=list, description="Tests calling altered function signatures")
    recommended_test_files: List[str] = Field(default_factory=list, description="Test files recommended to run")
    recommended_scenarios: List[str] = Field(default_factory=list, description="Unit and integration test scenarios to add")
    recommended_edge_cases: List[str] = Field(default_factory=list, description="Boundary and edge conditions to verify")
    recommended_integration_tests: List[str] = Field(default_factory=list, description="Cross-module integration test recommendations")

class RiskAssessment(BaseModel):
    risk_id: str = Field(..., description="Unique risk identifier")
    title: str = Field(..., description="Short summary of the risk")
    category: str = Field("security", description="Category: security, architecture, maintainability, test_coverage")
    severity: str = Field("Medium", description="Severity: Critical, High, Medium, Low")
    file_path: str = Field(..., description="Affected repository file")
    line_number: Optional[int] = Field(None, description="Line number if localized")
    evidence: str = Field("", description="Supporting code snippet or diff hunk")
    remediation: str = Field("", description="Recommended fix or preventive action")

class ReviewComment(BaseModel):
    comment_id: str = Field(..., description="Unique comment identifier")
    file_path: str = Field(..., description="Target file path")
    line_number: Optional[int] = Field(None, description="Specific line number in diff")
    symbol_name: Optional[str] = Field(None, description="Affected symbol or function name")
    severity: str = Field("warning", description="Severity: critical, warning, suggestion, nitpick")
    title: str = Field(..., description="Concise comment headline")
    body: str = Field(..., description="Detailed review feedback")
    evidence: str = Field("", description="Code evidence snippet")
    recommendation: str = Field("", description="Concrete action recommendation or code snippet")

class PullRequestAnalysis(BaseModel):
    pr_id: str = Field("pr_1", description="Pull request identifier")
    summary: PRSummary = Field(..., description="Executive and developer summaries")
    file_changes: List[FileChange] = Field(default_factory=list, description="Structured per-file diff analysis")
    architecture_impact: ArchitectureImpact = Field(default_factory=ArchitectureImpact, description="Architecture and dependency impact")
    test_recommendations: TestRecommendation = Field(default_factory=TestRecommendation, description="Test coverage and scenario recommendations")
    risks: List[RiskAssessment] = Field(default_factory=list, description="Static security and architectural risks")
    review_comments: List[ReviewComment] = Field(default_factory=list, description="Actionable inline review comments")
    analyzed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO timestamp")

class PRReviewResponse(BaseModel):
    verdict: str = Field("COMMENT", description="Review verdict: APPROVE, REQUEST_CHANGES, COMMENT")
    summary: PRSummary = Field(..., description="High-level PR summary")
    positive_findings: List[str] = Field(default_factory=list, description="Well-implemented aspects of the PR")
    risks: List[RiskAssessment] = Field(default_factory=list, description="Identified risks across security, architecture, and tests")
    suggestions: List[str] = Field(default_factory=list, description="Improvement and refactoring suggestions")
    required_follow_ups: List[str] = Field(default_factory=list, description="Mandatory actions before merging")
    review_comments: List[ReviewComment] = Field(default_factory=list, description="Evidence-backed review comments")
    sources: List[SourceAttribution] = Field(default_factory=list, description="Repository sources cited in review")

