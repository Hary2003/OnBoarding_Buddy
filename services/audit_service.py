import os
import re
from typing import List, Dict, Set, Tuple, Optional
from models.repository_index import RepositoryIndex, FileInfo, ContributionOpportunity, AuditReport

SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|password)\s*=\s*[\'"]([a-zA-Z0-9_\-]{16,})[\'"]', "Hardcoded Secret / API Token"),
    (r'(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}', "Exposed Bearer Authentication Token")
]

UNSAFE_PATTERNS = [
    (r'\beval\s*\(', "Unsafe Dynamic Code Evaluation (eval)", "Critical"),
    (r'\bexec\s*\(', "Unsafe Execution (exec)", "Critical"),
    (r'shell\s*=\s*True', "Subprocess Shell Execution Vulnerability", "High"),
    (r'verify\s*=\s*False', "Disabled SSL Certificate Verification", "High"),
    (r'pickle\.loads\s*\(', "Unsafe Object Deserialization (pickle.loads)", "High"),
    (r'yaml\.load\s*\([^,)]*\)', "Unsafe PyYAML Load (use SafeLoader)", "Medium")
]

class SecurityScanner:
    def scan(self, repo_index: RepositoryIndex) -> List[ContributionOpportunity]:
        opportunities: List[ContributionOpportunity] = []
        opp_counter = 1

        for file_info in repo_index.files:
            if file_info.language not in ["python", "javascript", "typescript"]:
                continue

            try:
                with open(file_info.full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                lines = content.splitlines()

                # 1. Hardcoded secrets check
                for line_idx, line in enumerate(lines, start=1):
                    # Skip comments or obvious placeholders
                    if line.strip().startswith("#") or line.strip().startswith("//") or "example" in line.lower() or "your_" in line.lower() or "test" in file_info.relative_path.lower():
                        continue

                    for pattern, label in SECRET_PATTERNS:
                        match = re.search(pattern, line)
                        if match:
                            opp_id = f"sec_{opp_counter}"
                            opp_counter += 1
                            title = f"🔒 Remediate {label} in `{file_info.file_name}`"
                            desc = f"Detected potential hardcoded secret on line {line_idx} of `{file_info.relative_path}`. Hardcoded credentials pose severe security risks when committed to version control."
                            remediation = f"Extract secret parameter on line {line_idx} into an environment variable (`.env` / `config.py`)."
                            
                            opportunities.append(ContributionOpportunity(
                                opportunity_id=opp_id,
                                title=title,
                                category="security",
                                severity="Critical",
                                target_files=[file_info.relative_path],
                                description=desc,
                                remediation_plan=remediation,
                                suggested_issue_title=f"Security: Remediate {label} in {file_info.file_name}",
                                suggested_issue_desc=f"Line {line_idx} of {file_info.relative_path} contains potential hardcoded credentials. Refactor to load from environment configuration."
                            ))
                            break

                # 2. Unsafe functions check
                for pattern, label, severity in UNSAFE_PATTERNS:
                    matches = re.finditer(pattern, content)
                    for m in matches:
                        line_no = content[:m.start()].count("\n") + 1
                        # Skip if in tests folder
                        if "test" in file_info.relative_path.lower() or "venv" in file_info.relative_path.lower():
                            continue

                        opp_id = f"sec_{opp_counter}"
                        opp_counter += 1
                        title = f"🛡️ Fix {label} in `{file_info.file_name}`"
                        desc = f"Identified `{label}` on line {line_no} in `{file_info.relative_path}`. Unsafe function usage can lead to Remote Code Execution (RCE) or Security Bypass."
                        remediation = f"Replace unsafe call on line {line_no} of `{file_info.relative_path}` with safe AST parsing or secure library calls."

                        opportunities.append(ContributionOpportunity(
                            opportunity_id=opp_id,
                            title=title,
                            category="security",
                            severity=severity,
                            target_files=[file_info.relative_path],
                            description=desc,
                            remediation_plan=remediation,
                            suggested_issue_title=f"Security: Refactor {label} in {file_info.file_name}",
                            suggested_issue_desc=f"Line {line_no} of {file_info.relative_path} uses unsafe patterns ({label}). Refactor to use safe alternatives."
                        ))

            except Exception:
                pass

        return opportunities

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
