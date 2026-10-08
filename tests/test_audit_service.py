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

    # =========================================================================
    # REGRESSION TESTS (Tasks 1-7)
    # =========================================================================

    def test_05_regression_real_hardcoded_secret(self):
        """Test 1 — Real hardcoded secret in repository source is detected and masked."""
        import tempfile
        scanner = SecurityScanner()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write('api_key = "AIzaSyD-REAL-TOKEN-1234567890"\n')
            temp_path = tf.name

        try:
            file_info = FileInfo(
                full_path=temp_path,
                relative_path="services/config.py",
                file_name="config.py",
                language="python",
                line_count=1,
                in_degree=1,
                out_degree=0,
                module_category="core",
                last_modified="Recent"
            )
            mock_repo = RepositoryIndex(
                repo_name="SecretRepo",
                repo_path=str(Path(temp_path).parent),
                total_files=1,
                total_lines=1,
                files=[file_info]
            )
            opps = scanner.scan(mock_repo)
            self.assertEqual(len(opps), 1)
            opp = opps[0]
            self.assertEqual(opp.category, "security")
            self.assertEqual(opp.severity, "High")
            self.assertIn("Potential Hardcoded Secret", opp.title)
            self.assertIn("config.py", opp.target_files[0])
            # Ensure raw secret is not leaked in plain text
            self.assertNotIn("AIzaSyD-REAL-TOKEN-1234567890", opp.description)
            self.assertIn("AIza...****...7890", opp.description)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_06_regression_real_eval(self):
        """Test 2 — Real eval(user_input) is detected as high-confidence Critical vulnerability."""
        import tempfile
        scanner = SecurityScanner()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write('def execute(user_input):\n    eval(user_input)\n')
            temp_path = tf.name

        try:
            file_info = FileInfo(
                full_path=temp_path,
                relative_path="services/handler.py",
                file_name="handler.py",
                language="python",
                line_count=2,
                in_degree=1,
                out_degree=0,
                module_category="core",
                last_modified="Recent"
            )
            mock_repo = RepositoryIndex(
                repo_name="EvalRepo",
                repo_path=str(Path(temp_path).parent),
                total_files=1,
                total_lines=2,
                files=[file_info]
            )
            opps = scanner.scan(mock_repo)
            self.assertEqual(len(opps), 1)
            opp = opps[0]
            self.assertEqual(opp.category, "security")
            self.assertEqual(opp.severity, "Critical")
            self.assertEqual(opp.confidence, "High")
            self.assertIn("eval", opp.title.lower())
            self.assertEqual(opp.line_number, 2)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_07_regression_example_string_eval(self):
        """Test 3 — Example string 'eval(user_input)' produces NO high-confidence eval vulnerability."""
        import tempfile
        scanner = SecurityScanner()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write('example = "eval(user_input)"\n')
            temp_path = tf.name

        try:
            file_info = FileInfo(
                full_path=temp_path,
                relative_path="services/docs.py",
                file_name="docs.py",
                language="python",
                line_count=1,
                in_degree=1,
                out_degree=0,
                module_category="standard",
                last_modified="Recent"
            )
            mock_repo = RepositoryIndex(
                repo_name="DocRepo",
                repo_path=str(Path(temp_path).parent),
                total_files=1,
                total_lines=1,
                files=[file_info]
            )
            opps = scanner.scan(mock_repo)
            # Must NOT produce high-confidence eval vulnerability
            eval_opps = [o for o in opps if "eval" in o.title.lower() and o.confidence == "High"]
            self.assertEqual(len(eval_opps), 0)
            self.assertEqual(len(opps), 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_08_regression_environment_variable(self):
        """Test 4 — Environment variable 'api_key = os.getenv(\"API_KEY\")' produces NO hardcoded-secret finding."""
        import tempfile
        scanner = SecurityScanner()
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write('import os\napi_key = os.getenv("API_KEY")\n')
            temp_path = tf.name

        try:
            file_info = FileInfo(
                full_path=temp_path,
                relative_path="config.py",
                file_name="config.py",
                language="python",
                line_count=2,
                in_degree=1,
                out_degree=0,
                module_category="core",
                last_modified="Recent"
            )
            mock_repo = RepositoryIndex(
                repo_name="EnvRepo",
                repo_path=str(Path(temp_path).parent),
                total_files=1,
                total_lines=2,
                files=[file_info]
            )
            opps = scanner.scan(mock_repo)
            secret_opps = [o for o in opps if "secret" in o.title.lower() or "secret" in o.category.lower()]
            self.assertEqual(len(secret_opps), 0)
            self.assertEqual(len(opps), 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_09_regression_demo_fixture_no_false_positive_on_app_js(self):
        """Test 5 — Demo fixtures and frontend/app.js do not create false vulnerabilities during repository audit."""
        scanner = SecurityScanner()
        app_js_path = str(ROOT_DIR / "frontend" / "app.js")
        self.assertTrue(os.path.exists(app_js_path), "frontend/app.js must exist")

        file_info = FileInfo(
            full_path=app_js_path,
            relative_path="frontend/app.js",
            file_name="app.js",
            language="javascript",
            line_count=2000,
            in_degree=1,
            out_degree=0,
            module_category="entry_point",
            last_modified="Recent"
        )
        mock_repo = RepositoryIndex(
            repo_name="OnBoardingBuddy",
            repo_path=str(ROOT_DIR),
            total_files=1,
            total_lines=2000,
            files=[file_info]
        )
        opps = scanner.scan(mock_repo)
        # Verify no false positive security findings against frontend/app.js
        sec_opps = [o for o in opps if o.category == "security"]
        self.assertEqual(len(sec_opps), 0, f"Expected 0 security findings in app.js, found: {[o.title for o in sec_opps]}")

    def test_10_regression_pr_demo_diff_security_analysis(self):
        """Test 6 — Intentionally vulnerable sample diff is correctly detected by PR diff security analysis pipeline."""
        from services.diff_service import diff_parser
        from services.pr_service import DiffSecurityScanner

        fixture_path = ROOT_DIR / "tests" / "fixtures" / "sample_vulnerable_diff.txt"
        self.assertTrue(fixture_path.exists(), "sample_vulnerable_diff.txt fixture must exist")

        diff_text = fixture_path.read_text(encoding="utf-8")
        file_changes = diff_parser.parse(diff_text)
        self.assertGreater(len(file_changes), 0)

        pr_scanner = DiffSecurityScanner()
        risks = pr_scanner.scan(file_changes)
        self.assertEqual(len(risks), 4)

        risk_titles = [r.title for r in risks]
        self.assertTrue(any("secret" in t.lower() or "credential" in t.lower() for t in risk_titles))
        self.assertTrue(any("eval" in t.lower() for t in risk_titles))
        self.assertTrue(any("shell" in t.lower() for t in risk_titles))
        self.assertTrue(any("ssl" in t.lower() or "certificate" in t.lower() for t in risk_titles))

    def test_11_api_sample_diffs_endpoint(self):
        """Test GET /api/pr/sample-diffs endpoint supplies feature, vulnerable, and architecture diffs."""
        res = self.client.get("/api/pr/sample-diffs")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("feature", data)
        self.assertIn("vulnerable", data)
        self.assertIn("architecture", data)
        self.assertIn("eval(query_param)", data["vulnerable"])
        self.assertIn("AIzaSyD-TESTING-SECRET-KEY-12345678", data["vulnerable"])

    def test_12_regression_js_real_eval_and_template_string_distinction(self):
        """Test JS scanner detects real eval() and real secret, but ignores template strings and comments."""
        import tempfile
        scanner = SecurityScanner()
        js_code = """
        // Real vulnerabilities in executable JS:
        function runCode(userInput) {
            eval(userInput);
        }
        const apiKey = "AIzaSyD-JS-REAL-SECRET-12345678";

        // Non-executable template strings & comments:
        const sampleDoc = `
            eval(query_param);
            api_key = "AIzaSyD-FAKE-KEY-12345678";
        `;
        // eval(commentedOut);
        const harmless = "eval(inAStringLiteral)";
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as tf:
            tf.write(js_code)
            temp_path = tf.name

        try:
            file_info = FileInfo(
                full_path=temp_path,
                relative_path="client/main.js",
                file_name="main.js",
                language="javascript",
                line_count=20,
                in_degree=1,
                out_degree=0,
                module_category="entry_point",
                last_modified="Recent"
            )
            mock_repo = RepositoryIndex(
                repo_name="JSRepo",
                repo_path=str(Path(temp_path).parent),
                total_files=1,
                total_lines=20,
                files=[file_info]
            )
            opps = scanner.scan(mock_repo)
            self.assertEqual(len(opps), 2)
            eval_opp = next((o for o in opps if "eval" in o.title.lower()), None)
            secret_opp = next((o for o in opps if "secret" in o.title.lower()), None)
            self.assertIsNotNone(eval_opp)
            self.assertIsNotNone(secret_opp)
            self.assertEqual(eval_opp.severity, "Critical")
            self.assertEqual(secret_opp.severity, "High")
            self.assertIn("AIza...****...5678", secret_opp.description)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_13_regression_python_subprocess_and_ssl(self):
        """Test Python scanner detects shell=True and verify=False with proper severity and confidence."""
        import tempfile
        scanner = SecurityScanner()
        py_code = """
        import subprocess
        import requests

        def run_task(cmd, url):
            subprocess.Popen(cmd, shell=True)
            requests.get(url, verify=False)
        """
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(py_code)
            temp_path = tf.name

        try:
            file_info = FileInfo(
                full_path=temp_path,
                relative_path="services/worker.py",
                file_name="worker.py",
                language="python",
                line_count=10,
                in_degree=1,
                out_degree=0,
                module_category="core",
                last_modified="Recent"
            )
            mock_repo = RepositoryIndex(
                repo_name="WorkerRepo",
                repo_path=str(Path(temp_path).parent),
                total_files=1,
                total_lines=10,
                files=[file_info]
            )
            opps = scanner.scan(mock_repo)
            self.assertEqual(len(opps), 2)
            shell_opp = next((o for o in opps if "shell" in o.title.lower()), None)
            ssl_opp = next((o for o in opps if "ssl" in o.title.lower()), None)
            self.assertIsNotNone(shell_opp)
            self.assertIsNotNone(ssl_opp)
            self.assertEqual(shell_opp.severity, "High")
            self.assertEqual(shell_opp.confidence, "High")
            self.assertEqual(ssl_opp.severity, "High")
            self.assertEqual(ssl_opp.confidence, "High")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
