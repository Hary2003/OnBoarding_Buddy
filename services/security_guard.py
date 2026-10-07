import os
import re
from typing import Tuple, Optional, Set, List

import posixpath

# Security limits for ingestion and file access to prevent resource exhaustion / DoS
MAX_PARSEABLE_FILE_SIZE = 1_048_576       # 1 MB: Skip AST/deep regex parse beyond this size
MAX_VIEWABLE_FILE_SIZE = 3_145_728        # 3 MB: Maximum bytes served to client
MAX_REPO_FILES = 10_000                   # Maximum number of indexed files per repo
MAX_DIFF_SIZE = 2_097_152                 # 2 MB: Maximum git diff size analyzed
MAX_LINE_COUNT_SCAN_BYTES = 2_097_152     # 2 MB: Max bytes scanned for line count estimation

# Disallowed Windows device names
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

# Dangerous Git schemes/prefixes that must never be executed or cloned
DANGEROUS_GIT_SCHEMES = ("ext::", "fd::", "file://", "ssh://-", "git+ssh://-", "rsync:")


def is_safe_repo_path(repo_root: str, candidate_path: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates that candidate_path strictly resides within the repository boundary (repo_root).
    Resolves symlinks to ensure they do not point outside the repository directory.

    Returns:
        (is_safe, canonical_target_path, error_message)
    """
    if not candidate_path or not str(candidate_path).strip():
        return False, "", "Empty path provided."

    if not repo_root or not str(repo_root).strip():
        return False, "", "Repository root is not specified."

    candidate_str = str(candidate_path).strip()
    root_str = str(repo_root).strip()

    # 1. Null byte injection check
    if "\x00" in candidate_str or "\x00" in root_str:
        return False, "", "Path contains invalid null byte characters."

    # 2. Check for reserved system device names (Windows)
    base_stem = os.path.basename(candidate_str.replace("\\", "/")).split(".")[0].upper()
    if base_stem in WINDOWS_RESERVED_NAMES:
        return False, "", f"Access to reserved system device '{base_stem}' is forbidden."

    # 3. Cross-platform check: foreign Windows drive letters on non-Windows platforms
    if os.name != "nt" and re.match(r"^[a-zA-Z]:", candidate_str):
        return False, candidate_str, "Path traversal attempt: foreign drive path outside repository boundary."

    # 4. Cross-platform relative traversal check (normalizing backslashes to slashes)
    norm_posix = posixpath.normpath(candidate_str.replace("\\", "/"))
    if norm_posix == ".." or norm_posix.startswith("../"):
        return False, candidate_str, "Path traversal attempt: relative path escapes repository boundary."

    try:
        canonical_root = os.path.realpath(os.path.abspath(root_str))

        if os.path.isabs(candidate_str) or candidate_str.startswith("/") or (os.name == "nt" and re.match(r"^[a-zA-Z]:[/\\]", candidate_str)):
            target = candidate_str
        else:
            target = os.path.join(canonical_root, candidate_str)

        canonical_target = os.path.realpath(os.path.abspath(target))

        # Check drive matching on Windows
        root_drive, _ = os.path.splitdrive(canonical_root)
        target_drive, _ = os.path.splitdrive(canonical_target)
        if root_drive.lower() != target_drive.lower():
            return False, canonical_target, "Path traversal attempt: target is on a different drive."

        # Verify commonpath confinement
        common = os.path.commonpath([canonical_root, canonical_target])
        if os.path.realpath(common) != canonical_root:
            return False, canonical_target, "Path traversal attempt: target resides outside repository boundary."

        return True, canonical_target, None

    except ValueError as e:
        # Occurs on Windows if paths are on different drives
        return False, "", f"Path validation error: {str(e)}"
    except Exception as e:
        return False, "", f"Path resolution error: {str(e)}"


def is_safe_git_target(target: str) -> Tuple[bool, Optional[str]]:
    """
    Validates a Git repository target (URL or local path) to prevent CLI flag injection
    or dangerous protocol exploitation (e.g. ext::).

    Returns:
        (is_safe, error_message)
    """
    if not target or not target.strip():
        return False, "Target repository path or URL is empty."

    cleaned = target.strip()

    # 1. CLI flag injection guard (starts with - or --)
    if cleaned.startswith("-"):
        return False, "Security violation: repository target cannot start with a hyphen or command-line flag."

    # 2. Dangerous protocols and schemes guard
    lower = cleaned.lower()
    for scheme in DANGEROUS_GIT_SCHEMES:
        if lower.startswith(scheme):
            return False, f"Security violation: dangerous protocol '{scheme}' is forbidden."

    # 3. Control characters and shell metacharacters
    if any(c in cleaned for c in ["\r", "\n", "\0", ";", "|", "`", "$"]):
        return False, "Security violation: repository target contains disallowed control characters."

    return True, None


def is_symlink_escaping_boundary(repo_root: str, file_path: str) -> bool:
    """
    Returns True if file_path is a symlink that resolves to a location outside repo_root.
    """
    try:
        canonical_root = os.path.realpath(os.path.abspath(repo_root))
        canonical_target = os.path.realpath(os.path.abspath(file_path))

        root_drive, _ = os.path.splitdrive(canonical_root)
        target_drive, _ = os.path.splitdrive(canonical_target)
        if root_drive.lower() != target_drive.lower():
            return True

        return os.path.commonpath([canonical_root, canonical_target]) != canonical_root
    except Exception:
        return True


def count_lines_safe(file_path: str, max_bytes: int = MAX_LINE_COUNT_SCAN_BYTES) -> int:
    """
    Counts lines in a file in chunks without reading the entire file into memory at once.
    """
    line_cnt = 0
    try:
        with open(file_path, "rb") as f:
            bytes_read = 0
            while chunk := f.read(65536):
                bytes_read += len(chunk)
                line_cnt += chunk.count(b"\n")
                if bytes_read >= max_bytes:
                    break
    except Exception:
        pass
    return line_cnt


def wrap_untrusted_context(context_text: str, tag_name: str = "untrusted_repository_evidence") -> str:
    """
    Wraps untrusted third-party repository data inside defensive boundary XML tags.
    """
    return f"<{tag_name}>\n{context_text}\n</{tag_name}>"
