import os
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from server import app, ACTIVE_SESSIONS
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, CycleDetail,
    ArchitectureSummary, AuditReport, ContributionOpportunity
)
from services.export_service import export_service


class TestExportService(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        self.mock_file_app = FileInfo(
            full_path="c:/test_repo/app.py",
            relative_path="app.py",
            file_name="app.py",
            language="python",
            line_count=120,
            in_degree=1,
            out_degree=4,
            is_entry_point=True,
            last_modified="2026-09-01",
            symbols=[Symbol(name="main", type="function", line_number=10)]
        )

        self.mock_file_core = FileInfo(
            full_path="c:/test_repo/core.py",
            relative_path="core.py",
            file_name="core.py",
            language="python",
            line_count=350,
            in_degree=6,
            out_degree=1,
            module_category="core",
            is_entry_point=False,
            last_modified="2026-09-02",
            symbols=[Symbol(name="CoreEngine", type="class", line_number=25)]
        )

        self.mock_file_util = FileInfo(
            full_path="c:/test_repo/util.py",
            relative_path="util.py",
            file_name="util.py",
            language="python",
            line_count=80,
            in_degree=4,
            out_degree=0,
            module_category="utility",
            is_entry_point=False,
            last_modified="2026-09-02"
        )

        self.mock_repo_index = RepositoryIndex(
            repo_name="AcmeEngine",
            repo_path="c:/test_repo",
            total_files=3,
            total_lines=550,
            entry_points=["app.py"],
            languages_breakdown={"python": 3},
            module_counts={"core": 1, "utility": 1, "entry_point": 1},
            circular_cycles=[
                CycleDetail(cycle_id="c1", path=["core.py", "app.py", "core.py"], cycle_length=2)
            ],
            architecture_summary=ArchitectureSummary(
                architecture_type="Modular Architecture",
                overview_narrative="AcmeEngine modular architecture with robust separation of concerns.",
                core_modules=["core.py"],
                leaf_utility_modules=["util.py"],
                circular_dependencies_count=1
            ),
            files=[self.mock_file_app, self.mock_file_core, self.mock_file_util]
        )

        ACTIVE_SESSIONS["test_export"] = self.mock_repo_index

    def tearDown(self):
        ACTIVE_SESSIONS.pop("test_export", None)

    def test_01_export_onboarding_guide_markdown(self):
        """Verify markdown onboarding guide generation contains repo metadata and sections."""
        md = export_service.export_onboarding_guide_markdown(
            self.mock_repo_index,
            guide_content="### Custom Step\nRun the test suite."
        )
        self.assertIn("# 🚀 Developer Onboarding Guide: AcmeEngine", md)
        self.assertIn("Modular Architecture", md)
        self.assertIn("Total Source Files**: `3`", md)
        self.assertIn("`app.py`", md)
        self.assertIn("### Custom Step", md)
        self.assertIn("Run the test suite.", md)

    def test_02_export_architecture_markdown(self):
        """Verify markdown architecture spec generates Mermaid diagram, core files, and cycle warnings."""
        md = export_service.export_architecture_markdown(self.mock_repo_index)
        self.assertIn("# 🏛️ Architecture Specification: AcmeEngine", md)
        self.assertIn("```mermaid", md)
        self.assertIn("graph TD", md)
        self.assertIn("`core.py`", md)
        self.assertIn("Circular Dependencies Analysis", md)
        self.assertIn("Warning", md)
        self.assertIn("Cycle #1", md)

    def test_03_export_audit_markdown(self):
        """Verify audit report export structures categories and actionable remediation steps."""
        report = AuditReport(
            repo_name="AcmeEngine",
            total_opportunities=2,
            critical_count=1,
            high_count=0,
            medium_count=1,
            low_count=0,
            summary_narrative="Overall healthy codebase with 1 critical secret vulnerability.",
            opportunities=[
                ContributionOpportunity(
                    opportunity_id="sec_1",
                    title="Hardcoded API Secret in config",
                    category="security",
                    severity="Critical",
                    target_files=["config.py"],
                    description="Plaintext secret found in config.",
                    remediation_plan="Extract to environment variable.",
                    suggested_issue_title="Security: Remove hardcoded credential in config.py"
                ),
                ContributionOpportunity(
                    opportunity_id="arch_1",
                    title="Circular import loop between core and app",
                    category="architecture_refactor",
                    severity="Medium",
                    target_files=["core.py", "app.py"],
                    description="Circular dependency detected.",
                    remediation_plan="Inject dependency or decouple shared state."
                )
            ]
        )

        md = export_service.export_audit_markdown(report)
        self.assertIn("# 🛡️ Codebase Health & Contribution Audit: AcmeEngine", md)
        self.assertIn("Critical Impact**: `1`", md)
        self.assertIn("Hardcoded API Secret in config", md)
        self.assertIn("CRITICAL", md)
        self.assertIn("config.py", md)
        self.assertIn("Extract to environment variable", md)
        self.assertIn("Circular import loop between core and app", md)

    def test_04_fastapi_export_guide_json_and_download(self):
        """Verify GET /api/export/guide returns structured JSON or downloadable markdown attachment."""
        # JSON response
        res = self.client.get("/api/export/guide?session_id=test_export&download=false")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["repo_name"], "AcmeEngine")
        self.assertIn("AcmeEngine_ONBOARDING_GUIDE.md", data["filename"])
        self.assertIn("# 🚀 Developer Onboarding Guide", data["markdown"])

        # Attachment download
        res_dl = self.client.get("/api/export/guide?session_id=test_export&download=true")
        self.assertEqual(res_dl.status_code, 200)
        self.assertIn("attachment; filename=", res_dl.headers.get("content-disposition", ""))
        self.assertIn("# 🚀 Developer Onboarding Guide", res_dl.text)

    def test_05_fastapi_export_architecture_endpoint(self):
        """Verify GET /api/export/architecture returns blueprint markdown."""
        res = self.client.get("/api/export/architecture?session_id=test_export&download=false")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["repo_name"], "AcmeEngine")
        self.assertIn("AcmeEngine_ARCHITECTURE_SPEC.md", data["filename"])
        self.assertIn("# 🏛️ Architecture Specification", data["markdown"])

    def test_06_fastapi_export_audit_endpoint(self):
        """Verify GET /api/export/audit runs audit and generates report."""
        res = self.client.get("/api/export/audit?session_id=test_export&download=false")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["repo_name"], "AcmeEngine")
        self.assertIn("AcmeEngine_AUDIT_REPORT.md", data["filename"])
        self.assertIn("# 🛡️ Codebase Health & Contribution Audit", data["markdown"])

    def test_07_export_endpoints_404_when_session_missing(self):
        """Verify export endpoints return 404 cleanly when no repository session is active."""
        res_guide = self.client.get("/api/export/guide?session_id=non_existent_session_123")
        self.assertEqual(res_guide.status_code, 404)

        res_arch = self.client.get("/api/export/architecture?session_id=non_existent_session_123")
        self.assertEqual(res_arch.status_code, 404)

        res_audit = self.client.get("/api/export/audit?session_id=non_existent_session_123")
        self.assertEqual(res_audit.status_code, 404)


if __name__ == "__main__":
    unittest.main()
