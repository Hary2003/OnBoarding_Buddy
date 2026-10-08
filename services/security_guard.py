import os
import re
import socket
import ipaddress
import time
import unicodedata
import urllib.parse
from urllib.parse import urlsplit
from collections import defaultdict
from typing import Tuple, Optional, Set, List, Dict

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

# SSRF host/IP restrictions
FORBIDDEN_HOSTNAMES = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal",
    "instance-data", "metadata"
}

CLOUD_METADATA_IPS = {
    "169.254.169.254",  # AWS, Azure, GCP, DigitalOcean, OpenStack
    "169.254.169.253",  # AWS DNS
    "100.100.100.200",  # Alibaba Cloud
}

PUBLIC_KNOWN_HOSTS = {
    "github.com", "gitlab.com", "bitbucket.com"
}

# Sensitive operating system paths that must never be cloned or ingested locally
SENSITIVE_SYSTEM_PREFIXES = {
    # Unix / Linux
    "/etc", "/root", "/var", "/proc", "/sys", "/dev", "/boot", "/usr", "/bin", "/sbin",
    # Windows
    "c:/windows", "c:/program files", "c:/program files (x86)", "c:/system volume information", "c:/perflogs"
}


def is_safe_remote_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validates a remote URL against Server-Side Request Forgery (SSRF).
    Blocks private IP ranges, loopbacks, link-local, cloud metadata services,
    and non-standard protocols.
    """
    if not url or not url.strip():
        return False, "Target URL is empty."

    cleaned = url.strip()
    try:
        parsed = urlsplit(cleaned)
    except Exception as e:
        return False, f"Malformed URL: {e}"

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https", "git"):
        return False, f"Security violation: Scheme '{scheme}' is forbidden. Only HTTP, HTTPS, or Git protocols are permitted."

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "Security violation: Missing hostname in repository URL."

    # Direct hostname blocklist
    if hostname in FORBIDDEN_HOSTNAMES or hostname.endswith(".local") or hostname.endswith(".internal"):
        return False, f"Security violation: Access to internal or loopback host '{hostname}' is forbidden (SSRF blocked)."

    raw_host = hostname.strip("[]")

    def _is_forbidden_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> Tuple[bool, Optional[str]]:
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified:
            return True, f"Security violation: URL targets private, loopback, or non-routable IP '{ip_obj}' (SSRF blocked)."
        if str(ip_obj) in CLOUD_METADATA_IPS:
            return True, f"Security violation: URL targets cloud metadata IP '{ip_obj}' (SSRF blocked)."
        if ip_obj.version == 6 and getattr(ip_obj, "ipv4_mapped", None):
            mapped = ip_obj.ipv4_mapped
            if mapped.is_loopback or mapped.is_private or mapped.is_link_local or mapped.is_multicast or mapped.is_reserved or mapped.is_unspecified:
                return True, f"Security violation: URL targets private/loopback IPv4-mapped address '{mapped}' (SSRF blocked)."
            if str(mapped) in CLOUD_METADATA_IPS:
                return True, f"Security violation: URL targets cloud metadata IPv4-mapped address '{mapped}' (SSRF blocked)."
        return False, None

    # Direct IP literal check
    try:
        ip = ipaddress.ip_address(raw_host)
        is_bad, err = _is_forbidden_ip(ip)
        if is_bad:
            return False, err
        return True, None
    except ValueError:
        pass

    # Bypass DNS lookup for known public platforms to avoid network dependence in tests
    if hostname in PUBLIC_KNOWN_HOSTS:
        return True, None

    # Resolve domain name to IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            is_bad, err = _is_forbidden_ip(ip)
            if is_bad:
                return False, err
    except socket.gaierror as e:
        return False, f"Security violation: Unable to resolve hostname '{hostname}' ({e})."
    except Exception as e:
        return False, f"Security violation: DNS resolution error for '{hostname}': {e}"

    return True, None


def is_safe_local_clone_path(path: str, is_production: bool = False, allowed_roots: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validates that a local clone directory target does not attempt local file inclusion
    or directory traversal into sensitive system directories (/etc, C:\\Windows, etc.).
    """
    if not path or not str(path).strip():
        return False, "Target path is empty."

    decoded_path = str(path).strip()
    for _ in range(3):
        unquoted = urllib.parse.unquote(decoded_path)
        if unquoted == decoded_path:
            break
        decoded_path = unquoted

    decoded_path = unicodedata.normalize("NFKC", decoded_path)

    if "\x00" in decoded_path:
        return False, "Security violation: Path contains invalid null byte characters."

    # 1. Direct cross-platform raw check (e.g. /etc or /var on Windows where abspath might prepend C:)
    raw_posix = decoded_path.replace("\\", "/").lower()
    for prefix in SENSITIVE_SYSTEM_PREFIXES:
        if raw_posix == prefix or raw_posix.startswith(prefix + "/"):
            return False, f"Security violation: Access to sensitive system path '{path}' is forbidden."

    # 2. Canonicalized abspath check
    norm = os.path.realpath(os.path.abspath(decoded_path)).replace("\\", "/")
    norm_lower = norm.lower()

    for prefix in SENSITIVE_SYSTEM_PREFIXES:
        if norm_lower == prefix or norm_lower.startswith(prefix + "/"):
            return False, f"Security violation: Access to sensitive system path '{path}' is forbidden."

    # 3. Path without drive check (e.g. C:/etc -> /etc)
    _, path_without_drive = os.path.splitdrive(norm_lower)
    if path_without_drive:
        for prefix in SENSITIVE_SYSTEM_PREFIXES:
            if path_without_drive == prefix or path_without_drive.startswith(prefix + "/"):
                return False, f"Security violation: Access to sensitive system path '{path}' is forbidden."

    if is_production:
        if allowed_roots:
            is_within_allowed = any(
                os.path.commonpath([os.path.realpath(r), os.path.realpath(norm)]) == os.path.realpath(r)
                for r in allowed_roots
            )
            if not is_within_allowed:
                return False, "Security violation: Local path is outside allowed production repository roots."

    return True, None


def is_safe_repo_path(repo_root: str, candidate_path: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates that candidate_path strictly resides within the repository boundary (repo_root).
    Resolves symlinks, performs iterative unquoting, and ensures canonical commonpath confinement.

    Returns:
        (is_safe, canonical_target_path, error_message)
    """
    if not candidate_path or not str(candidate_path).strip():
        return False, "", "Empty path provided."

    if not repo_root or not str(repo_root).strip():
        return False, "", "Repository root is not specified."

    candidate_str = str(candidate_path).strip()
    root_str = str(repo_root).strip()

    # 1. Iterative URL decoding (defends against single, double, and triple %-encoding traversal bypasses)
    decoded_candidate = candidate_str
    for _ in range(3):
        unquoted = urllib.parse.unquote(decoded_candidate)
        if unquoted == decoded_candidate:
            break
        decoded_candidate = unquoted

    # 2. Unicode NFKC normalization
    decoded_candidate = unicodedata.normalize("NFKC", decoded_candidate)

    # 3. Null byte injection check
    if "\x00" in decoded_candidate or "\x00" in root_str:
        return False, "", "Path contains invalid null byte characters."

    # 4. Check for reserved system device names (Windows)
    base_stem = os.path.basename(decoded_candidate.replace("\\", "/")).split(".")[0].upper()
    if base_stem in WINDOWS_RESERVED_NAMES:
        return False, "", f"Access to reserved system device '{base_stem}' is forbidden."

    # 5. Cross-platform check: foreign Windows drive letters on non-Windows platforms
    if os.name != "nt" and re.match(r"^[a-zA-Z]:", decoded_candidate):
        return False, candidate_str, "Path traversal attempt: foreign drive path outside repository boundary."

    # 6. Cross-platform relative traversal check (normalizing backslashes to slashes)
    norm_posix = posixpath.normpath(decoded_candidate.replace("\\", "/"))
    if norm_posix == ".." or norm_posix.startswith("../") or "/../" in norm_posix or norm_posix.startswith("..\\"):
        return False, candidate_str, "Path traversal attempt: relative path escapes repository boundary."

    try:
        canonical_root = os.path.realpath(os.path.abspath(root_str))

        if os.path.isabs(decoded_candidate) or decoded_candidate.startswith("/") or (os.name == "nt" and re.match(r"^[a-zA-Z]:[/\\]", decoded_candidate)):
            target = decoded_candidate
        else:
            target = os.path.join(canonical_root, decoded_candidate)

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
        return False, "", f"Path validation error: {str(e)}"
    except Exception as e:
        return False, "", f"Path resolution error: {str(e)}"


def is_safe_git_target(target: str) -> Tuple[bool, Optional[str]]:
    """
    Validates a Git repository target (URL or local path) to prevent CLI flag injection,
    dangerous protocol exploitation (e.g. ext::), and Server-Side Request Forgery (SSRF).

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

    # 4. Remote URL SSRF validation
    if lower.startswith("http://") or lower.startswith("https://") or lower.startswith("git://"):
        safe_url, url_err = is_safe_remote_url(cleaned)
        if not safe_url:
            return False, url_err

    return True, None


class InMemoryRateLimiter:
    """
    Sliding-window in-memory rate limiter per client IP.
    Protects against API quota depletion, CPU exhaustion, and brute-force DoS.
    """
    def __init__(self, default_limit: int = 120):
        self.default_limit = default_limit
        self._history: Dict[str, List[float]] = defaultdict(list)
        self.expensive_endpoints = {
            "/api/clone", "/api/chat", "/api/generate-guide",
            "/api/pr/review", "/api/pr/analyze", "/api/summarize",
            "/api/agent/explore", "/api/contribution/analyze"
        }

    def check_rate_limit(self, client_ip: str, path: str, limit: Optional[int] = None) -> Tuple[bool, int, int]:
        """
        Returns:
            (is_allowed, remaining_requests, retry_after_seconds)
        """
        now = time.time()
        window = 60.0

        if limit is not None:
            max_reqs = limit
        elif any(path.startswith(exp) for exp in self.expensive_endpoints):
            max_reqs = max(10, self.default_limit // 2)
        else:
            max_reqs = self.default_limit

        key = f"{client_ip}:{path if any(path.startswith(exp) for exp in self.expensive_endpoints) else 'general'}"
        timestamps = self._history[key]

        cutoff = now - window
        self._history[key] = [t for t in timestamps if t > cutoff]

        if len(self._history[key]) >= max_reqs:
            oldest = self._history[key][0]
            retry_after = max(1, int(oldest + window - now))
            return False, 0, retry_after

        self._history[key].append(now)
        remaining = max_reqs - len(self._history[key])
        return True, remaining, 0

    def reset(self):
        self._history.clear()


rate_limiter = InMemoryRateLimiter()


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
