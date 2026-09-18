import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from config import settings
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, Dependency,
    PullRequestAnalysis, PRReviewResponse, PRSummary,
    FileChange, DiffHunk, CodeChange, RiskAssessment, ReviewComment
)
from server import ACTIVE_SESSIONS, app
from services.diff_service import diff_parser, change_classifier, GitDiffParser, ChangeClassifier
from services.pr_service import pr_service, PRService, ArchitectureReviewer, TestImpactAnalyzer, DiffSecurityScanner, ReviewCommentGenerator, PRSummarizer, PRReviewAgent
from services.agent.tools import build_repository_tool_registry, build_pr_tool_registry
from services.agent.tool_executor import ToolExecutor
from models.repository_index import ToolCall
from services.repo_service import repo_service


DIFF_SAMPLE_FEATURE = """diff --git a/services/payment_service.py b/services/payment_service.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/services/payment_service.py
@@ -0,0 +1,25 @@
+from typing import Dict, Any
+
+class PaymentService:
+    def __init__(self, provider: str = "stripe"):
+        self.provider = provider
+
+    def process_payment(self, amount: float, currency: str = "USD") -> Dict[str, Any]:
+        if amount <= 0:
+            raise ValueError("Amount must be positive")
+        return {"success": True, "transaction_id": "tx_9988", "amount": amount}
+
+    def refund_payment(self, transaction_id: str) -> bool:
+        return True
+"""

DIFF_SAMPLE_VULNERABLE = """diff --git a/services/report_generator.py b/services/report_generator.py
--- a/services/report_generator.py
+++ b/services/report_generator.py
@@ -10,6 +10,18 @@ def run_report(user_code: str, query: str):
+    api_key = "AIzaSyD-LIVE-SECRET-KEY-ABC1234567"
+    eval(user_code)
+    exec("import os")
+    import subprocess
+    subprocess.Popen("rm -rf /tmp", shell=True)
+    import requests
+    requests.get("https://internal.service/api", verify=False)
+    import pickle
+    pickle.loads(user_code)
+    return True
"""

DIFF_SAMPLE_LAYER_VIOLATION = """diff --git a/models/account.py b/models/account.py
--- a/models/account.py
+++ b/models/account.py
@@ -1,5 +1,9 @@
 from pydantic import BaseModel
+# Model importing server/api layer directly
+from server import app
+import services.repo_service
+
 class Account(BaseModel):
     account_id: str
"""

DIFF_SAMPLE_RENAME_AND_MODIFY = """diff --git a/lib/old_utils.py b/lib/new_utils.py
similarity index 90%
rename from lib/old_utils.py
rename to lib/new_utils.py
--- a/lib/old_utils.py
+++ b/lib/new_utils.py
@@ -5,4 +5,5 @@ def helper_one():
-    return 1
+    return 10
+def helper_two():
+    return 20
"""

DIFF_SAMPLE_BUGFIX = """diff --git a/services/auth.py b/services/auth.py
--- a/services/auth.py
+++ b/services/auth.py
@@ -12,4 +12,6 @@ def validate(token):
-    return token.is_valid()
+    if not token:
+        return False
+    return token.is_valid()
"""

DIFF_SAMPLE_DOCS = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,6 @@
 # Project
+
+## Getting Started
+Run with python server.py
"""

DIFF_SAMPLE_CONFIG = """diff --git a/requirements.txt b/requirements.txt
--- a/requirements.txt
+++ b/requirements.txt
@@ -1,2 +1,3 @@
 fastapi>=0.100.0
+redis>=4.5.0
"""

DIFF_SAMPLE_TESTS = """diff --git a/tests/test_payments.py b/tests/test_payments.py
new file mode 100644
--- /dev/null
+++ b/tests/test_payments.py
@@ -0,0 +1,10 @@
+import unittest
+
+class TestPayment(unittest.TestCase):
+    def test_success(self):
+        self.assertTrue(True)
+"""


class TestM7PullRequestIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.success, cls.repo_index, cls.err_msg = repo_service.parse_repository(str(ROOT_DIR))
        if cls.success and cls.repo_index:
            ACTIVE_SESSIONS["default"] = cls.repo_index
        cls.client = TestClient(app)

    def test_01_diff_parser_extracts_files_and_hunks(self):
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        self.assertEqual(len(changes), 1)
        fc = changes[0]
        self.assertEqual(fc.file_path, "services/payment_service.py")
        self.assertEqual(fc.status, "added")
        self.assertGreater(fc.additions, 0)
        self.assertEqual(fc.deletions, 0)
        self.assertEqual(len(fc.hunks), 1)

    def test_02_diff_parser_extracts_modified_symbols(self):
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        fc = changes[0]
        self.assertTrue(any("PaymentService" in sym or "process_payment" in sym for sym in fc.modified_symbols))

    def test_03_diff_parser_handles_renames(self):
        changes = diff_parser.parse(DIFF_SAMPLE_RENAME_AND_MODIFY)
        self.assertEqual(len(changes), 1)
        fc = changes[0]
        self.assertEqual(fc.status, "renamed")
        self.assertEqual(fc.old_path, "lib/old_utils.py")
        self.assertEqual(fc.file_path, "lib/new_utils.py")

    def test_04_diff_parser_extracts_added_lines_with_numbers(self):
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        added_lines = diff_parser.extract_added_lines(changes[0])
        self.assertGreater(len(added_lines), 0)
        self.assertEqual(added_lines[0].change_type, "added")
        self.assertIsNotNone(added_lines[0].new_line_number)

    def test_05_change_classifier_feature(self):
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        cat = change_classifier.classify(changes, title="Add new payment provider support")
        self.assertEqual(cat, "feature")

    def test_06_change_classifier_bugfix(self):
        changes = diff_parser.parse(DIFF_SAMPLE_BUGFIX)
        cat = change_classifier.classify(changes, title="Fix null token validation crash")
        self.assertEqual(cat, "bug_fix")

    def test_07_change_classifier_documentation(self):
        changes = diff_parser.parse(DIFF_SAMPLE_DOCS)
        cat = change_classifier.classify(changes)
        self.assertEqual(cat, "documentation_update")

    def test_08_change_classifier_config(self):
        changes = diff_parser.parse(DIFF_SAMPLE_CONFIG)
        cat = change_classifier.classify(changes)
        self.assertEqual(cat, "configuration_change")

    def test_09_change_classifier_tests(self):
        changes = diff_parser.parse(DIFF_SAMPLE_TESTS)
        cat = change_classifier.classify(changes)
        self.assertEqual(cat, "test_update")

    def test_10_change_classifier_refactor(self):
        changes = diff_parser.parse(DIFF_SAMPLE_RENAME_AND_MODIFY)
        cat = change_classifier.classify(changes, title="Refactor utils module structure")
        self.assertEqual(cat, "refactor")

    def test_11_security_scanner_detects_hardcoded_secret(self):
        changes = diff_parser.parse(DIFF_SAMPLE_VULNERABLE)
        scanner = DiffSecurityScanner()
        risks = scanner.scan(changes)
        titles = [r.title for r in risks]
        self.assertTrue(any("Secret" in t or "Credential" in t for t in titles))

    def test_12_security_scanner_detects_unsafe_eval_and_exec(self):
        changes = diff_parser.parse(DIFF_SAMPLE_VULNERABLE)
        scanner = DiffSecurityScanner()
        risks = scanner.scan(changes)
        titles = [r.title for r in risks]
        self.assertTrue(any("eval" in t for t in titles))
        self.assertTrue(any("exec" in t for t in titles))

    def test_13_security_scanner_detects_shell_execution(self):
        changes = diff_parser.parse(DIFF_SAMPLE_VULNERABLE)
        scanner = DiffSecurityScanner()
        risks = scanner.scan(changes)
        titles = [r.title for r in risks]
        self.assertTrue(any("Shell Execution" in t for t in titles))

    def test_14_security_scanner_detects_ssl_verification_disabled(self):
        changes = diff_parser.parse(DIFF_SAMPLE_VULNERABLE)
        scanner = DiffSecurityScanner()
        risks = scanner.scan(changes)
        titles = [r.title for r in risks]
        self.assertTrue(any("SSL" in t for t in titles))

    def test_15_security_scanner_detects_unsafe_deserialization(self):
        changes = diff_parser.parse(DIFF_SAMPLE_VULNERABLE)
        scanner = DiffSecurityScanner()
        risks = scanner.scan(changes)
        titles = [r.title for r in risks]
        self.assertTrue(any("Deserialization" in t for t in titles))

    def test_16_architecture_reviewer_layer_classification(self):
        reviewer = ArchitectureReviewer()
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        impact = reviewer.analyze(changes, self.repo_index)
        self.assertIn("service", impact.architectural_layers)

    def test_17_architecture_reviewer_detects_layer_violation(self):
        reviewer = ArchitectureReviewer()
        changes = diff_parser.parse(DIFF_SAMPLE_LAYER_VIOLATION)
        impact = reviewer.analyze(changes, self.repo_index)
        self.assertGreater(len(impact.layer_violations), 0)
        self.assertIn("Model layer file imports", impact.layer_violations[0])

    def test_18_architecture_reviewer_traces_entry_points(self):
        reviewer = ArchitectureReviewer()
        diff_entry = """diff --git a/server.py b/server.py
--- a/server.py
+++ b/server.py
@@ -10,3 +10,4 @@ import os
+# entry point change
"""
        changes = diff_parser.parse(diff_entry)
        impact = reviewer.analyze(changes, self.repo_index)
        self.assertIn("server.py", impact.affected_entry_points)

    def test_19_test_impact_analyzer_flags_missing_tests(self):
        analyzer = TestImpactAnalyzer()
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        rec = analyzer.analyze(changes, self.repo_index)
        self.assertGreater(len(rec.missing_tests), 0)

    def test_20_test_impact_analyzer_recommends_scenarios(self):
        analyzer = TestImpactAnalyzer()
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        rec = analyzer.analyze(changes, self.repo_index)
        self.assertGreater(len(rec.recommended_scenarios), 0)
        self.assertGreater(len(rec.recommended_edge_cases), 0)

    def test_21_review_comment_generator_creates_evidence_comments(self):
        gen = ReviewCommentGenerator()
        changes = diff_parser.parse(DIFF_SAMPLE_VULNERABLE)
        risks = DiffSecurityScanner().scan(changes)
        arch = ArchitectureReviewer().analyze(changes, self.repo_index)
        test_rec = TestImpactAnalyzer().analyze(changes, self.repo_index)
        comments = gen.generate(changes, risks, arch, test_rec)
        self.assertGreater(len(comments), 0)
        self.assertTrue(any(c.severity in ["critical", "warning"] for c in comments))
        self.assertTrue(any(c.recommendation for c in comments))

    def test_22_pr_summarizer_generates_two_tier_summary(self):
        summarizer = PRSummarizer()
        changes = diff_parser.parse(DIFF_SAMPLE_FEATURE)
        risks = []
        arch = ArchitectureReviewer().analyze(changes, self.repo_index)
        test_rec = TestImpactAnalyzer().analyze(changes, self.repo_index)
        summary = summarizer.summarize(changes, "feature", risks, arch, test_rec, title="Payment Integration")
        self.assertIn("Payment Integration", summary.executive_summary)
        self.assertIn("Developer Summary", summary.developer_summary)
        self.assertEqual(summary.risk_level, "Medium")  # Medium due to missing tests

    def test_23_pr_review_agent_requests_changes_on_security_risk(self):
        agent = PRReviewAgent()
        analysis = pr_service.analyze_pr(DIFF_SAMPLE_VULNERABLE, repo_index=self.repo_index)
        review = agent.review(analysis)
        self.assertEqual(review.verdict, "REQUEST_CHANGES")
        self.assertGreater(len(review.risks), 0)
        self.assertGreater(len(review.required_follow_ups), 0)

    def test_24_pr_review_agent_approves_safe_tested_changes(self):
        safe_tested_diff = DIFF_SAMPLE_DOCS
        analysis = pr_service.analyze_pr(safe_tested_diff, repo_index=self.repo_index)
        review = PRReviewAgent().review(analysis)
        self.assertEqual(review.verdict, "APPROVE")
        self.assertGreater(len(review.positive_findings), 0)

    def test_25_agent_pr_tools_registered_when_diff_provided(self):
        registry = build_pr_tool_registry(self.repo_index, DIFF_SAMPLE_FEATURE)
        names = registry.names()
        self.assertIn("get_pr_diff", names)
        self.assertIn("get_changed_files", names)
        self.assertIn("get_changed_symbols", names)
        self.assertIn("review_architecture", names)
        self.assertIn("review_security", names)
        self.assertIn("review_tests", names)
        self.assertIn("summarize_changes", names)

    def test_26_agent_pr_tool_get_changed_files(self):
        registry = build_pr_tool_registry(self.repo_index, DIFF_SAMPLE_FEATURE)
        executor = ToolExecutor(registry)
        result = executor.execute(ToolCall(call_id="c1", tool_name="get_changed_files", arguments={}))
        self.assertTrue(result.success)
        self.assertIn("files", result.data)
        self.assertEqual(len(result.data["files"]), 1)

    def test_27_agent_pr_tool_review_security(self):
        registry = build_pr_tool_registry(self.repo_index, DIFF_SAMPLE_VULNERABLE)
        executor = ToolExecutor(registry)
        result = executor.execute(ToolCall(call_id="c2", tool_name="review_security", arguments={}))
        self.assertTrue(result.success)
        self.assertGreater(len(result.data["risks"]), 0)

    def test_28_agent_pr_tool_review_architecture(self):
        registry = build_pr_tool_registry(self.repo_index, DIFF_SAMPLE_LAYER_VIOLATION)
        executor = ToolExecutor(registry)
        result = executor.execute(ToolCall(call_id="c3", tool_name="review_architecture", arguments={}))
        self.assertTrue(result.success)
        self.assertIn("architecture_impact", result.data)
        self.assertGreater(len(result.data["architecture_impact"]["layer_violations"]), 0)

    def test_29_agent_pr_tool_summarize_changes(self):
        registry = build_pr_tool_registry(self.repo_index, DIFF_SAMPLE_FEATURE)
        executor = ToolExecutor(registry)
        result = executor.execute(ToolCall(call_id="c4", tool_name="summarize_changes", arguments={}))
        self.assertTrue(result.success)
        self.assertIn("summary", result.data)
        self.assertEqual(result.data["summary"]["change_type"], "feature")

    def test_30_api_endpoint_pr_analyze(self):
        ACTIVE_SESSIONS["default"] = self.repo_index
        res = self.client.post("/api/pr/analyze", json={
            "diff": DIFF_SAMPLE_FEATURE,
            "session_id": "default",
            "title": "Payment Service Feature"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("file_changes", data)
        self.assertIn("architecture_impact", data)
        self.assertIn("test_recommendations", data)
        self.assertIn("review_comments", data)

    def test_31_api_endpoint_pr_review(self):
        ACTIVE_SESSIONS["default"] = self.repo_index
        res = self.client.post("/api/pr/review", json={
            "diff": DIFF_SAMPLE_VULNERABLE,
            "session_id": "default",
            "title": "Vulnerable PR Review"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["verdict"], "REQUEST_CHANGES")
        self.assertGreater(len(data["risks"]), 0)
        self.assertGreater(len(data["review_comments"]), 0)

    def test_32_api_endpoint_pr_summary(self):
        ACTIVE_SESSIONS["default"] = self.repo_index
        res = self.client.post("/api/pr/summary", json={
            "diff": DIFF_SAMPLE_FEATURE,
            "session_id": "default"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("executive_summary", data)
        self.assertIn("developer_summary", data)

    def test_33_api_empty_diff_validation(self):
        res = self.client.post("/api/pr/analyze", json={"diff": "   "})
        self.assertEqual(res.status_code, 400)

    def test_34_pr_service_empty_diff_raises_error(self):
        with self.assertRaises(ValueError):
            pr_service.analyze_pr("")


if __name__ == "__main__":
    unittest.main()
