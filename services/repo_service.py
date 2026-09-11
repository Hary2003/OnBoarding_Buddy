import os
import ast
import re
import math
import tempfile
import shutil
import stat
import time
from typing import Optional, List, Dict, Set, Tuple
from datetime import datetime
from git import Repo, GitCommandError

from models.repository_index import Symbol, Dependency, FileInfo, RepositoryIndex, GraphNode, GraphEdge

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
                            return_type = ast.unparse(n.returns) if n.returns else None
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

    def extract_dependencies(self, file_path: str, repo_path: str, file_map: Dict[str, str]) -> List[Dependency]:
        """Precise AST & pattern import extraction resolving internal files vs external packages."""
        deps: List[Dependency] = []
        source_rel = os.path.relpath(file_path, repo_path).replace("\\", "/")
        ext = os.path.splitext(file_path)[1].lower()

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            raw_imports: List[Tuple[str, str]] = [] # (module_path, statement)

            # Python AST import parsing
            if ext == ".py":
                try:
                    tree = ast.parse(content)
                    for n in ast.walk(tree):
                        if isinstance(n, ast.Import):
                            for alias in n.names:
                                raw_imports.append((alias.name, f"import {alias.name}"))
                        elif isinstance(n, ast.ImportFrom):
                            mod = n.module or ""
                            dots = "." * n.level
                            full_mod = f"{dots}{mod}"
                            for alias in n.names:
                                raw_imports.append((f"{full_mod}.{alias.name}", f"from {full_mod} import {alias.name}"))
                except SyntaxError:
                    pass

            # JS/TS ES6 & CommonJS import parsing
            if ext in [".js", ".ts", ".jsx", ".tsx"]:
                matches = re.findall(r'(?:import|from|require)\s*\(?[\'"]([^\'"]+)[\'"]\)?', content)
                for m in matches:
                    raw_imports.append((m, f"import {m}"))

            # Go & Java imports
            if ext in [".go", ".java", ".cs"]:
                matches = re.findall(r'import\s+(?:[\w.]+\s+)?[\'"]?([^\'"\s;]+)[\'"]?', content)
                for m in matches:
                    raw_imports.append((m, f"import {m}"))

            # Resolve targets against repository internal file_map
            seen_targets = set()
            for mod_str, raw_stmt in raw_imports:
                target_path = mod_str
                is_internal = False

                for rel_path in file_map.keys():
                    base_name = os.path.splitext(os.path.basename(rel_path))[0]
                    dotted_path = rel_path.replace("/", ".").replace(".py", "")

                    if (mod_str and mod_str.startswith(".")) or base_name == mod_str or mod_str in dotted_path or rel_path in mod_str:
                        target_path = rel_path
                        is_internal = True
                        break

                edge_key = (source_rel, target_path)
                if edge_key not in seen_targets:
                    seen_targets.add(edge_key)
                    deps.append(Dependency(
                        source_path=source_rel,
                        target_path=target_path,
                        import_statement=raw_stmt[:120],
                        is_internal=is_internal
                    ))

        except Exception:
            pass

        return deps

    def detect_circular_dependencies(self, file_info_list: List[FileInfo]) -> Set[str]:
        """Detects circular dependency cycles (A -> B -> A) using Tarjan's / DFS cycle detection."""
        graph: Dict[str, Set[str]] = {f.relative_path: set() for f in file_info_list}
        for f in file_info_list:
            for dep in f.dependencies:
                if dep.is_internal and dep.target_path in graph and dep.target_path != f.relative_path:
                    graph[f.relative_path].add(dep.target_path)

        circular_files: Set[str] = set()
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
                    for cycle_node in path[cycle_start_idx:]:
                        circular_files.add(cycle_node)

            rec_stack.remove(node)
            path.pop()

        for f in file_info_list:
            if f.relative_path not in visited:
                dfs(f.relative_path, [])

        return circular_files

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
                "title": f"<b>{f.relative_path}</b><br/>In-Degree: {f.in_degree} | Out-Degree: {f.out_degree}<br/>Score: {f.activity_score}",
                "group": f.language,
                "path": f.relative_path,
                "in_degree": f.in_degree,
                "out_degree": f.out_degree,
                "is_entry_point": f.is_entry_point,
                "is_circular": f.is_circular,
                "activity_score": f.activity_score,
                "symbols_count": len(f.symbols),
                "node_type": "internal"
            })

        edge_set = set()
        for f in files:
            source_id = file_map.get(f.relative_path)
            if not source_id: continue

            for dep in f.dependencies:
                if dep.is_internal and dep.target_path in file_map:
                    target_id = file_map[dep.target_path]
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
                            "node_type": "external_package"
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
                if dep.is_internal and dep.target_path in in_degree_map:
                    out_cnt += 1
                    in_degree_map[dep.target_path] += 1
            out_degree_map[info.relative_path] = out_cnt

        for info in file_info_list:
            info.in_degree = in_degree_map.get(info.relative_path, 0)
            info.out_degree = out_degree_map.get(info.relative_path, 0)

        # Circular dependency detection
        circular_files = self.detect_circular_dependencies(file_info_list)
        for info in file_info_list:
            if info.relative_path in circular_files:
                info.is_circular = True

        # Entry points detection
        entry_points = self.detect_entry_points(file_info_list)
        
        # Build dependency graph payload
        graph_data = self.extract_dependency_graph(repo_path, file_info_list, include_external=True)

        repo_index = RepositoryIndex(
            repo_name=os.path.basename(repo_path),
            repo_path=repo_path,
            total_files=len(file_info_list),
            total_lines=total_lines,
            languages_breakdown=languages_count,
            entry_points=entry_points,
            files=file_info_list,
            dependency_graph=graph_data
        )

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
