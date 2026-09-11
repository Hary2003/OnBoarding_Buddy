import os
import ast
import re
import math
import tempfile
import shutil
import stat
import time
from typing import Optional
from datetime import datetime
from git import Repo, GitCommandError

from models.repository_index import Symbol, Dependency, FileInfo, RepositoryIndex

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
    def clone_or_use_repo(self, target: str) -> tuple[bool, str, str]:
        """Clones a remote git URL or validates a local directory path."""
        target = target.strip()
        if not target:
            return False, "", "Target repository path or URL is empty."
        
        # Check if local path exists
        if os.path.exists(target) and os.path.isdir(target):
            return True, os.path.abspath(target), ""
        
        # If GitHub URL or git URL
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

    def get_repo_files(self, repo_path: str) -> list[str]:
        """Returns all relevant source code files in repository."""
        code_files = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    code_files.append(os.path.join(root, file))
        return sorted(code_files)

    def extract_symbols(self, file_path: str, language: str) -> list[Symbol]:
        """Extracts function, method, and class symbols with AST or regex."""
        symbols: list[Symbol] = []
        ext = os.path.splitext(file_path)[1].lower()

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # --- Python AST Parser ---
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

            # --- Multi-Language Regex Fallback (JS, TS, Go, Java, Rust) ---
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

    def extract_dependencies(self, file_path: str, repo_path: str, file_map: dict[str, str]) -> list[Dependency]:
        """Resolves imported dependencies and checks if internal to repository."""
        deps: list[Dependency] = []
        source_rel = os.path.relpath(file_path, repo_path).replace("\\", "/")
        ext = os.path.splitext(file_path)[1].lower()

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            import_lines = []
            if ext == ".py":
                for line in content.splitlines():
                    line_str = line.strip()
                    if line_str.startswith("import ") or line_str.startswith("from "):
                        import_lines.append(line_str)
            elif ext in [".js", ".ts", ".jsx", ".tsx"]:
                import_matches = re.findall(r'(?:import|require)\s*\(?[\'"]([^\'"]+)[\'"]\)?', content)
                import_lines = [f"import {m}" for m in import_matches]
            elif ext == ".go":
                import_matches = re.findall(r'import\s+[\'"]([^\'"]+)[\'"]', content)
                import_lines = [f"import {m}" for m in import_matches]

            for raw_import in import_lines:
                target_path = raw_import
                is_internal = False
                
                # Check match against repo relative file paths
                for rel_path in file_map.keys():
                    base_mod = os.path.splitext(os.path.basename(rel_path))[0]
                    mod_path = rel_path.replace("/", ".").replace(".py", "")
                    
                    if base_mod in raw_import or mod_path in raw_import or rel_path in raw_import:
                        target_path = rel_path
                        is_internal = True
                        break

                deps.append(Dependency(
                    source_path=source_rel,
                    target_path=target_path,
                    import_statement=raw_import[:120],
                    is_internal=is_internal
                ))

        except Exception:
            pass

        return deps

    def calculate_git_activity_scores(self, repo_path: str, files: list[str]) -> dict[str, tuple[int, str, float]]:
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
            # Non-git folder fallback
            for f in files:
                file_commit_counts[f] = 1
                file_dates[f] = datetime.fromtimestamp(os.path.getmtime(f))

        max_commits = max(file_commit_counts.values()) if file_commit_counts else 1

        for f in files:
            cnt = file_commit_counts[f]
            dt = file_dates[f]
            date_str = dt.strftime("%Y-%m-%d %H:%M")
            
            # Recency decay (days since last modification)
            days_ago = max(0, (now - dt).days)
            recency_weight = math.exp(-days_ago / 90.0) # 90-day half-life decay
            commit_ratio = cnt / max(1, max_commits)
            
            # Composite Activity Score (0.0 to 100.0)
            score = round((0.6 * commit_ratio + 0.4 * recency_weight) * 100.0, 1)
            activity_data[f] = (cnt, date_str, score)

        return activity_data

    def detect_entry_points(self, file_info_list: list[FileInfo]) -> list[str]:
        """Detects application entry points using AST heuristics and file conventions."""
        entry_points = []

        entry_filenames = {"main.py", "app.py", "server.py", "index.py", "wsgi.py", "asgi.py",
                           "index.js", "main.js", "server.js", "app.js",
                           "index.ts", "main.ts", "server.ts", "app.ts",
                           "main.go"}

        for info in file_info_list:
            confidence = 0.0
            base_name = os.path.basename(info.relative_path).lower()

            # Filename heuristic
            if base_name in entry_filenames:
                confidence += 0.4

            # Root directory bonus
            if "/" not in info.relative_path and "\\" not in info.relative_path:
                confidence += 0.15

            # Symbol & Content AST heuristics
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

    def extract_dependency_graph(self, repo_path: str, files: list[FileInfo]) -> dict:
        """Generates visual node/edge JSON dictionary for frontend visualizer."""
        nodes = []
        edges = []
        file_map = {f.relative_path: str(idx) for idx, f in enumerate(files)}

        for idx, f in enumerate(files):
            nodes.append({
                "id": str(idx),
                "label": f.file_name,
                "title": f"{f.relative_path} (Score: {f.activity_score})",
                "group": f.language
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
                            edges.append({"from": source_id, "to": target_id})

        return {"nodes": nodes, "edges": edges}

    def parse_repository(self, target: str) -> tuple[bool, Optional[RepositoryIndex], str]:
        """Main method: Parses repository into a unified RepositoryIndex object."""
        success, repo_path, err_msg = self.clone_or_use_repo(target)
        if not success:
            return False, None, err_msg

        raw_files = self.get_repo_files(repo_path)
        if not raw_files:
            return False, None, "No supported source code files found in repository."

        activity_data = self.calculate_git_activity_scores(repo_path, raw_files)
        file_map = {os.path.relpath(f, repo_path).replace("\\", "/"): f for f in raw_files}

        file_info_list: list[FileInfo] = []
        total_lines = 0
        languages_count: dict[str, int] = {}

        for f in raw_files:
            rel_path = os.path.relpath(f, repo_path).replace("\\", "/")
            ext = os.path.splitext(f)[1].lower()
            lang = LANGUAGE_MAP.get(ext, "other")
            languages_count[lang] = languages_count.get(lang, 0) + 1

            # Line & Size counts
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

        # Entry points detection
        entry_points = self.detect_entry_points(file_info_list)
        
        # Build dependency graph
        graph_data = self.extract_dependency_graph(repo_path, file_info_list)

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
