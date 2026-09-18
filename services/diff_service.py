import os
import re
from typing import Dict, List, Optional, Tuple, Any
from models.repository_index import FileChange, DiffHunk, CodeChange, RepositoryIndex


class GitDiffParser:
    """Parses unified git diffs and extracts structured file changes, line numbers, and symbols."""

    HUNK_HEADER_REGEX = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$")
    DIFF_GIT_REGEX = re.compile(r"^diff\s+--git\s+(?:a/)?(.*?)\s+(?:b/)?(.*?)$")

    def parse(self, diff_text: str, repo_index: Optional[RepositoryIndex] = None) -> List[FileChange]:
        if not diff_text or not diff_text.strip():
            return []

        raw_chunks = self._split_file_chunks(diff_text)
        file_changes: List[FileChange] = []

        for chunk in raw_chunks:
            file_change = self._parse_single_file_chunk(chunk, repo_index)
            if file_change:
                file_changes.append(file_change)

        return file_changes

    def _split_file_chunks(self, diff_text: str) -> List[str]:
        lines = diff_text.splitlines(keepends=True)
        chunks: List[str] = []
        current_chunk: List[str] = []

        for line in lines:
            if line.startswith("diff --git ") and current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = [line]
            elif (line.startswith("--- ") and not current_chunk) or (line.startswith("--- a/") and not any("diff --git" in c for c in current_chunk)):
                if current_chunk and any(c.startswith("--- ") for c in current_chunk):
                    chunks.append("".join(current_chunk))
                    current_chunk = [line]
                else:
                    current_chunk.append(line)
            else:
                current_chunk.append(line)

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    def _parse_single_file_chunk(self, chunk: str, repo_index: Optional[RepositoryIndex] = None) -> Optional[FileChange]:
        lines = chunk.splitlines()
        if not lines:
            return None

        file_path = ""
        old_path: Optional[str] = None
        status = "modified"
        hunks: List[DiffHunk] = []
        current_hunk: Optional[DiffHunk] = None
        current_hunk_lines: List[str] = []
        modified_symbols: List[str] = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Match diff --git a/file b/file
            diff_match = self.DIFF_GIT_REGEX.match(line)
            if diff_match:
                old_candidate = diff_match.group(1).strip()
                new_candidate = diff_match.group(2).strip()
                if old_candidate != "/dev/null":
                    old_path = old_candidate
                if new_candidate != "/dev/null":
                    file_path = new_candidate
                i += 1
                continue

            if line.startswith("new file mode"):
                status = "added"
                i += 1
                continue
            elif line.startswith("deleted file mode"):
                status = "deleted"
                i += 1
                continue
            elif line.startswith("rename from "):
                old_path = line.replace("rename from ", "").strip()
                status = "renamed"
                i += 1
                continue
            elif line.startswith("rename to "):
                file_path = line.replace("rename to ", "").strip()
                status = "renamed"
                i += 1
                continue
            elif line.startswith("--- "):
                path_part = line[4:].strip()
                if path_part.startswith("a/"):
                    path_part = path_part[2:]
                if path_part != "/dev/null" and not old_path:
                    old_path = path_part
                i += 1
                continue
            elif line.startswith("+++ "):
                path_part = line[4:].strip()
                if path_part.startswith("b/"):
                    path_part = path_part[2:]
                if path_part != "/dev/null":
                    file_path = path_part
                i += 1
                continue

            # Hunk header @@ -start,count +start,count @@ context
            hunk_match = self.HUNK_HEADER_REGEX.match(line)
            if hunk_match:
                if current_hunk:
                    current_hunk.lines = current_hunk_lines
                    hunks.append(current_hunk)
                    current_hunk_lines = []

                old_start = int(hunk_match.group(1))
                old_lines = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3))
                new_lines = int(hunk_match.group(4)) if hunk_match.group(4) else 1
                header_ctx = hunk_match.group(5).strip()

                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_lines=old_lines,
                    new_start=new_start,
                    new_lines=new_lines,
                    header=header_ctx,
                    lines=[]
                )

                sym_from_header = self._extract_symbol_from_header(header_ctx)
                if sym_from_header and sym_from_header not in modified_symbols:
                    modified_symbols.append(sym_from_header)

                i += 1
                continue

            if current_hunk:
                current_hunk_lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    added_code = line[1:].strip()
                    sym_name = self._detect_symbol_definition(added_code)
                    if sym_name and sym_name not in modified_symbols:
                        modified_symbols.append(sym_name)

            i += 1

        if current_hunk:
            current_hunk.lines = current_hunk_lines
            hunks.append(current_hunk)

        if not file_path:
            file_path = old_path or "unknown_file"

        # Calculate additions and deletions
        additions = 0
        deletions = 0
        for h in hunks:
            for hl in h.lines:
                if hl.startswith("+") and not hl.startswith("+++"):
                    additions += 1
                elif hl.startswith("-") and not hl.startswith("---"):
                    deletions += 1

        if status == "modified":
            if additions > 0 and deletions == 0 and (old_path == "/dev/null" or not old_path):
                status = "added"
            elif deletions > 0 and additions == 0 and file_path == "/dev/null":
                status = "deleted"
                file_path = old_path or file_path

        # Correlate modified line numbers with repository AST symbols if repository index is provided
        if repo_index and file_path:
            norm_path = file_path.replace("\\", "/").lstrip("/")
            matched_file = next((f for f in repo_index.files if f.relative_path == norm_path), None)
            if matched_file:
                for h in hunks:
                    h_start = h.new_start
                    h_end = h.new_start + h.new_lines
                    for sym in matched_file.symbols:
                        sym_end = sym.end_line or (sym.line_number + 15)
                        if not (h_end < sym.line_number or h_start > sym_end):
                            if sym.name not in modified_symbols:
                                modified_symbols.append(sym.name)

        return FileChange(
            file_path=file_path.replace("\\", "/").lstrip("/"),
            old_path=old_path.replace("\\", "/").lstrip("/") if old_path else None,
            status=status,
            additions=additions,
            deletions=deletions,
            modified_symbols=modified_symbols,
            hunks=hunks,
            patch=chunk.strip()
        )

    @staticmethod
    def _extract_symbol_from_header(header: str) -> Optional[str]:
        if not header:
            return None
        match = re.search(r"(?:def|class|function|func)\s+([a-zA-Z0-9_]+)", header)
        if match:
            return match.group(1)
        match = re.search(r"([a-zA-Z0-9_]+)\s*\(", header)
        if match:
            cand = match.group(1)
            if cand not in {"if", "for", "while", "with", "switch", "catch"}:
                return cand
        return None

    @staticmethod
    def _detect_symbol_definition(code_line: str) -> Optional[str]:
        match = re.search(r"^\s*(?:def|class|async\s+def|function|func)\s+([a-zA-Z0-9_]+)", code_line)
        if match:
            return match.group(1)
        return None

    def extract_added_lines(self, file_change: FileChange) -> List[CodeChange]:
        changes: List[CodeChange] = []
        for hunk in file_change.hunks:
            current_new_line = hunk.new_start
            current_old_line = hunk.old_start
            for line in hunk.lines:
                if line.startswith("+") and not line.startswith("+++"):
                    changes.append(CodeChange(
                        file_path=file_change.file_path,
                        change_type="added",
                        old_line_number=None,
                        new_line_number=current_new_line,
                        content=line[1:]
                    ))
                    current_new_line += 1
                elif line.startswith("-") and not line.startswith("---"):
                    changes.append(CodeChange(
                        file_path=file_change.file_path,
                        change_type="removed",
                        old_line_number=current_old_line,
                        new_line_number=None,
                        content=line[1:]
                    ))
                    current_old_line += 1
                else:
                    current_new_line += 1
                    current_old_line += 1
        return changes


class ChangeClassifier:
    """Classifies PR changes into feature, bug_fix, refactor, test_update, configuration_change, or documentation_update."""

    DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
    CONFIG_NAMES = {
        "package.json", "pyproject.toml", "setup.py", "requirements.txt",
        "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".env", ".env.example", "config.py", "settings.py"
    }

    def classify(self, file_changes: List[FileChange], title: str = "", description: str = "") -> str:
        if not file_changes:
            return "feature"

        paths = [fc.file_path.lower() for fc in file_changes]
        text_context = f"{title} {description}".lower()

        # 1. Configuration change
        if all(os.path.basename(p) in self.CONFIG_NAMES or p.endswith(".yml") or p.endswith(".yaml") or p.endswith(".json") or p.endswith(".toml") or "config" in p for p in paths):
            return "configuration_change"

        # 2. Test update
        if all("test" in p or "spec" in p for p in paths):
            return "test_update"

        # 3. Documentation update
        if all(any(p.endswith(ext) for ext in self.DOC_EXTENSIONS) or "doc" in p or "docs/" in p for p in paths):
            return "documentation_update"

        # 4. Bug fix indicators
        fix_keywords = {"fix", "bug", "patch", "resolve", "hotfix", "issue", "error", "crash", "flaky"}
        if any(kw in text_context for kw in fix_keywords):
            return "bug_fix"

        has_fix_signals = False
        total_additions = sum(fc.additions for fc in file_changes)
        total_deletions = sum(fc.deletions for fc in file_changes)

        for fc in file_changes:
            for hunk in fc.hunks:
                for line in hunk.lines:
                    if line.startswith("+"):
                        lowered = line.lower()
                        if any(term in lowered for term in ["try:", "catch", "except", "if not", "fix", "err is not nil", "none", "null"]):
                            has_fix_signals = True

        if has_fix_signals and (total_additions < 60 or total_deletions > total_additions * 0.5):
            if any(term in text_context for term in ["fix", "resolve", "patch", "handle", "check"]):
                return "bug_fix"

        # 5. Refactor indicators
        refactor_keywords = {"refactor", "cleanup", "reorganize", "restructure", "move", "rename", "format"}
        if any(kw in text_context for kw in refactor_keywords):
            return "refactor"

        any_renames = any(fc.status == "renamed" for fc in file_changes)
        if any_renames and total_additions < 100:
            return "refactor"

        all_symbols = [sym for fc in file_changes for sym in fc.modified_symbols]
        if total_additions > 0 and total_deletions > 0:
            ratio = min(total_additions, total_deletions) / max(total_additions, total_deletions)
            if ratio > 0.7 and not any(fc.status == "added" for fc in file_changes) and len(all_symbols) <= 2:
                return "refactor"

        # 6. Default to feature
        return "feature"


diff_parser = GitDiffParser()
change_classifier = ChangeClassifier()
