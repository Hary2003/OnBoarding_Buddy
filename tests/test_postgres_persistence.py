import os
from unittest import TestCase
from unittest.mock import patch

from config import settings
from database import engine, init_db, check_db_health, get_db_context
from models.db_models import RepositoryRecord, ConversationTurnRecord, PRReviewRecord, AuditReportRecord
from models.repository_index import RepositoryIndex, FileInfo, Symbol, Dependency, ArchitectureSummary
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
        self.assertNotIn("npg_Crm5wavGTc1Q", str(health))
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
        self.assertNotIn("npg_Crm5wavGTc1Q", res.text)


if __name__ == "__main__":
    import unittest
    unittest.main()
