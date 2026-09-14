import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add root directory to sys.path
ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from server import app, ACTIVE_SESSIONS
from services.repo_service import repo_service
from services.contribution_service import (
    contribution_service, IssueAnalyzer, ContributionRanker,
    ChangeImpactAnalyzer, TestDetector, ConfigDetector
)
from models.repository_index import (
    RepositoryIndex, IssueAnalysis, ContributionCandidate, ImpactAnalysis,
    TestImpact, ConfigImpact, ContributionPlan
)

class TestContributionIntelligence(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.target = str(ROOT_DIR)
        cls.success, cls.repo_index, cls.err_msg = repo_service.parse_repository(cls.target)
        if cls.success and cls.repo_index:
            ACTIVE_SESSIONS["default"] = cls.repo_index
        cls.client = TestClient(app)

    def test_01_issue_analyzer_title_and_description(self):
        """1. Test IssueAnalyzer title and description extraction."""
        analyzer = IssueAnalyzer()
        res = analyzer.analyze(
            title="Add support for PostgreSQL connection pooling",
            description="The application should reuse database connections and allow pool size to be configured via environment variables."
        )
        self.assertIsInstance(res, IssueAnalysis)
        self.assertEqual(res.title, "Add support for PostgreSQL connection pooling")
        self.assertIn("database", res.domains)
        self.assertIn("configuration", res.domains)

    def test_02_issue_analyzer_keyword_extraction(self):
        """2. Test keyword extraction in IssueAnalyzer."""
        analyzer = IssueAnalyzer()
        res = analyzer.analyze("Fix AST symbol extraction bug in repo_service")
        self.assertTrue(any(kw in res.keywords for kw in ["ast", "symbol", "extraction", "repo_service"]))

    def test_03_issue_analyzer_technology_extraction(self):
        """3. Test technology stack term detection."""
        analyzer = IssueAnalyzer()
        res = analyzer.analyze("Integrate FastAPI router with Docker and PostgreSQL")
        self.assertIn("fastapi", res.technologies)
        self.assertIn("docker", res.technologies)
        self.assertIn("postgresql", res.technologies)

    def test_04_issue_analyzer_action_extraction(self):
        """4. Test action verbs extraction."""
        analyzer = IssueAnalyzer()
        res = analyzer.analyze("Refactor services and configure new endpoints")
        self.assertIn("refactor", res.actions)
        self.assertIn("configure", res.actions)

    def test_05_issue_analyzer_empty_input(self):
        """5. Test handling of minimal or empty issue input."""
        analyzer = IssueAnalyzer()
        res = analyzer.analyze("   ", "   ")
        self.assertIsInstance(res, IssueAnalysis)

    def test_06_contribution_ranker_m3_integration(self):
        """6. Test ContributionRanker extending M3 retrieval scores."""
        ranker = ContributionRanker()
        analyzer = IssueAnalyzer()
        issue = analyzer.analyze("Update repo_service dependency graph analysis")
        candidates = ranker.rank_candidates(self.repo_index, issue, max_files=5)
        
        self.assertGreater(len(candidates), 0)
        self.assertIsInstance(candidates[0], ContributionCandidate)
        self.assertGreater(candidates[0].contribution_score, 0.0)

    def test_07_contribution_ranker_explainable_scoring(self):
        """7. Test explainable scoring explanations on candidate objects."""
        ranker = ContributionRanker()
        analyzer = IssueAnalyzer()
        issue = analyzer.analyze("FastAPI server endpoint configuration")
        candidates = ranker.rank_candidates(self.repo_index, issue, max_files=5)
        
        top = candidates[0]
        self.assertIsInstance(top.scoring_explanations, list)
        self.assertGreater(len(top.scoring_explanations), 0)

    def test_08_change_impact_downstream_detection(self):
        """8. Test downstream impact detection via M2 graph."""
        impact_analyzer = ChangeImpactAnalyzer()
        # repo_service is imported by server.py / tests
        impact = impact_analyzer.analyze_impact(self.repo_index, ["services/repo_service.py"], max_depth=2)
        
        self.assertIn("services/repo_service.py", impact.directly_affected)
        self.assertIsInstance(impact.downstream_impact, list)
        self.assertGreater(len(impact.downstream_impact), 0)

    def test_09_change_impact_upstream_context(self):
        """9. Test upstream context detection."""
        impact_analyzer = ChangeImpactAnalyzer()
        impact = impact_analyzer.analyze_impact(self.repo_index, ["server.py"], max_depth=2)
        
        self.assertIn("server.py", impact.directly_affected)
        self.assertIsInstance(impact.upstream_context, list)

    def test_10_change_impact_circular_graph_safety(self):
        """10. Test impact analysis safety on circular graphs."""
        impact_analyzer = ChangeImpactAnalyzer()
        impact = impact_analyzer.analyze_impact(self.repo_index, ["models/repository_index.py"], max_depth=3)
        self.assertIsInstance(impact.dependency_chains, list)

    def test_11_change_impact_duplicate_prevention(self):
        """11. Test that directly affected files are not duplicated in downstream impact."""
        impact_analyzer = ChangeImpactAnalyzer()
        impact = impact_analyzer.analyze_impact(self.repo_index, ["services/repo_service.py"], max_depth=2)
        for f in impact.directly_affected:
            self.assertNotIn(f, impact.downstream_impact)

    def test_12_test_detector_direct_convention(self):
        """12. Test test file detection matching naming conventions."""
        detector = TestDetector()
        test_impact = detector.detect_tests(self.repo_index, ["services/repo_service.py"])
        
        self.assertIsInstance(test_impact, TestImpact)
        self.assertGreater(len(test_impact.directly_related_tests) + len(test_impact.potentially_related_tests), 0)

    def test_13_test_detector_import_linking(self):
        """13. Test matching test files by import declarations."""
        detector = TestDetector()
        test_impact = detector.detect_tests(self.repo_index, ["models/repository_index.py"])
        self.assertIsInstance(test_impact.evidence, list)

    def test_14_config_detector_identification(self):
        """14. Test project configuration file detection."""
        detector = ConfigDetector()
        analyzer = IssueAnalyzer()
        issue = analyzer.analyze("Configure environment settings and database host")
        config_impact = detector.detect_config(self.repo_index, issue)
        
        self.assertIsInstance(config_impact, ConfigImpact)
        self.assertTrue(any("config.py" in c or ".env" in c for c in config_impact.configuration_files) or len(config_impact.configuration_files) > 0)

    def test_15_confidence_calculation_high(self):
        """15. Test High confidence calculation logic."""
        cand = ContributionCandidate(
            file_path="services/repo_service.py",
            file_name="repo_service.py",
            base_retrieval_score=10.0,
            contribution_score=12.0,
            module_category="core",
            matched_symbols=["parse_repository()"],
            scoring_explanations=[]
        )
        impact = ImpactAnalysis(directly_affected=["services/repo_service.py"], downstream_impact=["server.py"], upstream_context=[], dependency_chains=["services/repo_service.py -> server.py"])
        tests = TestImpact(directly_related_tests=["tests/test_dependency_analysis.py"], potentially_related_tests=[], evidence=[])
        configs = ConfigImpact(configuration_files=["config.py"], evidence=[])
        
        conf, ev = contribution_service.calculate_confidence([cand], impact, tests, configs)
        self.assertEqual(conf, "High")
        self.assertGreater(len(ev), 0)

    def test_16_confidence_calculation_medium_low(self):
        """16. Test Medium and Low confidence calculations."""
        cand = ContributionCandidate(file_path="foo.py", file_name="foo.py", base_retrieval_score=2.0, contribution_score=2.5, module_category="standard", matched_symbols=[], scoring_explanations=[])
        impact = ImpactAnalysis(directly_affected=["foo.py"], downstream_impact=[], upstream_context=[], dependency_chains=[])
        tests = TestImpact(directly_related_tests=[], potentially_related_tests=[], evidence=[])
        configs = ConfigImpact(configuration_files=[], evidence=[])
        
        conf, _ = contribution_service.calculate_confidence([cand], impact, tests, configs)
        self.assertEqual(conf, "Low")

    def test_17_contribution_plan_generation(self):
        """17. Test complete ContributionPlan assembly and narrative generation."""
        plan = contribution_service.generate_plan(
            title="Add PostgreSQL connection pooling",
            description="Reuse database connections in repo_service and allow pool size in config.py",
            session_id="default",
            repo_index=self.repo_index
        )
        self.assertIsInstance(plan, ContributionPlan)
        self.assertEqual(plan.repo_name, self.repo_index.repo_name)
        self.assertIn("Contribution Intelligence", plan.plan_narrative)
        self.assertGreater(len(plan.directly_affected_files), 0)

    def test_18_no_repository_loaded_handling(self):
        """18. Test contribution analysis when no repository is loaded."""
        plan = contribution_service.generate_plan(
            title="Add PostgreSQL connection pooling",
            session_id="unloaded_session",
            repo_index=None
        )
        self.assertEqual(plan.confidence, "Low")
        self.assertIn("No repository loaded", plan.plan_narrative)

    def test_19_fastapi_contribution_analyze_endpoint(self):
        """19. Test POST /api/contribution/analyze REST endpoint."""
        res = self.client.post("/api/contribution/analyze", json={
            "title": "Refactor dependency analysis and graph extraction",
            "description": "Improve performance of directed graph traversal in services/repo_service.py",
            "session_id": "default"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("repo_name", data)
        self.assertIn("confidence", data)
        self.assertIn("plan_narrative", data)
        self.assertIn("directly_affected_files", data)

    def test_20_no_hallucinated_existing_files(self):
        """20. Test that directly affected files correspond strictly to existing repo files."""
        plan = contribution_service.generate_plan(
            title="Optimize AST parser and server router",
            session_id="default",
            repo_index=self.repo_index
        )
        existing_rel_paths = {f.relative_path for f in self.repo_index.files}
        for affected in plan.directly_affected_files:
            self.assertIn(affected, existing_rel_paths, f"Directly affected file '{affected}' does not exist in repository index!")

    def test_21_fastapi_404_when_session_invalid(self):
        """21. Test POST /api/contribution/analyze returns 404 on invalid session."""
        res = self.client.post("/api/contribution/analyze", json={
            "title": "Invalid session test",
            "session_id": "non_existent_session_999"
        })
        self.assertEqual(res.status_code, 404)

if __name__ == "__main__":
    unittest.main()
