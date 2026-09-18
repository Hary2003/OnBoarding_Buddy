import os
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timezone

from config import settings
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, SourceAttribution,
    FileChange, CodeChange, PRSummary, ArchitectureImpact,
    TestRecommendation, RiskAssessment, ReviewComment,
    PullRequestAnalysis, PRReviewResponse
)
from services.diff_service import diff_parser, change_classifier
from services.groq_service import groq_service


class ArchitectureReviewer:
    """Evaluates architectural layer alignment, coupling risks, and circular dependencies in a PR."""

    def analyze(self, file_changes: List[FileChange], repo_index: Optional[RepositoryIndex]) -> ArchitectureImpact:
        if not repo_index or not file_changes:
            return ArchitectureImpact()

        file_map: Dict[str, FileInfo] = {f.relative_path: f for f in repo_index.files}
        affected_modules: List[str] = []
        affected_entry_points: List[str] = []
        affected_services: List[str] = []
        affected_apis: List[str] = []
        upstream_impact: List[str] = []
        downstream_impact: List[str] = []
        architectural_layers: Set[str] = set()
        layer_violations: List[str] = []
        circular_risks: List[str] = []
        god_module_risks: List[str] = []
        coupling_score = 0.0

        for fc in file_changes:
            path = fc.file_path
            affected_modules.append(path)
            layer = self._classify_layer(path)
            architectural_layers.add(layer)

            info = file_map.get(path)
            if info:
                if info.is_entry_point or path in repo_index.entry_points:
                    affected_entry_points.append(path)
                if layer == "service":
                    affected_services.append(path)
                elif layer == "api":
                    affected_apis.append(path)

                # Downstream dependencies
                for dep in info.dependencies:
                    target = dep.resolved_path or dep.target_path
                    if dep.is_internal and target not in downstream_impact and target != path:
                        downstream_impact.append(target)

                # Upstream callers (files importing this changed file)
                for other in repo_index.files:
                    if other.relative_path == path:
                        continue
                    if any((d.resolved_path or d.target_path) == path for d in other.dependencies if d.is_internal):
                        if other.relative_path not in upstream_impact:
                            upstream_impact.append(other.relative_path)
                            if other.is_entry_point and other.relative_path not in affected_entry_points:
                                affected_entry_points.append(other.relative_path)

                # Check if changed file is in circular dependencies
                if info.is_circular:
                    circular_risks.append(f"Modified file `{path}` is part of an existing circular dependency chain.")

                # God module check: additions > 200 or high in-degree + large additions
                if fc.additions > 200 or (info.in_degree > 4 and fc.additions > 80):
                    god_module_risks.append(f"`{path}` grew significantly (+{fc.additions} lines, in-degree {info.in_degree}), risking becoming an oversized god module.")
            else:
                # Newly added file
                if layer == "api":
                    affected_apis.append(path)
                elif layer == "service":
                    affected_services.append(path)
                if fc.additions > 300:
                    god_module_risks.append(f"Newly added module `{path}` is very large (+{fc.additions} lines). Consider modularizing.")

            # Layer violation detection in added lines
            for hunk in fc.hunks:
                for line in hunk.lines:
                    if line.startswith("+") and not line.startswith("+++"):
                        clean_line = line[1:].strip()
                        violation = self._detect_layer_violation(layer, clean_line)
                        if violation and violation not in layer_violations:
                            layer_violations.append(f"In `{path}`: {violation}")

        # Compute heuristic coupling increase score
        total_touched = len(set(upstream_impact + downstream_impact))
        coupling_score = round(min(10.0, len(file_changes) * 0.8 + total_touched * 0.5 + len(layer_violations) * 2.0), 2)

        return ArchitectureImpact(
            affected_entry_points=sorted(list(set(affected_entry_points))),
            affected_modules=sorted(list(set(affected_modules))),
            affected_services=sorted(list(set(affected_services))),
            affected_apis=sorted(list(set(affected_apis))),
            upstream_impact=sorted(list(set(upstream_impact)))[:15],
            downstream_impact=sorted(list(set(downstream_impact)))[:15],
            architectural_layers=sorted(list(architectural_layers)),
            layer_violations=layer_violations,
            circular_dependency_risks=circular_risks,
            god_module_risks=god_module_risks,
            coupling_increase_score=coupling_score
        )

    @staticmethod
    def _classify_layer(file_path: str) -> str:
        p = file_path.lower()
        if p.startswith("tests/") or "test_" in p or "_test" in p:
            return "test"
        if "server.py" in p or "app.py" in p or "routes" in p or "api" in p or "controllers" in p:
            return "api"
        if "services/" in p or "service" in p:
            return "service"
        if "models/" in p or "model" in p or "schemas" in p:
            return "model"
        if "config" in p or ".env" in p or "settings" in p:
            return "config"
        if "lib/" in p or "utils/" in p or "helpers/" in p:
            return "utility"
        return "standard"

    @staticmethod
    def _detect_layer_violation(source_layer: str, added_line: str) -> Optional[str]:
        # Models should not import services or APIs
        if source_layer == "model":
            if re.search(r"^\s*(?:from|import)\s+(?:services|server|api|controllers)\b", added_line):
                return f"Model layer file imports high-level service/API: `{added_line.strip()}`"
        # Utilities should not import business services or APIs
        if source_layer == "utility":
            if re.search(r"^\s*(?:from|import)\s+(?:services|server|api|controllers)\b", added_line):
                return f"Utility layer file imports higher-level service/API: `{added_line.strip()}`"
        return None


class TestImpactAnalyzer:
    """Detects affected test suites, missing tests, and recommends test scenarios and edge cases."""

    def analyze(self, file_changes: List[FileChange], repo_index: Optional[RepositoryIndex]) -> TestRecommendation:
        related_tests: List[str] = []
        missing_tests: List[str] = []
        outdated_tests: List[str] = []
        recommended_files: List[str] = []
        recommended_scenarios: List[str] = []
        recommended_edge_cases: List[str] = []
        recommended_integrations: List[str] = []

        changed_test_files = [fc.file_path for fc in file_changes if "test" in fc.file_path.lower() or "spec" in fc.file_path.lower()]
        changed_code_files = [fc for fc in file_changes if fc.file_path not in changed_test_files and not any(fc.file_path.lower().endswith(ext) for ext in [".md", ".rst", ".txt", ".json", ".yml", ".yaml"])]

        if repo_index:
            for fc in changed_code_files:
                matched_tests_for_file = self._find_tests_for_file(fc.file_path, repo_index)
                for t in matched_tests_for_file:
                    if t not in related_tests:
                        related_tests.append(t)
                    if t not in recommended_files:
                        recommended_files.append(t)

                # If code was modified or added, but no matching test file was updated in this PR
                if fc.additions > 5 or fc.deletions > 5 or fc.status == "added":
                    updated_in_pr = any(t in changed_test_files for t in matched_tests_for_file)
                    if not updated_in_pr:
                        missing_tests.append(f"`{fc.file_path}` was modified (+{fc.additions}/-{fc.deletions}) but corresponding test coverage was not updated in this PR.")

                # If symbols were modified, generate specific scenarios
                for sym in fc.modified_symbols:
                    recommended_scenarios.append(f"Verify return values and success paths for `{sym}` in `{fc.file_path}`.")
                    recommended_edge_cases.append(f"Test `{sym}` with null, empty, or malformed parameters.")
                    recommended_edge_cases.append(f"Verify error handling and exception paths when `{sym}` encounters unexpected input.")

        # If there are changed code files but NO tests were modified in the entire PR
        if changed_code_files and not changed_test_files:
            missing_tests.insert(0, "PR touches functional code across files without adding or updating any test cases.")

        # If API or entry points are touched, recommend integration tests
        api_changes = [fc.file_path for fc in changed_code_files if "server" in fc.file_path.lower() or "api" in fc.file_path.lower() or "route" in fc.file_path.lower()]
        if api_changes:
            for api_f in api_changes:
                recommended_integrations.append(f"Run end-to-end request/response integration tests touching `{api_f}`.")
                recommended_scenarios.append(f"Verify HTTP status codes (200, 400, 404, 500) and payload serialization for endpoints in `{api_f}`.")

        # Add general boundary edge cases if symbols changed
        if any(fc.modified_symbols for fc in changed_code_files):
            recommended_edge_cases.append("Verify boundary values, zero values, and empty list/dictionary payloads.")

        return TestRecommendation(
            related_tests=sorted(list(set(related_tests))),
            missing_tests=missing_tests,
            outdated_tests=outdated_tests,
            recommended_test_files=sorted(list(set(recommended_files))),
            recommended_scenarios=recommended_scenarios[:8],
            recommended_edge_cases=recommended_edge_cases[:8],
            recommended_integration_tests=recommended_integrations[:6]
        )

    @staticmethod
    def _find_tests_for_file(file_path: str, repo_index: RepositoryIndex) -> List[str]:
        target_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        matched: List[str] = []
        for f in repo_index.files:
            p_lower = f.relative_path.lower()
            if not ("test" in p_lower or "spec" in p_lower):
                continue
            test_base = os.path.splitext(f.file_name)[0].lower()
            imports_target = any((d.resolved_path or d.target_path) == file_path for d in f.dependencies)
            name_matches = target_name and (target_name in test_base or test_base.replace("test_", "") in target_name)
            if imports_target or name_matches:
                matched.append(f.relative_path)
        return matched


class DiffSecurityScanner:
    """Scans added diff code lines for security vulnerabilities and dangerous anti-patterns."""

    SECURITY_RULES: List[Tuple[str, str, str, str]] = [
        (
            r'(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|password|passwd)\s*=\s*[\'"][a-zA-Z0-9_\-]{16,}[\'"]',
            "Hardcoded Secret / API Credential",
            "Critical",
            "Extract secret into environment variables (`.env` or `config.py`) instead of hardcoding."
        ),
        (
            r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}',
            "Exposed Bearer Authentication Token",
            "Critical",
            "Revoke token immediately and inject credentials via environment variables."
        ),
        (
            r'\beval\s*\(',
            "Unsafe Dynamic Code Evaluation (eval)",
            "Critical",
            "Remove eval() call; replace with safe JSON/literal parsing (`ast.literal_eval`)."
        ),
        (
            r'\bexec\s*\(',
            "Unsafe Execution of Dynamic Code (exec)",
            "Critical",
            "Refactor code to avoid dynamic Python string execution."
        ),
        (
            r'shell\s*=\s*True',
            "Subprocess Shell Execution Vulnerability",
            "High",
            "Set shell=False and pass arguments as a list to avoid command injection."
        ),
        (
            r'os\.system\s*\(',
            "Insecure os.system Command Execution",
            "High",
            "Use subprocess.run with arguments array and shell=False instead of os.system."
        ),
        (
            r'(?i)(select|insert|update|delete)\s+.*?\bfrom\b.*?(?:%s|format\(|f[\'"].*?\{)',
            "Potential SQL Injection Pattern",
            "High",
            "Use parameterized SQL queries or ORM query builders rather than string interpolation."
        ),
        (
            r'(?i)dangerouslysetinnerhtml|\.innerhtml\s*=',
            "Potential Cross-Site Scripting (XSS)",
            "High",
            "Sanitize input before rendering HTML or use textContent/safe framework templates."
        ),
        (
            r'(?i)verify\s*=\s*False',
            "Disabled SSL Certificate Verification",
            "High",
            "Enable SSL verification (verify=True) to protect against Man-in-the-Middle attacks."
        ),
        (
            r'pickle\.loads\s*\(',
            "Unsafe Object Deserialization (pickle.loads)",
            "High",
            "Replace pickle with safe serialization formats like JSON, MessagePack, or Protobuf."
        ),
        (
            r'yaml\.load\s*\([^,)]*\)',
            "Unsafe PyYAML Load",
            "Medium",
            "Use yaml.safe_load() or specify Loader=yaml.SafeLoader."
        ),
        (
            r'(?i)requests\.(?:get|post)\s*\(\s*(?:url|target_url|user_url)\b',
            "Potential Server-Side Request Forgery (SSRF)",
            "Medium",
            "Validate and allowlist outbound URL hosts before making HTTP requests."
        ),
    ]

    def scan(self, file_changes: List[FileChange]) -> List[RiskAssessment]:
        risks: List[RiskAssessment] = []
        risk_counter = 1

        for fc in file_changes:
            # Skip test files from strict secret/mock checking if marked as mock/test
            is_test_file = "test" in fc.file_path.lower() or "spec" in fc.file_path.lower()

            for hunk in fc.hunks:
                current_line = hunk.new_start
                for line in hunk.lines:
                    if line.startswith("+") and not line.startswith("+++"):
                        code_content = line[1:]
                        trimmed = code_content.strip()

                        # Skip comments
                        if trimmed.startswith("#") or trimmed.startswith("//"):
                            current_line += 1
                            continue

                        for pattern, title, severity, remediation in self.SECURITY_RULES:
                            if is_test_file and severity in {"Medium", "Low"}:
                                continue
                            # If test file, skip mock credentials
                            if is_test_file and any(mock in trimmed.lower() for mock in ["mock", "dummy", "fake", "test", "example"]):
                                continue

                            if re.search(pattern, trimmed):
                                risk_id = f"sec_pr_{risk_counter}"
                                risk_counter += 1
                                risks.append(RiskAssessment(
                                    risk_id=risk_id,
                                    title=title,
                                    category="security",
                                    severity=severity,
                                    file_path=fc.file_path,
                                    line_number=current_line,
                                    evidence=trimmed[:160],
                                    remediation=remediation
                                ))
                                break

                        current_line += 1
                    elif not line.startswith("-"):
                        current_line += 1

        return risks


class ReviewCommentGenerator:
    """Generates actionable, evidence-backed review comments for code reviews."""

    def generate(
        self,
        file_changes: List[FileChange],
        risks: List[RiskAssessment],
        arch_impact: ArchitectureImpact,
        test_rec: TestRecommendation
    ) -> List[ReviewComment]:
        comments: List[ReviewComment] = []
        comment_idx = 1

        # 1. Generate comments for security risks
        for risk in risks:
            comment_id = f"comment_{comment_idx}"
            comment_idx += 1
            severity_map = {
                "Critical": "critical",
                "High": "warning",
                "Medium": "warning",
                "Low": "suggestion"
            }
            comments.append(ReviewComment(
                comment_id=comment_id,
                file_path=risk.file_path,
                line_number=risk.line_number,
                symbol_name=None,
                severity=severity_map.get(risk.severity, "warning"),
                title=risk.title,
                body=f"Detected security risk: {risk.title}. This could introduce vulnerabilities when deployed.",
                evidence=risk.evidence,
                recommendation=risk.remediation
            ))

        # 2. Generate comments for architectural layer violations
        for violation in arch_impact.layer_violations:
            comment_id = f"comment_{comment_idx}"
            comment_idx += 1
            # Extract target file if formatted as "In `path`: ..."
            match = re.search(r"In `(.*?)`:\s*(.*)", violation)
            target_f = match.group(1) if match else (file_changes[0].file_path if file_changes else "unknown")
            body_text = match.group(2) if match else violation

            comments.append(ReviewComment(
                comment_id=comment_id,
                file_path=target_f,
                line_number=None,
                symbol_name=None,
                severity="critical",
                title="Architectural Layer Violation",
                body=body_text,
                evidence="",
                recommendation="Refactor dependency injection or move logic to appropriate architectural layer."
            ))

        # 3. Generate comments for missing test coverage
        for missing in test_rec.missing_tests[:3]:
            comment_id = f"comment_{comment_idx}"
            comment_idx += 1
            match = re.search(r"`(.*?)`", missing)
            target_f = match.group(1) if match else (file_changes[0].file_path if file_changes else "unknown")
            comments.append(ReviewComment(
                comment_id=comment_id,
                file_path=target_f,
                line_number=None,
                symbol_name=None,
                severity="warning",
                title="Missing Test Coverage",
                body=missing,
                evidence="",
                recommendation="Add unit or integration tests verifying the new behavior and edge cases."
            ))

        # 4. Generate comments for god module / oversized changes
        for god_risk in arch_impact.god_module_risks:
            comment_id = f"comment_{comment_idx}"
            comment_idx += 1
            match = re.search(r"`(.*?)`", god_risk)
            target_f = match.group(1) if match else "unknown"
            comments.append(ReviewComment(
                comment_id=comment_id,
                file_path=target_f,
                line_number=None,
                symbol_name=None,
                severity="suggestion",
                title="Maintainability: High Module Growth",
                body=god_risk,
                evidence="",
                recommendation="Consider breaking this component into smaller, focused single-responsibility helper modules."
            ))

        return comments


class PRSummarizer:
    """Produces two-tier summaries (Executive & Developer) from parsed diffs and architecture impact."""

    def summarize(
        self,
        file_changes: List[FileChange],
        change_type: str,
        risks: List[RiskAssessment],
        arch_impact: ArchitectureImpact,
        test_rec: TestRecommendation,
        title: str = "",
        description: str = ""
    ) -> PRSummary:
        files_count = len(file_changes)
        total_add = sum(fc.additions for fc in file_changes)
        total_del = sum(fc.deletions for fc in file_changes)

        # Determine overall risk level
        severities = {r.severity for r in risks}
        if "Critical" in severities or arch_impact.layer_violations:
            risk_level = "Critical"
        elif "High" in severities:
            risk_level = "High"
        elif "Medium" in severities or test_rec.missing_tests:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Executive Summary
        exec_lines = [
            f"This pull request is classified as a **{change_type.replace('_', ' ').title()}** altering **{files_count} file(s)** with **+{total_add}** line additions and **-{total_del}** deletions."
        ]
        if title:
            exec_lines.append(f"**Intent:** {title}.")
        if arch_impact.affected_entry_points:
            exec_lines.append(f"**Entry Points Impacted:** {', '.join(f'`{ep}`' for ep in arch_impact.affected_entry_points[:3])}.")
        if risks:
            exec_lines.append(f"**Risk Alert:** {len(risks)} risk(s) identified (Risk Level: **{risk_level}**).")
        else:
            exec_lines.append("No critical security or architectural risks were detected.")
        exec_summary = " ".join(exec_lines)

        # Developer Summary
        dev_lines = [
            "### 🛠️ Developer Summary",
            f"- **Change Category:** `{change_type}` | **Overall Risk:** `{risk_level}`",
            f"- **Files Modified:** {files_count} | **Additions:** +{total_add} | **Deletions:** -{total_del}",
        ]

        if file_changes:
            dev_lines.append("\n#### Changed Files & Symbols")
            for fc in file_changes[:8]:
                syms = f" (Symbols: {', '.join(f'`{s}`' for s in fc.modified_symbols[:3])})" if fc.modified_symbols else ""
                dev_lines.append(f"- `{fc.file_path}` [{fc.status}] (+{fc.additions}/-{fc.deletions}){syms}")

        if arch_impact.architectural_layers:
            dev_lines.append(f"\n- **Architectural Layers Touched:** {', '.join(arch_impact.architectural_layers)}")
        if arch_impact.upstream_impact:
            dev_lines.append(f"- **Upstream Dependents Impacted:** {len(arch_impact.upstream_impact)} file(s)")
        if arch_impact.downstream_impact:
            dev_lines.append(f"- **Downstream Dependencies Used:** {len(arch_impact.downstream_impact)} file(s)")

        if test_rec.recommended_test_files:
            dev_lines.append(f"- **Recommended Tests to Run:** {', '.join(f'`{t}`' for t in test_rec.recommended_test_files[:4])}")
        if test_rec.missing_tests:
            dev_lines.append(f"- **⚠️ Missing Test Warnings:** {len(test_rec.missing_tests)} module(s) missing updated tests")

        dev_summary = "\n".join(dev_lines)

        return PRSummary(
            title=title or f"{change_type.replace('_', ' ').capitalize()} PR affecting {files_count} file(s)",
            executive_summary=exec_summary,
            developer_summary=dev_summary,
            change_type=change_type,
            risk_level=risk_level,
            files_changed=files_count,
            lines_added=total_add,
            lines_removed=total_del,
            commit_references=[]
        )


class PRReviewAgent:
    """Evaluates pull requests, produces findings, suggestions, follow-ups, and approval verdicts."""

    def review(self, analysis: PullRequestAnalysis) -> PRReviewResponse:
        summary = analysis.summary
        risks = analysis.risks
        arch = analysis.architecture_impact
        tests = analysis.test_recommendations

        positive_findings: List[str] = []
        suggestions: List[str] = []
        required_follow_ups: List[str] = []

        # 1. Determine positive findings
        if summary.files_changed > 0:
            positive_findings.append(f"Clean, focused changes across {summary.files_changed} file(s) (+{summary.lines_added}/-{summary.lines_removed}).")
        if not risks:
            positive_findings.append("Static security review passed with 0 vulnerabilities detected.")
        if not arch.layer_violations:
            positive_findings.append("Changes conform to repository architectural layers without circular dependencies.")
        if not tests.missing_tests and tests.related_tests:
            positive_findings.append("Existing test coverage identified for the touched components.")

        # 2. Determine suggestions & follow-ups
        for risk in risks:
            required_follow_ups.append(f"Remediate {risk.title} in `{risk.file_path}`: {risk.remediation}")

        for violation in arch.layer_violations:
            required_follow_ups.append(f"Resolve layer violation: {violation}")

        for missing in tests.missing_tests:
            suggestions.append(f"Add test coverage: {missing}")

        for scenario in tests.recommended_scenarios[:3]:
            suggestions.append(f"Add test scenario: {scenario}")

        # 3. Determine review verdict
        has_critical = any(r.severity == "Critical" for r in risks) or bool(arch.layer_violations)
        has_high = any(r.severity == "High" for r in risks)
        has_warnings = bool(risks) or bool(tests.missing_tests)

        if has_critical or has_high:
            verdict = "REQUEST_CHANGES"
        elif has_warnings:
            verdict = "COMMENT"
        else:
            verdict = "APPROVE"

        # Build repository sources citation
        sources: List[SourceAttribution] = []
        for fc in analysis.file_changes:
            sources.append(SourceAttribution(
                file_path=fc.file_path,
                line_number=1,
                relevance_reason=f"PR modified file ({fc.status})"
            ))

        return PRReviewResponse(
            verdict=verdict,
            summary=summary,
            positive_findings=positive_findings,
            risks=risks,
            suggestions=suggestions,
            required_follow_ups=required_follow_ups,
            review_comments=analysis.review_comments,
            sources=sources[:20]
        )


class PRService:
    """Orchestrates pull request diff parsing, intelligence analysis, and automated code review."""

    def __init__(self):
        self.diff_parser = diff_parser
        self.change_classifier = change_classifier
        self.arch_reviewer = ArchitectureReviewer()
        self.test_analyzer = TestImpactAnalyzer()
        self.security_scanner = DiffSecurityScanner()
        self.comment_generator = ReviewCommentGenerator()
        self.summarizer = PRSummarizer()
        self.review_agent = PRReviewAgent()

    def analyze_pr(
        self,
        diff_text: str,
        repo_index: Optional[RepositoryIndex] = None,
        title: str = "",
        description: str = ""
    ) -> PullRequestAnalysis:
        if not diff_text or not diff_text.strip():
            raise ValueError("diff_text is required and cannot be empty")

        file_changes = self.diff_parser.parse(diff_text, repo_index=repo_index)
        change_type = self.change_classifier.classify(file_changes, title=title, description=description)

        arch_impact = self.arch_reviewer.analyze(file_changes, repo_index)
        test_rec = self.test_analyzer.analyze(file_changes, repo_index)
        risks = self.security_scanner.scan(file_changes)
        review_comments = self.comment_generator.generate(file_changes, risks, arch_impact, test_rec)
        summary = self.summarizer.summarize(file_changes, change_type, risks, arch_impact, test_rec, title=title, description=description)

        return PullRequestAnalysis(
            pr_id=f"pr_{abs(hash(diff_text)) % 100000}",
            summary=summary,
            file_changes=file_changes,
            architecture_impact=arch_impact,
            test_recommendations=test_rec,
            risks=risks,
            review_comments=review_comments
        )

    def review_pr(
        self,
        diff_text: str,
        repo_index: Optional[RepositoryIndex] = None,
        title: str = "",
        description: str = ""
    ) -> PRReviewResponse:
        analysis = self.analyze_pr(diff_text, repo_index, title=title, description=description)
        return self.review_agent.review(analysis)

    def summarize_pr(
        self,
        diff_text: str,
        repo_index: Optional[RepositoryIndex] = None,
        title: str = "",
        description: str = ""
    ) -> PRSummary:
        analysis = self.analyze_pr(diff_text, repo_index, title=title, description=description)
        return analysis.summary


pr_service = PRService()
