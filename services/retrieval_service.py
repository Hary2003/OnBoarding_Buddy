import os
import re
from typing import List, Dict, Set, Tuple, Optional
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, Dependency,
    QueryAnalysis, RetrievalMatch, ScoredFile, RetrievedContextPayload
)

# Common English and programming stop words to ignore during query tokenization
STOP_WORDS = {
    "a", "an", "the", "in", "on", "of", "for", "to", "from", "with", "by", "at",
    "and", "or", "not", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "doing", "can", "could", "would",
    "should", "how", "what", "where", "when", "why", "which", "who", "whom",
    "this", "that", "these", "those", "it", "its", "handled", "work", "works",
    "show", "find", "get", "get_file", "code", "file", "files", "project", "repo"
}

# Domain-specific software engineering concept mapping
CONCEPT_SYNONYMS = {
    "db": ["database", "sql", "orm", "models", "connection", "schema", "sqlite", "postgres"],
    "database": ["db", "sql", "orm", "models", "connection", "schema"],
    "sql": ["db", "database", "query", "orm", "models"],
    "auth": ["authentication", "login", "user", "jwt", "token", "password", "session", "security"],
    "authentication": ["auth", "login", "user", "jwt", "token", "session"],
    "login": ["auth", "authentication", "user", "session"],
    "user": ["auth", "account", "profile"],
    "init": ["initialize", "initialization", "setup", "startup", "config", "settings", "configure"],
    "initialization": ["init", "initialize", "setup", "startup", "config", "settings"],
    "initialize": ["init", "initialization", "setup", "startup"],
    "setup": ["init", "initialization", "config", "startup"],
    "config": ["configuration", "settings", "env", "environment", "setup", "init"],
    "configuration": ["config", "settings", "env"],
    "settings": ["config", "configuration", "env"],
    "api": ["endpoint", "router", "route", "server", "fastapi", "flask", "express", "http", "rest"],
    "endpoint": ["api", "route", "router", "server", "fastapi", "rest"],
    "route": ["router", "api", "endpoint", "path"],
    "router": ["route", "api", "endpoint"],
    "server": ["app", "main", "api", "backend", "uvicorn", "express"],
    "service": ["services", "provider", "logic", "manager", "handler"],
    "summary": ["summarize", "summarizer", "groq", "ai", "llm", "overview"],
    "summarize": ["summary", "summarizer", "groq", "ai", "llm"],
    "dependency": ["dependencies", "graph", "import", "cycle", "circular", "in_degree"],
    "graph": ["dependency", "nodes", "edges", "viz", "vis"],
}

DEFAULT_SCORING_WEIGHTS = {
    "filename_exact": 5.0,
    "filename_token": 3.0,
    "symbol_exact": 5.0,
    "symbol_token": 3.0,
    "docstring": 3.0,
    "dependency": 2.0,
    "content": 2.0,
    "entry_point": 1.0,
    "core_module": 1.0,
    "git_activity": 1.0,
}

class QueryAnalyzer:
    def analyze(self, query: str) -> QueryAnalysis:
        """Converts natural-language query into normalized terms and concept expansions."""
        raw_text = query.lower()
        # Clean punctuation except underscores, dots, hyphens
        clean_text = re.sub(r'[^a-z0-9_.\-\s]', ' ', raw_text)
        raw_tokens = [t.strip() for t in clean_text.split() if t.strip()]

        normalized_terms = []
        for t in raw_tokens:
            if t not in STOP_WORDS and len(t) > 1:
                normalized_terms.append(t)

        expanded_concepts = set()
        for term in normalized_terms:
            syns = CONCEPT_SYNONYMS.get(term, [])
            for syn in syns:
                expanded_concepts.add(syn)
            # Lightweight suffix stemming
            if term.endswith("ing"):
                expanded_concepts.add(term[:-3])
            elif term.endswith("tion"):
                expanded_concepts.add(term[:-4])
            elif term.endswith("s") and len(term) > 3:
                expanded_concepts.add(term[:-1])

        return QueryAnalysis(
            original_query=query,
            normalized_terms=normalized_terms,
            expanded_concepts=sorted(list(expanded_concepts))
        )

class RepositoryRetriever:
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights if weights else DEFAULT_SCORING_WEIGHTS

    def score_file(self, file_info: FileInfo, query_analysis: QueryAnalysis, repo_path: str) -> ScoredFile:
        """Scores a single file using explainable signal rules."""
        total_score = 0.0
        matches: List[RetrievalMatch] = []
        matched_terms: Set[str] = set()
        signals: Set[str] = set()
        matched_symbols: Set[str] = set()

        all_query_terms = set(query_analysis.normalized_terms + query_analysis.expanded_concepts)
        file_base = file_info.file_name.lower()
        file_name_no_ext = os.path.splitext(file_base)[0]
        rel_path_lower = file_info.relative_path.lower()

        # 1. Filename Exact Match
        for term in query_analysis.normalized_terms:
            if term == file_name_no_ext or term == rel_path_lower:
                score = self.weights["filename_exact"]
                total_score += score
                signals.add("filename_exact")
                matched_terms.add(term)
                matches.append(RetrievalMatch(
                    signal_type="filename_exact",
                    score=score,
                    matched_term=term,
                    details=f"Exact match on filename '{file_info.file_name}'"
                ))

        # 2. Filename Token Match
        for term in all_query_terms:
            if len(term) >= 2 and (term in file_base or term in rel_path_lower):
                if "filename_exact" not in signals:
                    score = self.weights["filename_token"]
                    total_score += score
                    signals.add("filename_token")
                    matched_terms.add(term)
                    matches.append(RetrievalMatch(
                        signal_type="filename_token",
                        score=score,
                        matched_term=term,
                        details=f"Filename/path contains token '{term}'"
                    ))

        # 3. Symbol Exact & Token Match
        for sym in file_info.symbols:
            sym_name_lower = sym.name.lower()
            sym_doc_lower = (sym.docstring or "").lower()

            for term in query_analysis.normalized_terms:
                if term == sym_name_lower:
                    score = self.weights["symbol_exact"]
                    total_score += score
                    signals.add("symbol_exact")
                    matched_terms.add(term)
                    matched_symbols.add(f"{sym.name}() [{sym.type}]")
                    matches.append(RetrievalMatch(
                        signal_type="symbol_exact",
                        score=score,
                        matched_term=term,
                        details=f"Exact symbol match: {sym.type} '{sym.name}'"
                    ))
                elif len(term) >= 3 and term in sym_name_lower:
                    score = self.weights["symbol_token"]
                    total_score += score
                    signals.add("symbol_token")
                    matched_terms.add(term)
                    matched_symbols.add(f"{sym.name}() [{sym.type}]")
                    matches.append(RetrievalMatch(
                        signal_type="symbol_token",
                        score=score,
                        matched_term=term,
                        details=f"Symbol token match: {sym.type} '{sym.name}'"
                    ))

            # 4. Docstring Match
            for term in all_query_terms:
                if len(term) >= 3 and term in sym_doc_lower:
                    score = self.weights["docstring"]
                    total_score += score
                    signals.add("docstring")
                    matched_terms.add(term)
                    matches.append(RetrievalMatch(
                        signal_type="docstring",
                        score=score,
                        matched_term=term,
                        details=f"Symbol '{sym.name}' docstring matches '{term}'"
                    ))

        # 5. Dependency / Import Match
        for dep in file_info.dependencies:
            dep_target_lower = dep.target_path.lower()
            for term in all_query_terms:
                if len(term) >= 3 and term in dep_target_lower:
                    score = self.weights["dependency"]
                    total_score += score
                    signals.add("dependency")
                    matched_terms.add(term)
                    matches.append(RetrievalMatch(
                        signal_type="dependency",
                        score=score,
                        matched_term=term,
                        details=f"Imports module/file '{dep.target_path}'"
                    ))

        # 6. Code / Content Match (read content if file exists)
        if file_info.full_path and os.path.exists(file_info.full_path):
            try:
                with open(file_info.full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content_lower = f.read().lower()
                for term in query_analysis.normalized_terms:
                    if len(term) >= 3 and term in content_lower:
                        score = self.weights["content"]
                        total_score += score
                        signals.add("content")
                        matched_terms.add(term)
                        matches.append(RetrievalMatch(
                            signal_type="content",
                            score=score,
                            matched_term=term,
                            details=f"Source code contains term '{term}'"
                        ))
            except Exception:
                pass

        # 7. Structural Signals (Entry point, Core module, Git activity)
        if file_info.is_entry_point or file_info.module_category == "entry_point":
            score = self.weights["entry_point"]
            total_score += score
            signals.add("entry_point")
            matches.append(RetrievalMatch(
                signal_type="entry_point",
                score=score,
                matched_term="entry_point",
                details="Application entry point file"
            ))

        if file_info.module_category == "core" or file_info.in_degree >= 2:
            score = self.weights["core_module"]
            total_score += score
            signals.add("core_module")
            matches.append(RetrievalMatch(
                signal_type="core_module",
                score=score,
                matched_term="core_module",
                details=f"Central core module (in_degree: {file_info.in_degree})"
            ))

        if file_info.activity_score >= 60.0:
            score = self.weights["git_activity"]
            total_score += score
            signals.add("git_activity")
            matches.append(RetrievalMatch(
                signal_type="git_activity",
                score=score,
                matched_term="active",
                details=f"High Git activity score ({file_info.activity_score})"
            ))

        return ScoredFile(
            relative_path=file_info.relative_path,
            file_name=file_info.file_name,
            language=file_info.language,
            module_category=file_info.module_category,
            total_score=round(total_score, 2),
            matched_terms=sorted(list(matched_terms)),
            signals=sorted(list(signals)),
            match_explanations=matches,
            is_expanded_dependency=False,
            expansion_reason=None,
            matched_symbols=sorted(list(matched_symbols))
        )

    def retrieve(self, repo_index: RepositoryIndex, query: str, top_n: int = 10) -> Tuple[QueryAnalysis, List[ScoredFile]]:
        """Analyzes query and scores all repository files."""
        analyzer = QueryAnalyzer()
        query_analysis = analyzer.analyze(query)

        scored_files: List[ScoredFile] = []
        for f in repo_index.files:
            scored = self.score_file(f, query_analysis, repo_index.repo_path)
            if scored.total_score > 0.0:
                scored_files.append(scored)

        scored_files.sort(key=lambda sf: sf.total_score, reverse=True)
        return query_analysis, scored_files[:top_n]

class DependencyExpander:
    def expand(self, primary_results: List[ScoredFile], repo_index: RepositoryIndex, max_depth: int = 2, max_related_files: int = 5) -> List[ScoredFile]:
        """Expands top candidates by adding downstream dependencies and upstream dependants from M2 graph."""
        existing_paths = {sf.relative_path for sf in primary_results}
        file_info_map = {f.relative_path: f for f in repo_index.files}

        expanded_results = list(primary_results)
        added_count = 0

        # Traverse primary candidates
        for primary in primary_results:
            if added_count >= max_related_files:
                break

            primary_info = file_info_map.get(primary.relative_path)
            if not primary_info:
                continue

            # 1. Downstream dependencies (files imported by primary)
            for dep in primary_info.dependencies:
                target_rel = dep.resolved_path or dep.target_path
                if dep.is_internal and target_rel in file_info_map and target_rel not in existing_paths:
                    existing_paths.add(target_rel)
                    target_info = file_info_map[target_rel]
                    
                    expanded_file = ScoredFile(
                        relative_path=target_info.relative_path,
                        file_name=target_info.file_name,
                        language=target_info.language,
                        module_category=target_info.module_category,
                        total_score=round(max(1.0, primary.total_score * 0.5), 2),
                        matched_terms=primary.matched_terms,
                        signals=["dependency_expansion"],
                        match_explanations=[RetrievalMatch(
                            signal_type="dependency_expansion",
                            score=1.5,
                            matched_term=primary.relative_path,
                            details=f"Direct dependency of top candidate '{primary.relative_path}'"
                        )],
                        is_expanded_dependency=True,
                        expansion_reason=f"Direct dependency of '{primary.relative_path}'",
                        matched_symbols=[s.name for s in target_info.symbols[:3]]
                    )
                    expanded_results.append(expanded_file)
                    added_count += 1
                    if added_count >= max_related_files:
                        break

            # 2. Upstream dependants (files that import primary)
            if added_count < max_related_files:
                for candidate_rel, candidate_info in file_info_map.items():
                    if candidate_rel not in existing_paths:
                        for dep in candidate_info.dependencies:
                            target_rel = dep.resolved_path or dep.target_path
                            if target_rel == primary.relative_path:
                                existing_paths.add(candidate_rel)
                                expanded_file = ScoredFile(
                                    relative_path=candidate_info.relative_path,
                                    file_name=candidate_info.file_name,
                                    language=candidate_info.language,
                                    module_category=candidate_info.module_category,
                                    total_score=round(max(1.0, primary.total_score * 0.4), 2),
                                    matched_terms=primary.matched_terms,
                                    signals=["dependant_expansion"],
                                    match_explanations=[RetrievalMatch(
                                        signal_type="dependant_expansion",
                                        score=1.0,
                                        matched_term=primary.relative_path,
                                        details=f"Imports top candidate '{primary.relative_path}'"
                                    )],
                                    is_expanded_dependency=True,
                                    expansion_reason=f"Dependant importing '{primary.relative_path}'",
                                    matched_symbols=[s.name for s in candidate_info.symbols[:3]]
                                )
                                expanded_results.append(expanded_file)
                                added_count += 1
                                if added_count >= max_related_files:
                                    break

        return expanded_results

class ContextBuilder:
    def build(self, query: str, repo_index: RepositoryIndex, query_analysis: QueryAnalysis, scored_files: List[ScoredFile], max_files: int = 8, max_tokens: int = 12000) -> RetrievedContextPayload:
        """Transforms retrieval results into structured, LLM-ready markdown context."""
        selected_files = scored_files[:max_files]
        file_info_map = {f.relative_path: f for f in repo_index.files}

        lines = []
        lines.append(f"# Repository Context for Developer Question")
        lines.append(f"**Repository**: {repo_index.repo_name}")
        lines.append(f"**Developer Question**: \"{query}\"")
        lines.append(f"**Query Analysis Tokens**: {', '.join(query_analysis.normalized_terms)}")
        if query_analysis.expanded_concepts:
            lines.append(f"**Concept Expansions**: {', '.join(query_analysis.expanded_concepts)}")
        lines.append("")
        lines.append(f"## Top Relevant Repository Files ({len(selected_files)} files retrieved)")
        lines.append("")

        char_budget = max_tokens * 4
        current_chars = len("\n".join(lines))

        for idx, sf in enumerate(selected_files, start=1):
            file_info = file_info_map.get(sf.relative_path)
            
            header = f"### [{idx}] `{sf.relative_path}`"
            meta = f"- **Category**: {sf.module_category.upper()} | **Language**: {sf.language} | **Relevance Score**: {sf.total_score}"
            
            exp_details = []
            if sf.is_expanded_dependency:
                exp_details.append(f"- 🔗 **Included via**: {sf.expansion_reason}")
            else:
                signals_str = ", ".join([f"{m.signal_type} (+{m.score})" for m in sf.match_explanations[:4]])
                exp_details.append(f"- 🎯 **Matched Signals**: {signals_str}")
            
            if sf.matched_symbols:
                exp_details.append(f"- 🧩 **Relevant Symbols**: {', '.join(sf.matched_symbols[:5])}")

            code_snippet_block = ""
            if file_info and file_info.full_path and os.path.exists(file_info.full_path):
                try:
                    with open(file_info.full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    snippet = content[:2000] # Cap snippet length per file
                    if len(content) > 2000:
                        snippet += "\n... (truncated)"
                    code_snippet_block = f"```\n{snippet}\n```"
                except Exception:
                    code_snippet_block = "*Could not load source file content.*"

            block_text = f"{header}\n{meta}\n" + "\n".join(exp_details) + f"\n\n**Code Snippet**:\n{code_snippet_block}\n\n---\n"
            
            if current_chars + len(block_text) > char_budget:
                lines.append(f"*(Remaining {len(selected_files) - idx + 1} files truncated to fit token budget)*")
                break

            lines.append(block_text)
            current_chars += len(block_text)

        formatted_context = "\n".join(lines)
        estimated_tokens = len(formatted_context) // 4

        return RetrievedContextPayload(
            repo_name=repo_index.repo_name,
            query=query,
            query_analysis=query_analysis,
            scored_files=selected_files,
            formatted_context=formatted_context,
            total_files_retrieved=len(selected_files),
            estimated_tokens=estimated_tokens
        )

# Global Retrieval Engine instance
class ContextRetrievalEngine:
    def __init__(self):
        self.analyzer = QueryAnalyzer()
        self.retriever = RepositoryRetriever()
        self.expander = DependencyExpander()
        self.builder = ContextBuilder()

    def process_query(self, repo_index: RepositoryIndex, query: str, max_files: int = 8, expand_dependencies: bool = True) -> RetrievedContextPayload:
        query_analysis, scored_files = self.retriever.retrieve(repo_index, query, top_n=max_files)
        
        if expand_dependencies and scored_files:
            scored_files = self.expander.expand(scored_files, repo_index, max_related_files=4)

        return self.builder.build(query, repo_index, query_analysis, scored_files, max_files=max_files)

retrieval_engine = ContextRetrievalEngine()
