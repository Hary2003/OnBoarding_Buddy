import os
import re
from typing import Any, Dict, List, Optional

from models.repository_index import FileInfo, RepositoryIndex
from services.agent.tool_registry import AgentToolSpec, RepositoryToolRegistry
from services.retrieval_service import retrieval_engine


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class RepositoryAgentTools:
    """Read-only repository tools backed by the active RepositoryIndex."""

    def __init__(self, repo_index: RepositoryIndex):
        self.repo_index = repo_index
        self.file_map: Dict[str, FileInfo] = {f.relative_path: f for f in repo_index.files}

    def _file(self, file_path: str) -> FileInfo:
        normalized = (file_path or "").replace("\\", "/").lstrip("/")
        info = self.file_map.get(normalized)
        if not info:
            raise ValueError(f"File is not part of the repository index: {file_path}")
        return info

    def _read_indexed_file(self, info: FileInfo) -> str:
        repo_root = os.path.abspath(self.repo_index.repo_path)
        full_path = os.path.abspath(info.full_path)
        if not full_path.startswith(repo_root):
            raise ValueError("Indexed file resolves outside the repository root.")
        with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()

    def search_repository(self, query: str, limit: int = 10) -> Dict[str, Any]:
        if not query or not query.strip():
            raise ValueError("query is required")
        limit = max(1, min(int(limit or 10), 25))
        _, scored = retrieval_engine.retriever.retrieve(self.repo_index, query, top_n=limit)
        results = []
        for item in scored:
            evidence_signals = [
                signal for signal in item.signals
                if signal not in {"entry_point", "core_module", "git_activity"}
            ]
            if not item.matched_terms and not item.matched_symbols and not evidence_signals:
                continue
            reason = item.signals[0] if item.signals else "retrieval_match"
            results.append({
                "file_path": item.relative_path,
                "file_name": item.file_name,
                "score": item.total_score,
                "matched_terms": item.matched_terms,
                "matched_symbols": item.matched_symbols,
                "reason": reason,
                "signals": item.signals
            })
        return {"success": True, "tool": "search_repository", "query": query, "results": results}

    def get_file(self, file_path: str, max_chars: int = 4000) -> Dict[str, Any]:
        info = self._file(file_path)
        max_chars = max(200, min(int(max_chars or 4000), 12000))
        content = self._read_indexed_file(info)
        return {
            "success": True,
            "tool": "get_file",
            "file_path": info.relative_path,
            "language": info.language,
            "line_count": info.line_count,
            "module_category": info.module_category,
            "symbols": [_model_to_dict(sym) for sym in info.symbols],
            "dependencies": [_model_to_dict(dep) for dep in info.dependencies],
            "content": content[:max_chars],
            "truncated": len(content) > max_chars
        }

    def get_symbol(self, file_path: str, symbol_name: str, context_lines: int = 20) -> Dict[str, Any]:
        info = self._file(file_path)
        if not symbol_name:
            raise ValueError("symbol_name is required")
        symbol = next((sym for sym in info.symbols if sym.name == symbol_name), None)
        if not symbol:
            raise ValueError(f"Symbol '{symbol_name}' was not found in {info.relative_path}")

        lines = self._read_indexed_file(info).splitlines()
        start = max(1, symbol.line_number - 2)
        end = symbol.end_line or min(len(lines), symbol.line_number + context_lines)
        end = min(len(lines), max(end, symbol.line_number))
        snippet = "\n".join(lines[start - 1:end])
        return {
            "success": True,
            "tool": "get_symbol",
            "file_path": info.relative_path,
            "symbol": _model_to_dict(symbol),
            "snippet": snippet,
            "start_line": start,
            "end_line": end
        }

    def find_references(self, symbol_name: str, file_path: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        if not symbol_name:
            raise ValueError("symbol_name is required")
        limit = max(1, min(int(limit or 20), 50))
        files = [self._file(file_path)] if file_path else self.repo_index.files
        pattern = re.compile(rf"\b{re.escape(symbol_name)}\b")
        refs = []

        for info in files:
            try:
                for line_no, line in enumerate(self._read_indexed_file(info).splitlines(), start=1):
                    if pattern.search(line):
                        refs.append({
                            "file_path": info.relative_path,
                            "line_number": line_no,
                            "line": line.strip()[:240],
                            "source_type": "content_match"
                        })
                        if len(refs) >= limit:
                            break
            except Exception:
                continue
            if len(refs) >= limit:
                break

        return {"success": True, "tool": "find_references", "symbol_name": symbol_name, "references": refs}

    def get_dependencies(self, file_path: str) -> Dict[str, Any]:
        info = self._file(file_path)
        deps = []
        paths = []
        for dep in info.dependencies:
            target = dep.resolved_path or dep.target_path
            deps.append(_model_to_dict(dep))
            if dep.is_internal:
                paths.append(f"{info.relative_path} -> {target}")
        return {
            "success": True,
            "tool": "get_dependencies",
            "file_path": info.relative_path,
            "dependencies": deps,
            "dependency_paths": paths
        }

    def get_dependants(self, file_path: str) -> Dict[str, Any]:
        target = self._file(file_path).relative_path
        dependants = []
        paths = []
        for info in self.repo_index.files:
            for dep in info.dependencies:
                dep_target = dep.resolved_path or dep.target_path
                if dep.is_internal and dep_target == target:
                    dependants.append({
                        "file_path": info.relative_path,
                        "import_statement": dep.import_statement,
                        "module_category": info.module_category
                    })
                    paths.append(f"{info.relative_path} -> {target}")
                    break
        return {
            "success": True,
            "tool": "get_dependants",
            "file_path": target,
            "dependants": dependants,
            "dependency_paths": paths
        }

    def find_entry_points(self, limit: int = 10) -> Dict[str, Any]:
        limit = max(1, min(int(limit or 10), 25))
        entries = []
        entry_set = set(self.repo_index.entry_points)
        candidates = [f for f in self.repo_index.files if f.relative_path in entry_set or f.is_entry_point]
        candidates.sort(key=lambda f: f.entry_point_confidence, reverse=True)
        for info in candidates[:limit]:
            entries.append({
                "file_path": info.relative_path,
                "confidence": info.entry_point_confidence,
                "symbols": [_model_to_dict(sym) for sym in info.symbols[:8]],
                "dependencies_count": len(info.dependencies),
                "module_category": info.module_category
            })
        return {"success": True, "tool": "find_entry_points", "entry_points": entries}

    def find_tests(self, file_path: Optional[str] = None, query: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        limit = max(1, min(int(limit or 20), 50))
        target = self._file(file_path).relative_path if file_path else None
        target_base = os.path.splitext(os.path.basename(target or ""))[0].lower()
        query_lower = (query or "").lower()
        tests = []

        for info in self.repo_index.files:
            rel_lower = info.relative_path.lower()
            name_lower = info.file_name.lower()
            is_test = rel_lower.startswith("tests/") or "test_" in name_lower or "_test" in name_lower or ".spec." in name_lower
            if not is_test:
                continue

            reason = "test_file_convention"
            if target:
                test_base = os.path.splitext(info.file_name)[0].lower()
                imports_target = any((dep.resolved_path or dep.target_path) == target for dep in info.dependencies)
                name_matches = target_base and (target_base in test_base or test_base.replace("test_", "") in target_base)
                if not imports_target and not name_matches:
                    continue
                reason = "imports_target" if imports_target else "name_convention_match"
            elif query_lower and query_lower not in rel_lower:
                try:
                    if query_lower not in self._read_indexed_file(info).lower():
                        continue
                except Exception:
                    continue
                reason = "query_match"

            tests.append({
                "file_path": info.relative_path,
                "reason": reason,
                "symbols": [sym.name for sym in info.symbols[:8]]
            })
            if len(tests) >= limit:
                break

        return {"success": True, "tool": "find_tests", "target_file": target, "tests": tests}

    def get_architecture(self) -> Dict[str, Any]:
        arch = self.repo_index.architecture_summary
        return {
            "success": True,
            "tool": "get_architecture",
            "repo_name": self.repo_index.repo_name,
            "total_files": self.repo_index.total_files,
            "total_lines": self.repo_index.total_lines,
            "languages_breakdown": self.repo_index.languages_breakdown,
            "module_counts": self.repo_index.module_counts,
            "entry_points": self.repo_index.entry_points,
            "architecture_summary": _model_to_dict(arch) if arch else {},
            "circular_cycles": [_model_to_dict(cycle) for cycle in self.repo_index.circular_cycles]
        }

    def get_git_activity(self, limit: int = 10) -> Dict[str, Any]:
        limit = max(1, min(int(limit or 10), 50))
        ranked = sorted(self.repo_index.files, key=lambda info: info.activity_score, reverse=True)
        return {
            "success": True,
            "tool": "get_git_activity",
            "files": [
                {
                    "file_path": info.relative_path,
                    "activity_score": info.activity_score,
                    "commit_count": info.commit_count,
                    "last_modified": info.last_modified,
                    "module_category": info.module_category
                }
                for info in ranked[:limit]
            ]
        }

    # --- M7 Pull Request Intelligence Tools ---

    def get_pr_diff(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        if not hasattr(self, "_pr_diff") or not self._pr_diff:
            raise ValueError("No active PR diff loaded in this investigation session.")
        if file_path and hasattr(self, "_pr_analysis") and self._pr_analysis:
            norm = file_path.replace("\\", "/").lstrip("/")
            fc = next((f for f in self._pr_analysis.file_changes if f.file_path == norm), None)
            if fc:
                return {"success": True, "tool": "get_pr_diff", "file_path": norm, "patch": fc.patch}
        return {"success": True, "tool": "get_pr_diff", "diff": self._pr_diff}

    def get_changed_files(self) -> Dict[str, Any]:
        if not hasattr(self, "_pr_analysis") or not self._pr_analysis:
            raise ValueError("No active PR diff loaded in this investigation session.")
        return {
            "success": True,
            "tool": "get_changed_files",
            "files": [
                {
                    "file_path": fc.file_path,
                    "status": fc.status,
                    "additions": fc.additions,
                    "deletions": fc.deletions,
                    "modified_symbols": fc.modified_symbols
                }
                for fc in self._pr_analysis.file_changes
            ]
        }

    def get_changed_symbols(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        if not hasattr(self, "_pr_analysis") or not self._pr_analysis:
            raise ValueError("No active PR diff loaded in this investigation session.")
        if file_path:
            norm = file_path.replace("\\", "/").lstrip("/")
            fc = next((f for f in self._pr_analysis.file_changes if f.file_path == norm), None)
            syms = fc.modified_symbols if fc else []
            return {"success": True, "tool": "get_changed_symbols", "file_path": norm, "symbols": syms}
        all_syms: Dict[str, List[str]] = {
            fc.file_path: fc.modified_symbols for fc in self._pr_analysis.file_changes if fc.modified_symbols
        }
        return {"success": True, "tool": "get_changed_symbols", "symbols_by_file": all_syms}

    def review_architecture(self) -> Dict[str, Any]:
        if not hasattr(self, "_pr_analysis") or not self._pr_analysis:
            raise ValueError("No active PR diff loaded in this investigation session.")
        arch = self._pr_analysis.architecture_impact
        return {
            "success": True,
            "tool": "review_architecture",
            "architecture_impact": _model_to_dict(arch)
        }

    def review_security(self) -> Dict[str, Any]:
        if not hasattr(self, "_pr_analysis") or not self._pr_analysis:
            raise ValueError("No active PR diff loaded in this investigation session.")
        return {
            "success": True,
            "tool": "review_security",
            "risks": [_model_to_dict(r) for r in self._pr_analysis.risks]
        }

    def review_tests(self) -> Dict[str, Any]:
        if not hasattr(self, "_pr_analysis") or not self._pr_analysis:
            raise ValueError("No active PR diff loaded in this investigation session.")
        rec = self._pr_analysis.test_recommendations
        return {
            "success": True,
            "tool": "review_tests",
            "test_recommendations": _model_to_dict(rec)
        }

    def summarize_changes(self) -> Dict[str, Any]:
        if not hasattr(self, "_pr_analysis") or not self._pr_analysis:
            raise ValueError("No active PR diff loaded in this investigation session.")
        summary = self._pr_analysis.summary
        return {
            "success": True,
            "tool": "summarize_changes",
            "summary": _model_to_dict(summary)
        }


def build_repository_tool_registry(
    repo_index: RepositoryIndex,
    diff_text: Optional[str] = None
) -> RepositoryToolRegistry:
    tools = RepositoryAgentTools(repo_index)
    registry = RepositoryToolRegistry()
    registry.register(AgentToolSpec("search_repository", "Search indexed repository files and symbols.", {"query": "str", "limit": "int=10"}, tools.search_repository))
    registry.register(AgentToolSpec("get_file", "Read an indexed repository file with metadata.", {"file_path": "str", "max_chars": "int=4000"}, tools.get_file))
    registry.register(AgentToolSpec("get_symbol", "Inspect an indexed symbol and source snippet.", {"file_path": "str", "symbol_name": "str", "context_lines": "int=20"}, tools.get_symbol))
    registry.register(AgentToolSpec("find_references", "Find indexed references to a symbol or term.", {"symbol_name": "str", "file_path": "str|None", "limit": "int=20"}, tools.find_references))
    registry.register(AgentToolSpec("get_dependencies", "List downstream imports for an indexed file.", {"file_path": "str"}, tools.get_dependencies))
    registry.register(AgentToolSpec("get_dependants", "List upstream files importing an indexed file.", {"file_path": "str"}, tools.get_dependants))
    registry.register(AgentToolSpec("find_entry_points", "Find likely application entry points.", {"limit": "int=10"}, tools.find_entry_points))
    registry.register(AgentToolSpec("find_tests", "Find tests related to a file or query.", {"file_path": "str|None", "query": "str|None", "limit": "int=20"}, tools.find_tests))
    registry.register(AgentToolSpec("get_architecture", "Return repository architecture summary and graph health.", {}, tools.get_architecture))
    registry.register(AgentToolSpec("get_git_activity", "Return most active files from Git/file activity metadata.", {"limit": "int=10"}, tools.get_git_activity))

    # M7 PR Intelligence Tools
    if diff_text:
        from services.pr_service import pr_service
        tools._pr_diff = diff_text
        tools._pr_analysis = pr_service.analyze_pr(diff_text, repo_index=repo_index)
        registry.register(AgentToolSpec("get_pr_diff", "Return full or per-file unified git diff patch.", {"file_path": "str|None"}, tools.get_pr_diff))
        registry.register(AgentToolSpec("get_changed_files", "Return list of files modified, added, or deleted in PR.", {}, tools.get_changed_files))
        registry.register(AgentToolSpec("get_changed_symbols", "Return functions and symbols modified in PR.", {"file_path": "str|None"}, tools.get_changed_symbols))
        registry.register(AgentToolSpec("review_architecture", "Evaluate PR architectural impact and layer violations.", {}, tools.review_architecture))
        registry.register(AgentToolSpec("review_security", "Return static security risks detected in PR diff additions.", {}, tools.review_security))
        registry.register(AgentToolSpec("review_tests", "Return test impact, missing test alerts, and recommended scenarios.", {}, tools.review_tests))
        registry.register(AgentToolSpec("summarize_changes", "Return executive and developer summary of PR changes.", {}, tools.summarize_changes))

    return registry


def build_pr_tool_registry(repo_index: RepositoryIndex, diff_text: str) -> RepositoryToolRegistry:
    return build_repository_tool_registry(repo_index, diff_text=diff_text)

