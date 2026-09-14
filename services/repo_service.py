import os
import ast
import re
import math
import posixpath
import tempfile
import shutil
import stat
import time
from typing import Optional, List, Dict, Set, Tuple
from datetime import datetime
from git import Repo, GitCommandError

from models.repository_index import Symbol, Dependency, FileInfo, RepositoryIndex, GraphNode, GraphEdge, CycleDetail, ArchitectureSummary

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".idea", ".vscode", "tmp", "temp"}
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".cs", ".html", ".css", ".json", ".md", ".yml", ".yaml"
}

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c_header",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml"
}

class RepoService:
    def clone_or_use_repo(self, target: str) -> Tuple[bool, str, str]:
        """Clones a remote git URL or validates a local directory path."""
        target = target.strip()
        if not target:
            return False, "", "Target repository path or URL is empty."
        
        if os.path.exists(target) and os.path.isdir(target):
            return True, os.path.abspath(target), ""
        
        if target.startswith("http://") or target.startswith("https://") or target.endswith(".git"):
            temp_dir = tempfile.mkdtemp(prefix="onboarding_repo_")
            try:
                Repo.clone_from(target, temp_dir, depth=1)
                return True, temp_dir, ""
            except GitCommandError as e:
                self.cleanup_temp_dir(temp_dir)
                return False, "", f"Git Clone Error: {str(e)}"
            except Exception as e:
                self.cleanup_temp_dir(temp_dir)
                return False, "", f"Failed to clone repository: {str(e)}"
        
        return False, "", f"Invalid path or repository URL: {target}"

    def get_repo_files(self, repo_path: str) -> List[str]:
        """Returns all relevant source code files in repository."""
        code_files = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    code_files.append(os.path.join(root, file))
        return sorted(code_files)

    def extract_symbols(self, file_path: str, language: str) -> List[Symbol]:
        """Extracts function, method, and class symbols with AST or regex."""
        symbols: List[Symbol] = []
        ext = os.path.splitext(file_path)[1].lower()

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if ext == ".py":
                try:
                    tree = ast.parse(content)
                    for n in ast.walk(tree):
                        if isinstance(n, ast.FunctionDef):
                            docstring = ast.get_docstring(n) or ""
                            args = [a.arg for a in n.args.args]
                            end_line = max([c.lineno for c in ast.walk(n) if hasattr(c, "lineno")], default=n.lineno)
                            return_type = ast.unparse(n.returns) if hasattr(ast, "unparse") and n.returns else None
                            symbols.append(Symbol(
                                name=n.name,
                                type="function",
                                line_number=n.lineno,
                                end_line=end_line,
                                parameters=args,
                                docstring=docstring[:300],
                                return_type=return_type
                            ))
                        elif isinstance(n, ast.ClassDef):
                            end_line = max([c.lineno for c in ast.walk(n) if hasattr(c, "lineno")], default=n.lineno)
                            symbols.append(Symbol(
                                name=n.name,
                                type="class",
                                line_number=n.lineno,
                                end_line=end_line,
                                parameters=[],
                                docstring=(ast.get_docstring(n) or "")[:300]
                            ))
                    symbols.sort(key=lambda s: s.line_number)
                    return symbols
                except SyntaxError:
                    pass

            func_patterns = [
                (r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', "function"),
                (r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)', "class"),
                (r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', "function"),
                (r'const\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>', "function"),
                (r'func\s+(?:\(.*?\)\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', "function"),
                (r'fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', "function"),
                (r'(?:public|private|protected|static|\s)+\s+[\w<>]+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', "method")
            ]

            lines = content.splitlines()
            for line_idx, line in enumerate(lines, start=1):
                for pattern, sym_type in func_patterns:
                    match = re.search(pattern, line)
                    if match:
                        name = match.group(1)
                        param_str = match.group(2) if len(match.groups()) > 1 and match.group(2) else ""
                        params = [p.strip().split(":")[0].strip() for p in param_str.split(",") if p.strip()]
                        symbols.append(Symbol(
                            name=name,
                            type=sym_type,
                            line_number=line_idx,
                            parameters=params
                        ))
                        break

        except Exception:
            pass

        return symbols

    def _resolve_python_import(self, source_rel: str, mod_str: str, level: int, file_map: Dict[str, str]) -> Tuple[Optional[str], bool, str]:
        """Resolves Python module import to internal repository relative path or external package."""
        source_dir = posixpath.dirname(source_rel)

        if level > 0:
            # Relative import (e.g. level 1 = ., level 2 = ..)
            curr_dir = source_dir
            for _ in range(level - 1):
                curr_dir = posixpath.dirname(curr_dir)

            mod_path = mod_str.replace(".", "/") if mod_str else ""
            candidates = []
            if mod_path:
                candidates.extend([
                    posixpath.normpath(posixpath.join(curr_dir, f"{mod_path}.py")),
                    posixpath.normpath(posixpath.join(curr_dir, mod_path, "__init__.py")),
                ])
            else:
                candidates.append(posixpath.normpath(posixpath.join(curr_dir, "__init__.py")))

            for cand in candidates:
                if cand in file_map:
                    return cand, True, "relative"

        # Absolute / package-style import (e.g. services.repo_service or models)
        mod_path = mod_str.replace(".", "/")
        candidates = [
            f"{mod_path}.py",
            f"{mod_path}/__init__.py",
            mod_path
        ]
        for cand in candidates:
            if cand in file_map:
                return cand, True, "package"

        # Match base name fallback
        base = mod_str.split(".")[0]
        for rel_path in file_map.keys():
            if rel_path == f"{base}.py" or rel_path.startswith(f"{base}/"):
                return rel_path, True, "package"

        return mod_str, False, "external"

    def _resolve_jsts_import(self, source_rel: str, import_path: str, file_map: Dict[str, str]) -> Tuple[Optional[str], bool, str]:
        """Resolves JS/TS import path to internal file or external package."""
        clean_path = import_path.split("?")[0].split("#")[0]
        
        if clean_path.startswith(".") or clean_path.startswith("/"):
            source_dir = posixpath.dirname(source_rel)
            resolved_base = posixpath.normpath(posixpath.join(source_dir, clean_path))
            
            extensions = ["", ".ts", ".tsx", ".js", ".jsx", ".json", "/index.ts", "/index.tsx", "/index.js", "/index.jsx"]
            for ext in extensions:
                cand = resolved_base + ext
                if cand in file_map:
                    return cand, True, "relative"
        
        # Check matching internal alias or file name
        for rel_path in file_map.keys():
            if rel_path.endswith(clean_path) or os.path.splitext(os.path.basename(rel_path))[0] == clean_path:
                return rel_path, True, "internal_alias"

        return clean_path, False, "external_package"

    def extract_dependencies(self, file_path: str, repo_path: str, file_map: Dict[str, str]) -> List[Dependency]:
        """Precise multi-language import extraction and path resolution."""
        deps: List[Dependency] = []
        source_rel = os.path.relpath(file_path, repo_path).replace("\\", "/")
        ext = os.path.splitext(file_path)[1].lower()

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            raw_imports: List[Tuple[str, str, int, str]] = [] # (mod_str, statement, level, import_kind)

            # Python AST import parsing
            if ext == ".py":
                try:
                    tree = ast.parse(content)
                    for n in ast.walk(tree):
                        if isinstance(n, ast.Import):
                            for alias in n.names:
                                raw_imports.append((alias.name, f"import {alias.name}", 0, "py"))
                        elif isinstance(n, ast.ImportFrom):
                            mod = n.module or ""
                            dots = "." * n.level
                            full_stmt = f"from {dots}{mod} import ..."
                            raw_imports.append((mod, full_stmt, n.level, "py"))
                except SyntaxError:
                    pass

            # JS/TS ES6 & CommonJS import parsing
            elif ext in [".js", ".ts", ".jsx", ".tsx"]:
                # match import x from 'y', import 'y', require('y'), export * from 'y'
                patterns = [
                    r'(?:import|from|require|export)\s*\(?\s*[\'"]([^\'"]+)[\'"]\s*\)?',
                    r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
                ]
                for pattern in patterns:
                    for m in re.findall(pattern, content):
                        raw_imports.append((m, f"import {m}", 0, "jsts"))

            # Go imports
            elif ext == ".go":
                matches = re.findall(r'import\s+(?:[\w.]+\s+)?[\'"]([^\'"]+)[\'"]', content)
                for m in matches:
                    raw_imports.append((m, f"import {m}", 0, "go"))

            # C / C++ includes
            elif ext in [".c", ".cpp", ".h"]:
                local_includes = re.findall(r'#include\s+"([^"]+)"', content)
                for inc in local_includes:
                    raw_imports.append((inc, f'#include "{inc}"', 0, "c_local"))
                sys_includes = re.findall(r'#include\s+<([^>]+)>', content)
                for inc in sys_includes:
                    raw_imports.append((inc, f'#include <{inc}>', 0, "c_sys"))

            # Java / C# / Rust imports
            elif ext in [".java", ".cs", ".rs"]:
                matches = re.findall(r'(?:import|using|use)\s+([a-zA-Z0-9_.:*]+);?', content)
                for m in matches:
                    raw_imports.append((m, f"import {m}", 0, "other"))

            seen_keys = set()
            for mod_str, raw_stmt, level, kind in raw_imports:
                target_path = mod_str
                resolved_path = None
                is_internal = False
                import_type = "external"

                if kind == "py":
                    resolved_cand, is_int, imp_t = self._resolve_python_import(source_rel, mod_str, level, file_map)
                    target_path = resolved_cand if is_int else mod_str
                    resolved_path = resolved_cand if is_int else None
                    is_internal = is_int
                    import_type = imp_t
                elif kind == "jsts":
                    resolved_cand, is_int, imp_t = self._resolve_jsts_import(source_rel, mod_str, file_map)
                    target_path = resolved_cand if is_int else mod_str
                    resolved_path = resolved_cand if is_int else None
                    is_internal = is_int
                    import_type = imp_t
                elif kind == "c_local":
                    source_dir = posixpath.dirname(source_rel)
                    cand = posixpath.normpath(posixpath.join(source_dir, mod_str))
                    if cand in file_map:
                        target_path = cand
                        resolved_path = cand
                        is_internal = True
                        import_type = "header_local"
                    else:
                        is_internal = False
                        import_type = "header_external"
                elif kind == "c_sys":
                    is_internal = False
                    import_type = "header_system"
                else:
                    # Match against file_map
                    for rel_path in file_map.keys():
                        base = os.path.splitext(os.path.basename(rel_path))[0]
                        if base and base in mod_str:
                            target_path = rel_path
                            resolved_path = rel_path
                            is_internal = True
                            import_type = "package"
                            break

                key = (source_rel, target_path)
                if key not in seen_keys and source_rel != target_path:
                    seen_keys.add(key)
                    deps.append(Dependency(
                        source_path=source_rel,
                        target_path=target_path,
                        import_statement=raw_stmt[:120],
                        is_internal=is_internal,
                        resolved_path=resolved_path,
                        import_type=import_type
                    ))

        except Exception:
            pass

        return deps

    def detect_circular_dependencies(self, file_info_list: List[FileInfo]) -> Tuple[Set[str], List[CycleDetail]]:
        """Detects circular dependency cycles (A -> B -> A) and returns affected files and detailed cycle paths."""
        graph: Dict[str, Set[str]] = {f.relative_path: set() for f in file_info_list}
        for f in file_info_list:
            for dep in f.dependencies:
                if dep.is_internal and dep.target_path in graph and dep.target_path != f.relative_path:
                    graph[f.relative_path].add(dep.target_path)

        circular_files: Set[str] = set()
        detected_cycles: List[CycleDetail] = []
        seen_cycle_tuples: Set[Tuple[str, ...]] = set()

        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Cycle found!
                    cycle_start_idx = path.index(neighbor) if neighbor in path else 0
                    cycle_path = path[cycle_start_idx:] + [neighbor]
                    
                    for cycle_node in cycle_path[:-1]:
                        circular_files.add(cycle_node)

                    # Deduplicate cycle representation
                    cycle_body = cycle_path[:-1]
                    min_idx = cycle_body.index(min(cycle_body))
                    norm_cycle = tuple(cycle_body[min_idx:] + cycle_body[:min_idx])
                    
                    if norm_cycle not in seen_cycle_tuples:
                        seen_cycle_tuples.add(norm_cycle)
                        cycle_id = f"cycle_{len(detected_cycles) + 1}"
                        detected_cycles.append(CycleDetail(
                            cycle_id=cycle_id,
                            path=cycle_path,
                            cycle_length=len(cycle_path) - 1
                        ))

            rec_stack.remove(node)
            path.pop()

        for f in file_info_list:
            if f.relative_path not in visited:
                dfs(f.relative_path, [])

        return circular_files, detected_cycles

    def classify_modules(self, file_info_list: List[FileInfo], entry_points: List[str]) -> Dict[str, int]:
        """Categorizes files into core, leaf, utility, entry_point, isolated, or standard."""
        counts = {"core": 0, "leaf": 0, "utility": 0, "entry_point": 0, "isolated": 0, "standard": 0}
        entry_set = set(entry_points)

        for info in file_info_list:
            category = "standard"

            if info.relative_path in entry_set or info.is_entry_point:
                category = "entry_point"
            elif info.in_degree == 0 and info.out_degree == 0:
                category = "isolated"
            elif info.out_degree == 0 and info.in_degree >= 1:
                category = "utility"
            elif info.out_degree == 0 and info.in_degree == 0:
                category = "leaf"
            elif info.in_degree >= 2 or (info.in_degree >= 1 and info.in_degree > info.out_degree):
                category = "core"
            else:
                category = "standard"

            info.module_category = category
            counts[category] += 1

        return counts

    def generate_architecture_summary(self, repo_index: RepositoryIndex) -> ArchitectureSummary:
        """Generates structured architectural breakdown from repository index metrics."""
        files = repo_index.files
        entry_pts = repo_index.entry_points
        
        # Sort core modules by in_degree descending
        core_files = [f.relative_path for f in sorted(files, key=lambda f: f.in_degree, reverse=True) if f.module_category == "core" or f.in_degree >= 1][:8]
        leaf_util_files = [f.relative_path for f in files if f.module_category in ["utility", "leaf"]][:8]
        
        # Determine likely architectural pattern
        langs = repo_index.languages_breakdown
        primary_lang = max(langs, key=langs.get) if langs else "unknown"

        arch_type = "Modular Component Architecture"
        if "python" in langs and any("fastapi" in f.full_path.lower() or "app.py" in f.relative_path or "server.py" in f.relative_path for f in files):
            arch_type = "FastAPI Modular Web Service"
        elif "javascript" in langs or "typescript" in langs:
            arch_type = "Fullstack Node.js / Web Application"
        elif len(files) <= 5:
            arch_type = "Compact Script / Service"
        elif len(core_files) >= 3:
            arch_type = "Layered Architecture with Core Utility Layer"

        narrative = (
            f"The codebase '{repo_index.repo_name}' follows a {arch_type} pattern written primarily in {primary_lang.capitalize()}. "
            f"It comprises {repo_index.total_files} source files totaling {repo_index.total_lines} lines of code across "
            f"{len(langs)} language group(s). "
            f"Key application entry point(s): {', '.join(entry_pts[:3]) if entry_pts else 'None detected'}. "
            f"Central core module hubs: {', '.join(core_files[:4]) if core_files else 'None'}. "
            f"Circular import cycles: {len(repo_index.circular_cycles)} cycle(s) detected."
        )

        return ArchitectureSummary(
            architecture_type=arch_type,
            entry_points_summary=entry_pts,
            core_modules=core_files,
            leaf_utility_modules=leaf_util_files,
            circular_dependencies_count=len(repo_index.circular_cycles),
            overview_narrative=narrative
        )

    def calculate_git_activity_scores(self, repo_path: str, files: List[str]) -> Dict[str, Tuple[int, str, float]]:
        """Calculates commit counts, last modified dates, and normalized 0-100 activity scores."""
        activity_data = {}
        file_commit_counts = {}
        file_dates = {}
        now = datetime.now()

        try:
            repo = Repo(repo_path)
            for f in files:
                rel_path = os.path.relpath(f, repo_path).replace("\\", "/")
                try:
                    commits = list(repo.iter_commits(paths=rel_path, max_count=50))
                    commit_cnt = len(commits)
                    if commits:
                        dt = datetime.fromtimestamp(commits[0].committed_date)
                    else:
                        dt = datetime.fromtimestamp(os.path.getmtime(f))
                except Exception:
                    commit_cnt = 1
                    dt = datetime.fromtimestamp(os.path.getmtime(f))

                file_commit_counts[f] = commit_cnt
                file_dates[f] = dt

        except Exception:
            for f in files:
                file_commit_counts[f] = 1
                file_dates[f] = datetime.fromtimestamp(os.path.getmtime(f))

        max_commits = max(file_commit_counts.values()) if file_commit_counts else 1

        for f in files:
            cnt = file_commit_counts[f]
            dt = file_dates[f]
            date_str = dt.strftime("%Y-%m-%d %H:%M")
            
            days_ago = max(0, (now - dt).days)
            recency_weight = math.exp(-days_ago / 90.0)
            commit_ratio = cnt / max(1, max_commits)
            
            score = round((0.6 * commit_ratio + 0.4 * recency_weight) * 100.0, 1)
            activity_data[f] = (cnt, date_str, score)

        return activity_data

    def detect_entry_points(self, file_info_list: List[FileInfo]) -> List[str]:
        """Detects application entry points using AST heuristics and file conventions."""
        entry_points = []

        entry_filenames = {"main.py", "app.py", "server.py", "index.py", "wsgi.py", "asgi.py",
                           "index.js", "main.js", "server.js", "app.js",
                           "index.ts", "main.ts", "server.ts", "app.ts",
                           "main.go"}

        for info in file_info_list:
            confidence = 0.0
            base_name = os.path.basename(info.relative_path).lower()

            if base_name in entry_filenames:
                confidence += 0.4

            if "/" not in info.relative_path and "\\" not in info.relative_path:
                confidence += 0.15

            symbol_names = {s.name for s in info.symbols}
            if "main" in symbol_names or "app" in symbol_names:
                confidence += 0.25

            try:
                with open(info.full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                if 'if __name__ == "__main__":' in content or "if __name__ == '__main__':" in content:
                    confidence += 0.4
                if "FastAPI(" in content or "Flask(" in content or "express(" in content or "app.listen(" in content:
                    confidence += 0.3
                if "func main()" in content or "public static void main(" in content:
                    confidence += 0.5
            except Exception:
                pass

            confidence = min(1.0, round(confidence, 2))
            if confidence >= 0.4:
                info.is_entry_point = True
                info.entry_point_confidence = confidence
                entry_points.append(info.relative_path)

        entry_points.sort(key=lambda path: next((f.entry_point_confidence for f in file_info_list if f.relative_path == path), 0.0), reverse=True)
        return entry_points

    def extract_dependency_graph(self, repo_path: str, files: List[FileInfo], include_external: bool = True) -> Dict:
        """Generates visual node/edge JSON dictionary with in_degree/out_degree centrality and external packages."""
        nodes = []
        edges = []
        file_map = {f.relative_path: str(idx) for idx, f in enumerate(files)}
        external_map: Dict[str, str] = {}
        ext_counter = len(files)

        for idx, f in enumerate(files):
            nodes.append({
                "id": str(idx),
                "label": f.file_name,
                "title": f"<b>{f.relative_path}</b><br/>Category: {f.module_category.upper()}<br/>In-Degree: {f.in_degree} | Out-Degree: {f.out_degree}<br/>Score: {f.activity_score}",
                "group": f.language,
                "path": f.relative_path,
                "in_degree": f.in_degree,
                "out_degree": f.out_degree,
                "is_entry_point": f.is_entry_point,
                "is_circular": f.is_circular,
                "activity_score": f.activity_score,
                "symbols_count": len(f.symbols),
                "node_type": "internal",
                "module_category": f.module_category
            })

        edge_set = set()
        for f in files:
            source_id = file_map.get(f.relative_path)
            if not source_id: continue

            for dep in f.dependencies:
                target_rel = dep.resolved_path or dep.target_path
                if dep.is_internal and target_rel in file_map:
                    target_id = file_map[target_rel]
                    if source_id != target_id:
                        edge_pair = (source_id, target_id)
                        if edge_pair not in edge_set:
                            edge_set.add(edge_pair)
                            edges.append({
                                "from": source_id,
                                "to": target_id,
                                "title": dep.import_statement,
                                "edge_type": "internal_import"
                            })
                elif include_external and not dep.is_internal and len(dep.target_path) < 40:
                    pkg_name = dep.target_path
                    if pkg_name not in external_map:
                        ext_id = str(ext_counter)
                        ext_counter += 1
                        external_map[pkg_name] = ext_id
                        nodes.append({
                            "id": ext_id,
                            "label": f"📦 {pkg_name}",
                            "title": f"External Package: {pkg_name}",
                            "group": "external",
                            "path": pkg_name,
                            "in_degree": 1,
                            "out_degree": 0,
                            "is_entry_point": False,
                            "is_circular": False,
                            "activity_score": 0.0,
                            "symbols_count": 0,
                            "node_type": "external_package",
                            "module_category": "external"
                        })
                    
                    ext_target_id = external_map[pkg_name]
                    edge_pair = (source_id, ext_target_id)
                    if edge_pair not in edge_set:
                        edge_set.add(edge_pair)
                        edges.append({
                            "from": source_id,
                            "to": ext_target_id,
                            "title": dep.import_statement,
                            "edge_type": "external_package"
                        })

        return {"nodes": nodes, "edges": edges}

    def parse_repository(self, target: str) -> Tuple[bool, Optional[RepositoryIndex], str]:
        """Main method: Parses repository into a unified RepositoryIndex object with dependency graph metrics."""
        success, repo_path, err_msg = self.clone_or_use_repo(target)
        if not success:
            return False, None, err_msg

        raw_files = self.get_repo_files(repo_path)
        if not raw_files:
            return False, None, "No supported source code files found in repository."

        activity_data = self.calculate_git_activity_scores(repo_path, raw_files)
        file_map = {os.path.relpath(f, repo_path).replace("\\", "/"): f for f in raw_files}

        file_info_list: List[FileInfo] = []
        total_lines = 0
        languages_count: Dict[str, int] = {}

        for f in raw_files:
            rel_path = os.path.relpath(f, repo_path).replace("\\", "/")
            ext = os.path.splitext(f)[1].lower()
            lang = LANGUAGE_MAP.get(ext, "other")
            languages_count[lang] = languages_count.get(lang, 0) + 1

            size_bytes = os.path.getsize(f)
            line_cnt = 0
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as file_obj:
                    line_cnt = len(file_obj.readlines())
            except Exception:
                pass
            total_lines += line_cnt

            cnt, date_str, act_score = activity_data.get(f, (1, "Recent", 50.0))

            symbols = self.extract_symbols(f, lang)
            deps = self.extract_dependencies(f, repo_path, file_map)

            info = FileInfo(
                full_path=f,
                relative_path=rel_path,
                file_name=os.path.basename(f),
                language=lang,
                size_bytes=size_bytes,
                line_count=line_cnt,
                last_modified=date_str,
                commit_count=cnt,
                activity_score=act_score,
                symbols=symbols,
                dependencies=deps
            )
            file_info_list.append(info)

        # Compute in_degree & out_degree for every file
        in_degree_map: Dict[str, int] = {f.relative_path: 0 for f in file_info_list}
        out_degree_map: Dict[str, int] = {f.relative_path: 0 for f in file_info_list}

        for info in file_info_list:
            out_cnt = 0
            for dep in info.dependencies:
                target_rel = dep.resolved_path or dep.target_path
                if dep.is_internal and target_rel in in_degree_map:
                    out_cnt += 1
                    in_degree_map[target_rel] += 1
            out_degree_map[info.relative_path] = out_cnt

        for info in file_info_list:
            info.in_degree = in_degree_map.get(info.relative_path, 0)
            info.out_degree = out_degree_map.get(info.relative_path, 0)

        # Circular dependency detection
        circular_files, circular_cycles = self.detect_circular_dependencies(file_info_list)
        for info in file_info_list:
            if info.relative_path in circular_files:
                info.is_circular = True

        # Entry points detection
        entry_points = self.detect_entry_points(file_info_list)
        
        # Classify modules (core, leaf, utility, entry_point, isolated, standard)
        module_counts = self.classify_modules(file_info_list, entry_points)

        # Build dependency graph payload
        graph_data = self.extract_dependency_graph(repo_path, file_info_list, include_external=True)

        repo_index = RepositoryIndex(
            repo_name=os.path.basename(repo_path),
            repo_path=repo_path,
            total_files=len(file_info_list),
            total_lines=total_lines,
            languages_breakdown=languages_count,
            entry_points=entry_points,
            circular_cycles=circular_cycles,
            module_counts=module_counts,
            files=file_info_list,
            dependency_graph=graph_data
        )

        # Generate architecture summary
        arch_summary = self.generate_architecture_summary(repo_index)
        repo_index.architecture_summary = arch_summary

        return True, repo_index, ""

    def force_remove_readonly(self, func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def cleanup_temp_dir(self, path: str, retries: int = 3, delay: float = 0.5):
        if os.path.exists(path):
            for _ in range(retries):
                try:
                    shutil.rmtree(path, onerror=self.force_remove_readonly)
                    return True
                except PermissionError:
                    time.sleep(delay)
        return False

repo_service = RepoService()
