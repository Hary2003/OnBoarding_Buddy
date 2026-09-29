import os
from urllib.parse import urlsplit
from unittest import TestCase
from unittest.mock import patch

from config import settings
from database import engine, init_db, check_db_health, get_db_context
from models.db_models import RepositoryRecord, ConversationTurnRecord, PRReviewRecord, AuditReportRecord
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, Dependency, ArchitectureSummary,
    PRReviewResponse, PRSummary, RiskAssessment, AuditReport, ContributionOpportunity
)
from services.repository_persistence import repository_persistence
from services.conversation_service import ConversationService
from server import app
from fastapi.testclient import TestClient


class TestPostgresPersistence(TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure tables are created
        init_db()

    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)
        self.test_session_id = "test_postgres_session_1"

    def tearDown(self):
        # Clean up test records
        try:
            with get_db_context() as db:
                db.query(RepositoryRecord).filter(RepositoryRecord.session_id == self.test_session_id).delete()
                db.query(ConversationTurnRecord).filter(ConversationTurnRecord.session_id == self.test_session_id).delete()
                db.query(PRReviewRecord).filter(PRReviewRecord.session_id == self.test_session_id).delete()
                db.query(AuditReportRecord).filter(AuditReportRecord.session_id == self.test_session_id).delete()
        except Exception:
            pass

    def test_01_database_health_check(self):
        """Verify check_db_health connects to PostgreSQL, returns latency and masked info."""
        health = check_db_health()
        self.assertEqual(health["status"], "healthy")
        self.assertIn("latency_ms", health)
        self.assertGreaterEqual(health["latency_ms"], 0.0)
        self.assertIn("provider", health)
        # Verify no credentials leaked
        db_pass = getattr(urlsplit(settings.DATABASE_URL), "password", None)
        if db_pass:
            self.assertNotIn(db_pass, str(health))
        self.assertIn("****", health.get("database", ""))

    def test_02_connection_pooling_configuration(self):
        """Verify SQLAlchemy engine is configured with connection pooling and pre-ping for Neon."""
        self.assertTrue(engine.pool._pre_ping)
        self.assertEqual(settings.DB_POOL_SIZE, 10)
        self.assertEqual(settings.DB_MAX_OVERFLOW, 20)
        self.assertEqual(settings.DB_POOL_RECYCLE, 300)

    def test_03_repository_persistence_roundtrip(self):
        """Verify saving and restoring a RepositoryIndex with files, symbols, and architecture."""
        symbols = [
            Symbol(name="AuthService", type="class", line_number=10),
            Symbol(name="login", type="function", line_number=15),
        ]
        deps = [
            Dependency(
                source_path="services/auth.py",
                target_path="jwt",
                import_statement="import jwt",
                is_internal=False
            )
        ]
        files = [
            FileInfo(
                full_path="/workspace/test-postgres-repo/services/auth.py",
                relative_path="services/auth.py",
                file_name="auth.py",
                language="Python",
                last_modified="2026-09-28",
                lines_of_code=120,
                symbols=symbols,
                dependencies=deps,
                activity_score=0.85,
                module_category="core",
                is_entry_point=True
            )
        ]
        arch_summary = ArchitectureSummary(
            core_modules=["services/auth.py"],
            leaf_utility_modules=[],
            circular_dependencies_count=0
        )
        sample_repo = RepositoryIndex(
            repo_name="test-postgres-repo",
            repo_path="/workspace/test-postgres-repo",
            total_files=1,
            total_lines=120,
            languages_breakdown={"Python": 100},
            entry_points=["services/auth.py"],
            module_counts={"core": 1},
            circular_cycles=[],
            architecture_summary=arch_summary,
            files=files
        )

        # Save to PostgreSQL
        saved = repository_persistence.save_repository(self.test_session_id, sample_repo)
        self.assertTrue(saved)

        # Load from PostgreSQL
        loaded_repo = repository_persistence.load_repository(self.test_session_id)
        self.assertIsNotNone(loaded_repo)
        self.assertEqual(loaded_repo.repo_name, "test-postgres-repo")
        self.assertEqual(loaded_repo.total_files, 1)
        self.assertEqual(loaded_repo.total_lines, 120)
        self.assertEqual(loaded_repo.languages_breakdown.get("Python"), 100)
        self.assertEqual(len(loaded_repo.files), 1)
        self.assertEqual(loaded_repo.files[0].relative_path, "services/auth.py")
        self.assertEqual(len(loaded_repo.files[0].symbols), 2)
        self.assertEqual(loaded_repo.files[0].symbols[0].name, "AuthService")

    def test_04_repository_list_and_delete(self):
        """Verify list_repositories and delete_repository operations."""
        sample_repo = RepositoryIndex(
            repo_name="list-test-repo",
            repo_path="/tmp/list-test",
            total_files=5,
            total_lines=500,
            files=[]
        )
        repository_persistence.save_repository(self.test_session_id, sample_repo)

        repos = repository_persistence.list_repositories()
        session_ids = [r["session_id"] for r in repos]
        self.assertIn(self.test_session_id, session_ids)

        deleted = repository_persistence.delete_repository(self.test_session_id)
        self.assertTrue(deleted)
        self.assertIsNone(repository_persistence.load_repository(self.test_session_id))

    def test_05_conversation_history_persistence(self):
        """Verify chat turns are saved to PostgreSQL and restored in new service instances."""
        conv1 = ConversationService()
        conv1.add_turn(self.test_session_id, "user", "What is the entry point?")
        conv1.add_turn(self.test_session_id, "assistant", "The entry point is server.py.")

        # Simulate fresh server restart by creating a new ConversationService with empty in-memory cache
        conv2 = ConversationService()
        history = conv2.get_history(self.test_session_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "What is the entry point?")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "The entry point is server.py.")

        # Test clear_history deletes from PostgreSQL
        cleared = conv2.clear_history(self.test_session_id)
        self.assertTrue(cleared)
        self.assertEqual(conv2.get_history(self.test_session_id), [])

    def test_06_health_endpoint_includes_database_status(self):
        """Verify /api/health includes database connection status without exposing passwords."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("database", data)
        self.assertEqual(data["database"]["status"], "healthy")
        db_pass = getattr(urlsplit(settings.DATABASE_URL), "password", None)
        if db_pass:
            self.assertNotIn(db_pass, res.text)

    def test_07_pr_review_persistence(self):
        """Verify PR review persistence properly populates verdict, risks_count, and summaries."""
        sample_review = PRReviewResponse(
            verdict="REQUEST_CHANGES",
            summary=PRSummary(
                title="Refactor Auth Handler",
                executive_summary="Security review detected potential vulnerabilities.",
                developer_summary="Changes made to auth.py require remediation.",
                risk_level="High"
            ),
            risks=[
                RiskAssessment(
                    risk_id="R-1",
                    title="Insecure Token Validation",
                    category="security",
                    severity="High",
                    file_path="services/auth.py"
                ),
                RiskAssessment(
                    risk_id="R-2",
                    title="Missing Exception Logging",
                    category="maintainability",
                    severity="Medium",
                    file_path="services/auth.py"
                )
            ]
        )

        saved = repository_persistence.save_pr_review(
            session_id=self.test_session_id,
            review=sample_review,
            title="Refactor Auth Handler"
        )
        self.assertTrue(saved)

        with get_db_context() as db:
            record = db.query(PRReviewRecord).filter(
                PRReviewRecord.session_id == self.test_session_id
            ).first()
            self.assertIsNotNone(record)
            self.assertEqual(record.verdict, "REQUEST_CHANGES")
            self.assertEqual(record.risks_count, 2)
            self.assertEqual(record.title, "Refactor Auth Handler")
            self.assertEqual(record.executive_summary, "Security review detected potential vulnerabilities.")
            self.assertEqual(record.developer_summary, "Changes made to auth.py require remediation.")
            self.assertIsInstance(record.full_analysis, dict)
            self.assertEqual(record.full_analysis.get("verdict"), "REQUEST_CHANGES")

    def test_08_audit_report_persistence(self):
        """Verify audit report persistence properly populates total_opportunities, severity counts, and narrative."""
        sample_report = AuditReport(
            repo_name="sample-audit-repo",
            total_opportunities=3,
            critical_count=1,
            high_count=2,
            medium_count=0,
            low_count=0,
            summary_narrative="Audit found 1 critical and 2 high contribution opportunities.",
            opportunities=[
                ContributionOpportunity(
                    opportunity_id="OPP-1",
                    title="Fix SQL injection risk",
                    category="security",
                    priority="critical",
                    target_files=["database.py"]
                )
            ]
        )

        saved = repository_persistence.save_audit_report(
            session_id=self.test_session_id,
            report=sample_report
        )
        self.assertTrue(saved)

        with get_db_context() as db:
            record = db.query(AuditReportRecord).filter(
                AuditReportRecord.session_id == self.test_session_id
            ).first()
            self.assertIsNotNone(record)
            self.assertEqual(record.repo_name, "sample-audit-repo")
            self.assertEqual(record.total_opportunities, 3)
            self.assertEqual(record.critical_count, 1)
            self.assertEqual(record.high_count, 2)
            self.assertEqual(record.medium_count, 0)
            self.assertEqual(record.low_count, 0)
            self.assertEqual(record.summary_narrative, "Audit found 1 critical and 2 high contribution opportunities.")
            self.assertIsInstance(record.report_data, dict)
            self.assertEqual(record.report_data.get("total_opportunities"), 3)

    def test_09_database_migration_schema_alignment(self):
        """Verify inspector finds all required columns in Neon database schema."""
        from sqlalchemy import inspect
        insp = inspect(engine)

        pr_cols = [c["name"] for c in insp.get_columns("pr_reviews")]
        self.assertIn("verdict", pr_cols)
        self.assertIn("risks_count", pr_cols)

        audit_cols = [c["name"] for c in insp.get_columns("audit_reports")]
        self.assertIn("total_opportunities", audit_cols)
        self.assertIn("critical_count", audit_cols)
        self.assertIn("high_count", audit_cols)
        self.assertIn("medium_count", audit_cols)
        self.assertIn("low_count", audit_cols)
        self.assertIn("summary_narrative", audit_cols)


if __name__ == "__main__":
    import unittest
    unittest.main()
