"""
Export Service for OnBoarding Buddy
Generates structured Markdown and JSON export documents for:
- Repository Onboarding Guides
- Architectural Specifications (with Mermaid diagrams)
- Audit & Contribution Reports
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from models.repository_index import RepositoryIndex, AuditReport, ContributionOpportunity


class ExportService:
    """Enterprise export service providing downloadable Markdown specifications and reports."""

    @staticmethod
    def export_onboarding_guide_markdown(
        repo_index: RepositoryIndex,
        guide_content: Optional[str] = None
    ) -> str:
        """Formats an onboarding guide into a polished, portable Markdown document."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        repo_name = repo_index.repo_name
        total_files = repo_index.total_files
        total_lines = repo_index.total_lines
        arch_type = repo_index.architecture_summary.architecture_type if repo_index.architecture_summary else "Modular"
        entry_points = repo_index.entry_points or ["None explicitly identified"]
        langs = repo_index.languages_breakdown or {}
        lang_str = ", ".join([f"{k} ({v})" for k, v in langs.items()]) or "Not specified"

        md_lines = [
            f"# 🚀 Developer Onboarding Guide: {repo_name}",
            f"",
            f"> Generated automatically by **OnBoarding Buddy** on `{now}`.",
            f"",
            f"---",
            f"",
            f"## 📋 Repository Quick Facts",
            f"",
            f"- **Repository Name**: `{repo_name}`",
            f"- **Architecture Pattern**: `{arch_type}`",
            f"- **Total Source Files**: `{total_files:,}`",
            f"- **Total Lines of Code**: `{total_lines:,}`",
            f"- **Primary Languages**: {lang_str}",
            f"- **Application Entry Points**:",
        ]

        for ep in entry_points:
            md_lines.append(f"  - `{ep}`")

        md_lines.extend([
            f"",
            f"---",
            f"",
            f"## 📖 Architecture & Orientation",
            f"",
        ])

        if guide_content and guide_content.strip():
            md_lines.append(guide_content.strip())
        else:
            md_lines.extend([
                f"### System Overview",
                f"Welcome to **{repo_name}**! This repository follows a **{arch_type}** design.",
                f"Begin your onboarding by examining the primary entry point files listed above.",
                f"",
                f"### Getting Started",
                f"1. Clone repository to your local environment.",
                f"2. Inspect configuration settings and environment variable templates (e.g. `.env.example`).",
                f"3. Run automated tests to verify your development environment.",
            ])

        md_lines.extend([
            f"",
            f"---",
            f"",
            f"*Document created by [OnBoarding Buddy](https://github.com/Hary2003/OnBoarding_Buddy) - Intelligent AST & AI Developer Onboarding Engine.*",
            f""
        ])

        return "\n".join(md_lines)

    @staticmethod
    def export_architecture_markdown(repo_index: RepositoryIndex) -> str:
        """Generates an in-depth Architectural Specification document with Mermaid diagrams."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        repo_name = repo_index.repo_name
        arch = repo_index.architecture_summary
        arch_type = arch.architecture_type if arch else "Modular"
        narrative = arch.overview_narrative if (arch and arch.overview_narrative) else "Comprehensive structural analysis."
        
        md_lines = [
            f"# 🏛️ Architecture Specification: {repo_name}",
            f"",
            f"> System Blueprint & Dependency Topology generated on `{now}`.",
            f"",
            f"## 1. Executive Summary",
            f"",
            f"- **Architecture Archetype**: `{arch_type}`",
            f"- **Source Volume**: `{repo_index.total_files:,}` files | `{repo_index.total_lines:,}` LOC",
            f"- **Circular Cycles Detected**: `{len(repo_index.circular_cycles)}`",
            f"",
            f"### Narrative Overview",
            f"{narrative}",
            f"",
            f"---",
            f"",
            f"## 2. Module Topology & Classification",
            f"",
            f"| Category | Count | Description |",
            f"| :--- | :--- | :--- |",
        ]

        category_descs = {
            "core": "Highly connected central hubs (high in-degree)",
            "leaf": "Modules with no internal dependents",
            "utility": "Shared reusable utilities and helpers",
            "entry_point": "System or CLI entry point files",
            "isolated": "Standalone modules with no internal dependencies",
            "standard": "Standard application modules",
        }

        counts = repo_index.module_counts or {}
        for cat, desc in category_descs.items():
            cnt = counts.get(cat, 0)
            if cnt > 0:
                md_lines.append(f"| **{cat.capitalize()}** | `{cnt}` | {desc} |")

        md_lines.extend([
            f"",
            f"---",
            f"",
            f"## 3. Application Entry Points",
            f"",
        ])

        if repo_index.entry_points:
            for ep in repo_index.entry_points:
                md_lines.append(f"- 🟢 `{ep}`")
        else:
            md_lines.append("*No dedicated entry points detected.*")

        md_lines.extend([
            f"",
            f"---",
            f"",
            f"## 4. Key Core Modules & Centrality",
            f"",
        ])

        core_files = [f for f in repo_index.files if f.module_category == "core" or f.in_degree >= 2]
        core_files.sort(key=lambda x: x.in_degree, reverse=True)

        if core_files:
            md_lines.append("| Module Path | In-Degree (Dependents) | Out-Degree (Imports) | Symbols |")
            md_lines.append("| :--- | :---: | :---: | :---: |")
            for cf in core_files[:15]:
                md_lines.append(f"| `{cf.relative_path}` | **{cf.in_degree}** | {cf.out_degree} | {len(cf.symbols)} |")
        else:
            md_lines.append("*All modules exhibit uniform coupling.*")

        md_lines.extend([
            f"",
            f"---",
            f"",
            f"## 5. Dependency Architecture Diagram",
            f"",
            f"```mermaid",
            f"graph TD",
        ])

        # Add top dependencies for Mermaid visualization
        added_edges = 0
        for f in repo_index.files:
            for dep in f.dependencies:
                if not dep.is_external and dep.target_file:
                    src_id = f.file_name.replace(".", "_").replace("-", "_")
                    tgt_id = dep.target_file.split("/")[-1].replace(".", "_").replace("-", "_")
                    if src_id != tgt_id:
                        md_lines.append(f"    {src_id}[\"{f.file_name}\"] --> {tgt_id}[\"{dep.target_file.split('/')[-1]}\"]")
                        added_edges += 1
                        if added_edges >= 25:
                            break
            if added_edges >= 25:
                break

        if added_edges == 0:
            md_lines.append(f"    App[\"{repo_name}\"] --> Modules[\"Modular Codebase\"]")

        md_lines.extend([
            f"```",
            f"",
            f"---",
            f"",
            f"## 6. Circular Dependencies Analysis",
            f"",
        ])

        if repo_index.circular_cycles:
            md_lines.append(f"> ⚠️ **Warning**: Found `{len(repo_index.circular_cycles)}` circular dependency cycle(s). These should be refactored.")
            md_lines.append("")
            for idx, cycle in enumerate(repo_index.circular_cycles, 1):
                raw_path = getattr(cycle, "path", None) or getattr(cycle, "cycle_path", [])
                hops = getattr(cycle, "cycle_length", len(raw_path))
                chain_str = " ➔ ".join([f"`{p}`" for p in raw_path])
                md_lines.append(f"- **Cycle #{idx}** ({hops} nodes): {chain_str}")
        else:
            md_lines.append("✅ **Clean Architecture**: No circular dependency cycles detected in this repository.")

        md_lines.extend([
            f"",
            f"---",
            f"",
            f"*Generated by OnBoarding Buddy Architecture Analyzer.*",
            f""
        ])

        return "\n".join(md_lines)

    @staticmethod
    def export_audit_markdown(audit_report: AuditReport) -> str:
        """Formats an AuditReport into an actionable Markdown contribution audit document."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        repo_name = audit_report.repo_name

        md_lines = [
            f"# 🛡️ Codebase Health & Contribution Audit: {repo_name}",
            f"",
            f"> Open Source Contribution Scanner report generated on `{now}`.",
            f"",
            f"## 📊 Audit Scorecard",
            f"",
            f"- **Total Identified Opportunities**: `{audit_report.total_opportunities}`",
            f"- 🔴 **Critical Impact**: `{audit_report.critical_count}`",
            f"- 🟠 **High Priority**: `{audit_report.high_count}`",
            f"- 🟡 **Medium Priority**: `{audit_report.medium_count}`",
            f"- 🟢 **Low / Quick Win**: `{audit_report.low_count}`",
            f"",
            f"### Executive Health Summary",
            f"{audit_report.summary_narrative or 'Automated audit scanner completed.'}",
            f"",
            f"---",
            f"",
            f"## 🎯 Contribution Opportunities",
            f"",
        ]

        if not audit_report.opportunities:
            md_lines.append("✅ **Great job!** No immediate open-source contribution issues or debt detected.")
        else:
            severity_icons = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢"
            }

            for idx, opp in enumerate(audit_report.opportunities, 1):
                icon = severity_icons.get(opp.severity.lower(), "⚪")
                md_lines.extend([
                    f"### {idx}. {icon} {opp.title}",
                    f"",
                    f"- **Category**: `{opp.category}`",
                    f"- **Severity**: `{opp.severity.upper()}`",
                    f"- **Target Files**:",
                ])
                for tf in opp.target_files:
                    md_lines.append(f"  - `{tf}`")

                md_lines.extend([
                    f"",
                    f"**Problem Description**:",
                    f"{opp.description}",
                    f"",
                    f"**Recommended Remediation Plan**:",
                    f"{opp.remediation_plan}",
                    f"",
                ])

                if opp.suggested_issue_title:
                    md_lines.extend([
                        f"**Suggested Issue / PR Title**:",
                        f"> `{opp.suggested_issue_title}`",
                        f"",
                    ])

                md_lines.append("---")
                md_lines.append("")

        md_lines.extend([
            f"*Generated by OnBoarding Buddy Audit Intelligence Engine.*",
            f""
        ])

        return "\n".join(md_lines)


export_service = ExportService()
