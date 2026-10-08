import os
import re
import ast
from typing import List, Dict, Set, Tuple, Optional, Any
from models.repository_index import RepositoryIndex, FileInfo, ContributionOpportunity, AuditReport

SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|password|passwd|client[_-]?secret)\s*=\s*[\'"]([a-zA-Z0-9_\-]{16,})[\'"]', "Potential Hardcoded Secret"),
    (r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}', "Exposed Bearer Authentication Token")
]

UNSAFE_PATTERNS = [
    (r'\beval\s*\(', "Unsafe Dynamic Code Evaluation (eval)", "Critical"),
    (r'\bexec\s*\(', "Unsafe Dynamic Execution (exec)", "Critical"),
    (r'shell\s*=\s*True', "Subprocess Shell Execution Vulnerability", "High"),
    (r'verify\s*=\s*False', "Disabled SSL Certificate Verification", "High"),
    (r'pickle\.loads\s*\(', "Unsafe Object Deserialization (pickle.loads)", "High"),
    (r'yaml\.load\s*\([^,)]*\)', "Unsafe PyYAML Load (use SafeLoader)", "Medium")
]

FIXTURE_DIR_NAMES = {
    "tests", "test", "__tests__", "fixtures", "fixture", "samples",
    "sample", "demos", "demo", "examples", "example", "docs", "documentation"
}

def is_fixture_or_test_path(path: str) -> bool:
    """Identifies test files, fixtures, demo files, documentation, and external packages."""
    if not path:
        return False
    norm = path.replace("\\", "/").lower()
    parts = norm.split("/")
    
    # Check if any parent folder is a test/fixture/doc/sample directory
    if any(p in FIXTURE_DIR_NAMES for p in parts[:-1]):
        return True
        
    fname = parts[-1]
    if fname.startswith("test_") or fname.endswith("_test.py") or ".test." in fname or ".spec." in fname:
        return True
        
    if any(v in norm for v in ["/venv/", "/.venv/", "/node_modules/", "/dist/", "/build/"]):
        return True
        
    return False

def mask_secret(value: str) -> str:
    """Masks sensitive credentials to prevent credential leakage in findings and logs."""
    if not value:
        return "****"
    val = value.strip().strip("'\"")
    if len(val) <= 8:
        return "****"
    return f"{val[:4]}...****...{val[-4:]}"

def is_obvious_placeholder(val: str) -> bool:
    """Checks if a string literal is an obvious non-credential placeholder."""
    v = val.lower().strip()
    placeholders = [
        "your_", "dummy", "fake", "placeholder", "changeme", "change_me",
        "todo", "<", ">", "{", "}", "localhost", "none", "null",
        "false", "true", "mock", "my_secret"
    ]
    return any(p in v for p in placeholders)

def lex_js_ts(content: str) -> str:
    """
    Lexical state machine for JavaScript/TypeScript:
    Replaces comments, string literals, and template strings outside ${...}
    with spaces while preserving line breaks, line indices, and column offsets.
    Expressions inside template strings (${...}) are preserved as executable code.
    """
    res = []
    i = 0
    n = len(content)
    stack = ['CODE']
    expr_braces = []

    while i < n:
        ch = content[i]
        nxt = content[i + 1] if i + 1 < n else ''
        state = stack[-1]

        if state == 'CODE':
            if ch == '/' and nxt == '/':
                stack.append('LINE_COMMENT')
                res.append('  ')
                i += 2
                continue
            elif ch == '/' and nxt == '*':
                stack.append('BLOCK_COMMENT')
                res.append('  ')
                i += 2
                continue
            elif ch == '\'':
                stack.append('SINGLE_QUOTE')
                res.append(' ')
                i += 1
                continue
            elif ch == '"':
                stack.append('DOUBLE_QUOTE')
                res.append(' ')
                i += 1
                continue
            elif ch == '`':
                stack.append('TEMPLATE')
                res.append(' ')
                i += 1
                continue
            elif ch == '{' and expr_braces:
                expr_braces[-1] += 1
                res.append(ch)
                i += 1
                continue
            elif ch == '}' and expr_braces:
                if expr_braces[-1] > 0:
                    expr_braces[-1] -= 1
                    res.append(ch)
                else:
                    expr_braces.pop()
                    stack.pop()
                    res.append(' ')
                i += 1
                continue
            else:
                res.append(ch)
                i += 1
                continue

        elif state == 'LINE_COMMENT':
            if ch == '\n':
                stack.pop()
                res.append('\n')
            else:
                res.append(' ')
            i += 1
            continue

        elif state == 'BLOCK_COMMENT':
            if ch == '*' and nxt == '/':
                stack.pop()
                res.append('  ')
                i += 2
            elif ch == '\n':
                res.append('\n')
                i += 1
            else:
                res.append(' ')
                i += 1
            continue

        elif state == 'SINGLE_QUOTE':
            if ch == '\\':
                res.append('  ' if nxt != '\n' else ' \n')
                i += 2
            elif ch == '\'':
                stack.pop()
                res.append(' ')
                i += 1
            elif ch == '\n':
                res.append('\n')
                i += 1
            else:
                res.append(' ')
                i += 1
            continue

        elif state == 'DOUBLE_QUOTE':
            if ch == '\\':
                res.append('  ' if nxt != '\n' else ' \n')
                i += 2
            elif ch == '"':
                stack.pop()
                res.append(' ')
                i += 1
            elif ch == '\n':
                res.append('\n')
                i += 1
            else:
                res.append(' ')
                i += 1
            continue

        elif state == 'TEMPLATE':
            if ch == '\\':
                res.append('  ' if nxt != '\n' else ' \n')
                i += 2
            elif ch == '$' and nxt == '{':
                stack.append('CODE')
                expr_braces.append(0)
                res.append('  ')
                i += 2
            elif ch == '`':
                stack.pop()
                res.append(' ')
                i += 1
            elif ch == '\n':
                res.append('\n')
                i += 1
            else:
                res.append(' ')
                i += 1
            continue

    return ''.join(res)

class SecurityScanner:
    def scan(self, repo_index: RepositoryIndex) -> List[ContributionOpportunity]:
        opportunities: List[ContributionOpportunity] = []
        opp_counter = 1

        for file_info in repo_index.files:
            if file_info.language not in ["python", "javascript", "typescript"]:
                continue

            # Separate production audit targets from test suites and demo/fixture directories
            if is_fixture_or_test_path(file_info.relative_path):
                continue

            try:
                with open(file_info.full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if file_info.language == "python":
                    file_opps, opp_counter = self._scan_python(file_info, content, opp_counter)
                elif file_info.language in ["javascript", "typescript"]:
                    file_opps, opp_counter = self._scan_js_ts(file_info, content, opp_counter)
                else:
                    file_opps, opp_counter = self._scan_fallback(file_info, content, opp_counter)

                opportunities.extend(file_opps)

            except Exception:
                pass

        return opportunities

    def _scan_python(self, file_info: FileInfo, content: str, opp_counter: int) -> Tuple[List[ContributionOpportunity], int]:
        opportunities: List[ContributionOpportunity] = []
        try:
            tree = ast.parse(content, filename=file_info.file_name)
        except SyntaxError:
            return self._scan_fallback(file_info, content, opp_counter)

        # 1. Unsafe calls and dangerous configurations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                lineno = getattr(node, "lineno", 1)

                # eval()
                if isinstance(node.func, ast.Name) and node.func.id == "eval":
                    opp_id = f"sec_{opp_counter}"
                    opp_counter += 1
                    title = f"🛡️ Unsafe Dynamic Code Evaluation (eval) in `{file_info.file_name}`"
                    reason = "Direct invocation of eval() was detected in executable application code. Dynamic code evaluation allows arbitrary code execution if input contains untrusted data."
                    remediation = f"Replace unsafe eval() call on line {lineno} of `{file_info.relative_path}` with safe AST parsing (ast.literal_eval) or structured JSON parsing (json.loads)."
                    opportunities.append(ContributionOpportunity(
                        opportunity_id=opp_id,
                        title=title,
                        category="security",
                        severity="Critical",
                        confidence="High",
                        line_number=lineno,
                        detection_reason=reason,
                        target_files=[file_info.relative_path],
                        description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: High). Reason: {reason}",
                        remediation_plan=remediation,
                        suggested_issue_title=f"Security: Refactor eval() in {file_info.file_name}",
                        suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: Critical | Confidence: High\n\nReason: {reason}\n\nRecommendation: {remediation}"
                    ))

                # exec()
                elif isinstance(node.func, ast.Name) and node.func.id == "exec":
                    opp_id = f"sec_{opp_counter}"
                    opp_counter += 1
                    title = f"🛡️ Unsafe Dynamic Execution (exec) in `{file_info.file_name}`"
                    reason = "Direct invocation of exec() was detected in executable application code. Dynamic Python code execution poses severe remote code execution risks."
                    remediation = f"Refactor code on line {lineno} of `{file_info.relative_path}` to avoid dynamic Python string execution; use direct function calls or lookup tables."
                    opportunities.append(ContributionOpportunity(
                        opportunity_id=opp_id,
                        title=title,
                        category="security",
                        severity="Critical",
                        confidence="High",
                        line_number=lineno,
                        detection_reason=reason,
                        target_files=[file_info.relative_path],
                        description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: High). Reason: {reason}",
                        remediation_plan=remediation,
                        suggested_issue_title=f"Security: Refactor exec() in {file_info.file_name}",
                        suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: Critical | Confidence: High\n\nReason: {reason}\n\nRecommendation: {remediation}"
                    ))

                # Subprocess shell=True
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        opp_id = f"sec_{opp_counter}"
                        opp_counter += 1
                        title = f"🛡️ Subprocess Shell Execution Vulnerability in `{file_info.file_name}`"
                        reason = "Subprocess invocation with shell=True was detected in executable application code. This enables shell command injection if command strings incorporate untrusted inputs."
                        remediation = f"Set shell=False on line {lineno} of `{file_info.relative_path}` and pass command arguments as a list of strings."
                        opportunities.append(ContributionOpportunity(
                            opportunity_id=opp_id,
                            title=title,
                            category="security",
                            severity="High",
                            confidence="High",
                            line_number=lineno,
                            detection_reason=reason,
                            target_files=[file_info.relative_path],
                            description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: High). Reason: {reason}",
                            remediation_plan=remediation,
                            suggested_issue_title=f"Security: Remove shell=True in {file_info.file_name}",
                            suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: High | Confidence: High\n\nReason: {reason}\n\nRecommendation: {remediation}"
                        ))
                    elif kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                        opp_id = f"sec_{opp_counter}"
                        opp_counter += 1
                        title = f"🛡️ Disabled SSL Certificate Verification in `{file_info.file_name}`"
                        reason = "HTTP request with disabled SSL certificate verification (verify=False) was detected. This leaves connections vulnerable to man-in-the-middle (MITM) attacks."
                        remediation = f"Enable certificate verification (verify=True or omit parameter) on line {lineno} of `{file_info.relative_path}`."
                        opportunities.append(ContributionOpportunity(
                            opportunity_id=opp_id,
                            title=title,
                            category="security",
                            severity="High",
                            confidence="High",
                            line_number=lineno,
                            detection_reason=reason,
                            target_files=[file_info.relative_path],
                            description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: High). Reason: {reason}",
                            remediation_plan=remediation,
                            suggested_issue_title=f"Security: Enable SSL verification in {file_info.file_name}",
                            suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: High | Confidence: High\n\nReason: {reason}\n\nRecommendation: {remediation}"
                        ))

                # pickle.loads
                if isinstance(node.func, ast.Attribute) and node.func.attr == "loads":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                        opp_id = f"sec_{opp_counter}"
                        opp_counter += 1
                        title = f"🛡️ Unsafe Object Deserialization (pickle.loads) in `{file_info.file_name}`"
                        reason = "Deserializing untrusted data with pickle.loads() can execute arbitrary Python bytecode."
                        remediation = f"Replace pickle serialization on line {lineno} of `{file_info.relative_path}` with safe formats such as JSON or Protocol Buffers."
                        opportunities.append(ContributionOpportunity(
                            opportunity_id=opp_id,
                            title=title,
                            category="security",
                            severity="High",
                            confidence="High",
                            line_number=lineno,
                            detection_reason=reason,
                            target_files=[file_info.relative_path],
                            description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: High). Reason: {reason}",
                            remediation_plan=remediation,
                            suggested_issue_title=f"Security: Replace pickle.loads in {file_info.file_name}",
                            suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: High | Confidence: High\n\nReason: {reason}\n\nRecommendation: {remediation}"
                        ))

                # yaml.load
                if isinstance(node.func, ast.Attribute) and node.func.attr == "load":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id in ("yaml", "pyyaml"):
                        has_safe = any(
                            kw.arg == "Loader" and "safe" in getattr(kw.value, "id", getattr(kw.value, "attr", "")).lower()
                            for kw in node.keywords
                        )
                        if not has_safe:
                            opp_id = f"sec_{opp_counter}"
                            opp_counter += 1
                            title = f"🛡️ Unsafe PyYAML Load in `{file_info.file_name}`"
                            reason = "Loading YAML with yaml.load() without SafeLoader can instantiate arbitrary Python objects."
                            remediation = f"Use yaml.safe_load() or specify Loader=yaml.SafeLoader on line {lineno} of `{file_info.relative_path}`."
                            opportunities.append(ContributionOpportunity(
                                opportunity_id=opp_id,
                                title=title,
                                category="security",
                                severity="Medium",
                                confidence="Medium",
                                line_number=lineno,
                                detection_reason=reason,
                                target_files=[file_info.relative_path],
                                description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: Medium). Reason: {reason}",
                                remediation_plan=remediation,
                                suggested_issue_title=f"Security: Use SafeLoader with PyYAML in {file_info.file_name}",
                                suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: Medium | Confidence: Medium\n\nReason: {reason}\n\nRecommendation: {remediation}"
                            ))

            # 2. Hardcoded secret variable assignments
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                lineno = getattr(node, "lineno", 1)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    target_name = ""
                    if isinstance(target, ast.Name):
                        target_name = target.id
                    elif isinstance(target, ast.Attribute):
                        target_name = target.attr

                    if not target_name:
                        continue

                    # Check if variable name indicates credential/secret storage
                    if re.search(r'(?i)^(.*_)?(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|password|passwd|client[_-]?secret|private[_-]?key)(_.*)?$', target_name):
                        val_node = node.value
                        # If assigned via function call (e.g. os.getenv, config.get), it's NOT a hardcoded secret
                        if isinstance(val_node, ast.Call):
                            continue

                        if isinstance(val_node, ast.Constant) and isinstance(val_node.value, str):
                            val_str = val_node.value
                            if is_obvious_placeholder(val_str) or len(val_str) < 8 or " " in val_str or "\n" in val_str:
                                continue

                            is_known_format = bool(re.search(r'AIza[0-9A-Za-z-_]{35}', val_str) or len(val_str) >= 16)
                            confidence = "Medium" if is_known_format else "Low"
                            severity = "High" if is_known_format else "Medium"
                            masked = mask_secret(val_str)

                            opp_id = f"sec_{opp_counter}"
                            opp_counter += 1
                            title = f"🔒 Potential Hardcoded Secret in `{file_info.file_name}`"
                            reason = f"A credential-shaped literal ({masked}) was detected in application source code assigned to variable '{target_name}'. Review whether this is a real credential."
                            remediation = f"Extract secret assigned on line {lineno} of `{file_info.relative_path}` into an environment variable (`.env` / `os.getenv`) or secrets manager and rotate if exposed."
                            opportunities.append(ContributionOpportunity(
                                opportunity_id=opp_id,
                                title=title,
                                category="security",
                                severity=severity,
                                confidence=confidence,
                                line_number=lineno,
                                detection_reason=reason,
                                target_files=[file_info.relative_path],
                                description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: {confidence}). Reason: {reason}",
                                remediation_plan=remediation,
                                suggested_issue_title=f"Security: Remediate Potential Hardcoded Secret in {file_info.file_name}",
                                suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: {severity} | Confidence: {confidence}\n\nReason: {reason}\n\nRecommendation: {remediation}"
                            ))

        return opportunities, opp_counter

    def _scan_js_ts(self, file_info: FileInfo, content: str, opp_counter: int) -> Tuple[List[ContributionOpportunity], int]:
        opportunities: List[ContributionOpportunity] = []
        sanitized = lex_js_ts(content)

        # 1. Unsafe functions in executable code
        unsafe_patterns_js = [
            (
                r'\beval\s*\(',
                "Unsafe Dynamic Code Evaluation (eval)",
                "Critical",
                "Direct invocation of eval() was detected in executable JavaScript code. Dynamic code evaluation allows arbitrary code execution if input contains untrusted data.",
                f"Replace unsafe eval() call in `{file_info.relative_path}` with safe JSON parsing or alternative logic."
            ),
            (
                r'\bexec\s*\(',
                "Unsafe Process Execution (exec)",
                "High",
                "Process execution function exec() was detected in executable JavaScript code.",
                f"Use execFile or spawn with argument arrays and shell disabled in `{file_info.relative_path}`."
            ),
            (
                r'shell\s*:\s*true',
                "Subprocess Shell Execution Vulnerability",
                "High",
                "Subprocess execution with shell: true was detected in executable JavaScript code.",
                f"Disable shell option and pass arguments as an array in `{file_info.relative_path}`."
            ),
            (
                r'rejectUnauthorized\s*:\s*false',
                "Disabled SSL Certificate Verification",
                "High",
                "Disabled TLS certificate verification (rejectUnauthorized: false) was detected.",
                f"Enable TLS verification to prevent man-in-the-middle attacks in `{file_info.relative_path}`."
            )
        ]

        for pattern, label, severity, reason, remediation in unsafe_patterns_js:
            for m in re.finditer(pattern, sanitized):
                lineno = content[:m.start()].count("\n") + 1
                opp_id = f"sec_{opp_counter}"
                opp_counter += 1
                title = f"🛡️ {label} in `{file_info.file_name}`"
                opportunities.append(ContributionOpportunity(
                    opportunity_id=opp_id,
                    title=title,
                    category="security",
                    severity=severity,
                    confidence="High",
                    line_number=lineno,
                    detection_reason=reason,
                    target_files=[file_info.relative_path],
                    description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: High). Reason: {reason}",
                    remediation_plan=remediation,
                    suggested_issue_title=f"Security: Refactor {label} in {file_info.file_name}",
                    suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: {severity} | Confidence: High\n\nReason: {reason}\n\nRecommendation: {remediation}"
                ))

        # 2. Hardcoded secrets in JS/TS variable assignments
        secret_js_pattern = re.compile(
            r'(?i)(?:const|let|var|\b)?\s*([a-zA-Z0-9_$]*(?:api[_-]?key|secret|token|password|passwd)[a-zA-Z0-9_$]*)\s*=\s*[\'"]([a-zA-Z0-9_\-]{16,})[\'"]'
        )
        for m in secret_js_pattern.finditer(content):
            # Verify LHS identifier is in executable code (not inside template string or comment)
            lhs_start = m.start(1)
            lhs_name = m.group(1)
            if sanitized[lhs_start:lhs_start + len(lhs_name)].strip() != lhs_name:
                continue

            val_str = m.group(2)
            if is_obvious_placeholder(val_str):
                continue

            lineno = content[:m.start()].count("\n") + 1
            masked = mask_secret(val_str)
            opp_id = f"sec_{opp_counter}"
            opp_counter += 1
            title = f"🔒 Potential Hardcoded Secret in `{file_info.file_name}`"
            reason = f"A credential-shaped literal ({masked}) was detected in application source code assigned to variable '{lhs_name}'. Review whether this is a real credential."
            remediation = f"Extract secret parameter on line {lineno} of `{file_info.relative_path}` into an environment variable (process.env) or secret manager."
            opportunities.append(ContributionOpportunity(
                opportunity_id=opp_id,
                title=title,
                category="security",
                severity="High",
                confidence="Medium",
                line_number=lineno,
                detection_reason=reason,
                target_files=[file_info.relative_path],
                description=f"Line {lineno} of `{file_info.relative_path}` (Confidence: Medium). Reason: {reason}",
                remediation_plan=remediation,
                suggested_issue_title=f"Security: Remediate Potential Hardcoded Secret in {file_info.file_name}",
                suggested_issue_desc=f"File: {file_info.relative_path}:{lineno}\nSeverity: High | Confidence: Medium\n\nReason: {reason}\n\nRecommendation: {remediation}"
            ))

        return opportunities, opp_counter

    def _scan_fallback(self, file_info: FileInfo, content: str, opp_counter: int) -> Tuple[List[ContributionOpportunity], int]:
        opportunities: List[ContributionOpportunity] = []
        lines = content.splitlines()

        for line_idx, line in enumerate(lines, start=1):
            trimmed = line.strip()
            # Skip comments or lines with placeholder indicators
            if trimmed.startswith("#") or trimmed.startswith("//") or trimmed.startswith("/*") or trimmed.startswith("*"):
                continue

            # Hardcoded secret check
            for pattern, label in SECRET_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    # Ignore os.getenv, os.environ, process.env
                    if "os.getenv" in line or "os.environ" in line or "process.env" in line:
                        continue
                    secret_val = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group(0)
                    if is_obvious_placeholder(secret_val):
                        continue

                    masked = mask_secret(secret_val)
                    opp_id = f"sec_{opp_counter}"
                    opp_counter += 1
                    title = f"🔒 Potential Hardcoded Secret in `{file_info.file_name}`"
                    reason = f"A credential-shaped literal ({masked}) was detected in application source code on line {line_idx}. Review whether this is a real credential."
                    remediation = f"Extract secret parameter on line {line_idx} of `{file_info.relative_path}` into an environment variable or secrets manager."
                    opportunities.append(ContributionOpportunity(
                        opportunity_id=opp_id,
                        title=title,
                        category="security",
                        severity="High",
                        confidence="Medium",
                        line_number=line_idx,
                        detection_reason=reason,
                        target_files=[file_info.relative_path],
                        description=f"Line {line_idx} of `{file_info.relative_path}` (Confidence: Medium). Reason: {reason}",
                        remediation_plan=remediation,
                        suggested_issue_title=f"Security: Remediate Potential Hardcoded Secret in {file_info.file_name}",
                        suggested_issue_desc=f"File: {file_info.relative_path}:{line_idx}\nSeverity: High | Confidence: Medium\n\nReason: {reason}\n\nRecommendation: {remediation}"
                    ))
                    break

            # Unsafe patterns check
            for pattern, label, severity in UNSAFE_PATTERNS:
                if re.search(pattern, line):
                    # Check if line appears to be a pure string assignment or comment
                    if re.match(r'^[a-zA-Z0-9_]+\s*=\s*[\'"].*[\'"]\s*$', trimmed):
                        continue

                    opp_id = f"sec_{opp_counter}"
                    opp_counter += 1
                    title = f"🛡️ {label} in `{file_info.file_name}`"
                    reason = f"Identified `{label}` on line {line_idx} in `{file_info.relative_path}`. Unsafe patterns can cause arbitrary execution or security bypass."
                    remediation = f"Refactor call on line {line_idx} of `{file_info.relative_path}` to use safe alternatives."
                    opportunities.append(ContributionOpportunity(
                        opportunity_id=opp_id,
                        title=title,
                        category="security",
                        severity=severity,
                        confidence="High",
                        line_number=line_idx,
                        detection_reason=reason,
                        target_files=[file_info.relative_path],
                        description=f"Line {line_idx} of `{file_info.relative_path}` (Confidence: High). Reason: {reason}",
                        remediation_plan=remediation,
                        suggested_issue_title=f"Security: Refactor {label} in {file_info.file_name}",
                        suggested_issue_desc=f"File: {file_info.relative_path}:{line_idx}\nSeverity: {severity} | Confidence: High\n\nReason: {reason}\n\nRecommendation: {remediation}"
                    ))

        return opportunities, opp_counter

class ArchitectureScanner:
    def scan(self, repo_index: RepositoryIndex) -> List[ContributionOpportunity]:
        opportunities: List[ContributionOpportunity] = []
        opp_counter = 1

        # 1. Circular dependencies refactoring opportunities
        for cycle in repo_index.circular_cycles:
            opp_id = f"arch_{opp_counter}"
            opp_counter += 1
            path_str = " ➔ ".join(cycle.path)
            title = f"🔄 Break Circular Dependency Loop ({cycle.cycle_length} hops)"
            desc = f"Circular import detected across modules: `{path_str}`. Circular dependencies create tight coupling, unpredictable import orders, and memory leaks."
            remediation = f"Decouple shared types/interfaces from `{cycle.path[0]}` and `{cycle.path[1]}` into a standalone utility or interface module."

            opportunities.append(ContributionOpportunity(
                opportunity_id=opp_id,
                title=title,
                category="architecture_refactor",
                severity="High",
                target_files=cycle.path[:3],
                description=desc,
                remediation_plan=remediation,
                suggested_issue_title=f"Refactor: Resolve circular dependency loop in {cycle.path[0]}",
                suggested_issue_desc=f"Refactor circular import loop between {path_str} by extracting shared abstractions."
            ))

        # 2. God module refactoring opportunities (large core modules)
        for f in repo_index.files:
            if f.module_category in ["core", "entry_point"] and f.line_count > 350:
                opp_id = f"arch_{opp_counter}"
                opp_counter += 1
                title = f"📦 Modularize Core Component `{f.file_name}` ({f.line_count} lines)"
                desc = f"Core module `{f.relative_path}` has high centrality (imported by {f.in_degree} modules) and a large codebase size ({f.line_count} lines)."
                remediation = f"Refactor `{f.relative_path}` by splitting monolithic functions and handlers into decoupled sub-modules."

                opportunities.append(ContributionOpportunity(
                    opportunity_id=opp_id,
                    title=title,
                    category="architecture_refactor",
                    severity="Medium",
                    target_files=[f.relative_path],
                    description=desc,
                    remediation_plan=remediation,
                    suggested_issue_title=f"Refactor: Modularize core module {f.file_name}",
                    suggested_issue_desc=f"Core module {f.relative_path} has reached {f.line_count} lines and high degree centrality. Refactor into modular sub-services."
                ))

        return opportunities

class TestCoverageScanner:
    def scan(self, repo_index: RepositoryIndex) -> List[ContributionOpportunity]:
        opportunities: List[ContributionOpportunity] = []
        opp_counter = 1

        all_test_files = [
            f.relative_path.lower() for f in repo_index.files
            if f.relative_path.startswith("tests/") or "test_" in f.file_name.lower() or "_test" in f.file_name.lower()
        ]

        for f in repo_index.files:
            if f.module_category in ["core", "entry_point"] and not f.relative_path.startswith("tests/"):
                base_name = os.path.splitext(f.file_name)[0].lower()
                
                # Check if matching test file exists
                has_test = any(base_name in tf or tf.replace("test_", "") in base_name for tf in all_test_files)
                if not has_test:
                    opp_id = f"test_{opp_counter}"
                    opp_counter += 1
                    title = f"🧪 Add Unit Test Suite for Core Module `{f.file_name}`"
                    desc = f"Core module `{f.relative_path}` (In-Degree: {f.in_degree}) lacks dedicated automated unit test coverage in `tests/`."
                    remediation = f"Create `tests/test_{base_name}.py` to cover core exported symbols ({', '.join([s.name for s in f.symbols[:3]])})."

                    opportunities.append(ContributionOpportunity(
                        opportunity_id=opp_id,
                        title=title,
                        category="test_coverage",
                        severity="High" if f.module_category == "core" else "Medium",
                        target_files=[f.relative_path],
                        description=desc,
                        remediation_plan=remediation,
                        suggested_issue_title=f"Test: Add unit test suite for {f.file_name}",
                        suggested_issue_desc=f"Create comprehensive unit test coverage for core module {f.relative_path} under tests/."
                    ))

        return opportunities

class AuditService:
    def __init__(self):
        self.security_scanner = SecurityScanner()
        self.arch_scanner = ArchitectureScanner()
        self.test_scanner = TestCoverageScanner()

    def run_audit(self, repo_index: Optional[RepositoryIndex]) -> AuditReport:
        """Executes full automated codebase audit to identify open source contribution opportunities."""
        if not repo_index or not repo_index.files:
            return AuditReport(
                repo_name="None",
                total_opportunities=0,
                opportunities=[],
                summary_narrative="⚠️ **No active repository loaded.** Analyze a repository first to run audit scanner."
            )

        opportunities: List[ContributionOpportunity] = []

        # Run individual scanners
        opportunities.extend(self.security_scanner.scan(repo_index))
        opportunities.extend(self.arch_scanner.scan(repo_index))
        opportunities.extend(self.test_scanner.scan(repo_index))

        # Sort opportunities by severity order
        severity_order = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
        opportunities.sort(key=lambda o: (severity_order.get(o.severity, 5), o.category))

        critical_count = sum(1 for o in opportunities if o.severity == "Critical")
        high_count = sum(1 for o in opportunities if o.severity == "High")
        medium_count = sum(1 for o in opportunities if o.severity == "Medium")
        low_count = sum(1 for o in opportunities if o.severity == "Low")

        # Generate summary report narrative
        narrative_lines = []
        narrative_lines.append(f"# 🔍 Open Source Contribution Audit Report — `{repo_index.repo_name}`\n")
        narrative_lines.append(f"Analyzed **{repo_index.total_files} files** ({repo_index.total_lines} lines of code). Identified **{len(opportunities)} actionable contribution opportunities**.\n")
        narrative_lines.append(f"- 🔴 **Critical**: {critical_count}")
        narrative_lines.append(f"- 🟠 **High**: {high_count}")
        narrative_lines.append(f"- 🟡 **Medium**: {medium_count}")
        narrative_lines.append(f"- 🔵 **Low**: {low_count}\n")

        narrative_lines.append("## 🚀 Recommended Pull Request Contributions")
        for idx, opp in enumerate(opportunities[:6], start=1):
            files_str = f" (`{', '.join(opp.target_files[:2])}`)" if opp.target_files else ""
            narrative_lines.append(f"{idx}. **[{opp.severity.upper()}]** {opp.title}{files_str}")
            narrative_lines.append(f"   _{opp.description}_")

        summary_narrative = "\n".join(narrative_lines)

        return AuditReport(
            repo_name=repo_index.repo_name,
            total_opportunities=len(opportunities),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            opportunities=opportunities,
            summary_narrative=summary_narrative
        )

audit_service = AuditService()
