import os
import ast
import re
import tempfile
import shutil
import stat
import time
from datetime import datetime
from git import Repo, GitCommandError

IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".idea", ".vscode"}
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".cs", ".html", ".css", ".json", ".md", ".yml", ".yaml"
}

class RepoService:
    def clone_or_use_repo(self, target: str) -> tuple[bool, str, str]:
        """Clones a remote git URL or validates a local directory path."""
        target = target.strip()
        if not target:
            return False, "", "Target repository path or URL is empty."
        
        # Check if local path exists
        if os.path.exists(target) and os.path.isdir(target):
            return True, target, ""
        
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
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    code_files.append(os.path.join(root, file))
        return sorted(code_files)

    def parse_file_symbols(self, file_path: str) -> list[dict]:
        """Extracts functions/classes from Python AST or multi-language regex."""
        ext = os.path.splitext(file_path)[1].lower()
        symbols = []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if ext == ".py":
                try:
                    node = ast.parse(content)
                    for n in ast.walk(node):
                        if isinstance(n, ast.FunctionDef):
                            docstring = ast.get_docstring(n) or ""
                            args = [a.arg for a in n.args.args]
                            symbols.append({
                                "name": n.name,
                                "type": "function",
                                "args": args,
                                "docstring": docstring,
                                "line": n.lineno
                            })
                        elif isinstance(n, ast.ClassDef):
                            symbols.append({
                                "name": n.name,
                                "type": "class",
                                "args": [],
                                "docstring": ast.get_docstring(n) or "",
                                "line": n.lineno
                            })
                    symbols.sort(key=lambda x: x["line"])
                    return symbols
                except SyntaxError:
                    pass  # Fallback to regex if parsing fails

            # Multi-language Regex Fallback (JS, TS, Go, Java, Rust, etc.)
            func_patterns = [
                r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', # Python fallback
                r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', # JS/TS function
                r'const\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:async\s*)?\(', # Arrow function
                r'func\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', # Go func
                r'fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', # Rust fn
                r'(?:public|private|protected|static|\s)+\s+[\w<>]+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(' # Java/C# method
            ]
            
            for line_idx, line in enumerate(content.splitlines(), start=1):
                for pattern in func_patterns:
                    match = re.search(pattern, line)
                    if match:
                        symbols.append({
                            "name": match.group(1),
                            "type": "function",
                            "args": [],
                            "docstring": "",
                            "line": line_idx
                        })

        except Exception:
            pass

        return symbols

    def rank_files_by_activity(self, repo_path: str, files: list[str]) -> list[dict]:
        """Ranks files by Git commit activity and modification dates."""
        results = []
        try:
            repo = Repo(repo_path)
            for f in files:
                rel_path = os.path.relpath(f, repo_path)
                try:
                    commits = list(repo.iter_commits(paths=rel_path, max_count=1))
                    if commits:
                        dt = datetime.fromtimestamp(commits[0].committed_date)
                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                    else:
                        date_str = "Static File"
                except Exception:
                    date_str = "Recent"

                results.append({
                    "full_path": f,
                    "rel_path": rel_path.replace("\\", "/"),
                    "last_modified": date_str
                })
        except Exception:
            # If not a git repo, use file system modified date
            for f in files:
                rel_path = os.path.relpath(f, repo_path)
                dt = datetime.fromtimestamp(os.path.getmtime(f))
                results.append({
                    "full_path": f,
                    "rel_path": rel_path.replace("\\", "/"),
                    "last_modified": dt.strftime("%Y-%m-%d %H:%M")
                })

        return results

    def extract_dependency_graph(self, repo_path: str, files: list[str]) -> dict:
        """Extracts import relationships between files for visual dependency graph."""
        nodes = []
        edges = []
        file_map = {}

        # Register nodes
        for idx, f in enumerate(files):
            rel_path = os.path.relpath(f, repo_path).replace("\\", "/")
            file_map[rel_path] = str(idx)
            ext = os.path.splitext(f)[1].lower()
            
            # Group styling based on language
            group = "other"
            if ext == ".py": group = "python"
            elif ext in [".js", ".ts", ".jsx", ".tsx"]: group = "javascript"
            elif ext == ".go": group = "go"
            elif ext in [".html", ".css"]: group = "web"

            nodes.append({
                "id": str(idx),
                "label": os.path.basename(f),
                "title": rel_path,
                "group": group
            })

        # Find import connections
        edge_set = set()
        for f in files:
            source_rel = os.path.relpath(f, repo_path).replace("\\", "/")
            source_id = file_map.get(source_rel)
            if not source_id:
                continue

            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as file_obj:
                    content = file_obj.read()
                
                # Check for mentions of other file basenames/modules
                for target_rel, target_id in file_map.items():
                    if source_id == target_id:
                        continue
                    target_name = os.path.splitext(os.path.basename(target_rel))[0]
                    if len(target_name) > 2 and re.search(r'\b' + re.escape(target_name) + r'\b', content):
                        edge_pair = (source_id, target_id)
                        if edge_pair not in edge_set:
                            edge_set.add(edge_pair)
                            edges.append({"from": source_id, "to": target_id})
            except Exception:
                pass

        return {"nodes": nodes, "edges": edges}

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
