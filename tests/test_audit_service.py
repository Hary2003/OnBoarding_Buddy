import sys
import os
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from server import app, ACTIVE_SESSIONS
from models.repository_index import RepositoryIndex, FileInfo, Symbol, CycleDetail
from services.audit_service import audit_service, SecurityScanner, ArchitectureScanner, TestCoverageScanner

class TestAuditService(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # Mock FileInfo objects
        self.file_main = FileInfo(
            full_path="d:/mock/main.py",
            relative_path="main.py",
            file_name="main.py",
            language="python",
            line_count=400,
            in_degree=5,
            out_degree=2,
            module_category="core",
            is_entry_point=True,
            last_modified="Recent",
            symbols=[Symbol(name="run_server", type="function", line_number=10)]
        )

        self.file_utils = FileInfo(
            full_path="d:/mock/utils.py",
            relative_path="utils.py",
            file_name="utils.py",
            language="python",
            line_count=150,
            in_degree=2,
            out_degree=1,
            is_circular=True,
            module_category="utility",
            last_modified="Recent"
        )

        self.mock_index = RepositoryIndex(
            repo_name="MockRepo",
            repo_path="d:/mock",
            total_files=2,
            total_lines=550,
            entry_points=["main.py"],
            circular_cycles=[
                CycleDetail(cycle_id="cycle_1", path=["utils.py", "helpers.py", "utils.py"], cycle_length=2)
            ],
            files=[self.file_main, self.file_utils]
        )

    def test_01_architecture_scanner_circular_loop(self):
        """Test detection of circular import loops as architecture opportunities."""
        scanner = ArchitectureScanner()
        opps = scanner.scan(self.mock_index)
        self.assertGreaterEqual(len(opps), 1)
        cycle_opp = next((o for o in opps if o.category == "architecture_refactor"), None)
        self.assertIsNotNone(cycle_opp)
        self.assertEqual(cycle_opp.severity, "High")
        self.assertIn("Break Circular Dependency", cycle_opp.title)

    def test_02_test_coverage_scanner_missing_tests(self):
        """Test detection of core modules lacking unit test suites."""
        scanner = TestCoverageScanner()
        opps = scanner.scan(self.mock_index)
        self.assertGreaterEqual(len(opps), 1)
        test_opp = next((o for o in opps if o.category == "test_coverage"), None)
        self.assertIsNotNone(test_opp)
        self.assertEqual(test_opp.target_files, ["main.py"])

    def test_03_audit_service_run_audit(self):
        """Test full AuditService aggregation and AuditReport narrative formatting."""
        report = audit_service.run_audit(self.mock_index)
        self.assertEqual(report.repo_name, "MockRepo")
        self.assertGreater(report.total_opportunities, 0)
        self.assertIn("# 🔍 Open Source Contribution Audit Report", report.summary_narrative)

    def test_04_api_endpoint_audit(self):
        """Test FastAPI POST /api/contribution/audit endpoint."""
        ACTIVE_SESSIONS["default"] = self.mock_index

        res = self.client.post("/api/contribution/audit", json={"session_id": "default"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["repo_name"], "MockRepo")
        self.assertGreater(data["total_opportunities"], 0)
        self.assertIn("opportunities", data)

if __name__ == "__main__":
    unittest.main()
