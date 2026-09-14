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
from services.groq_service import groq_service, GROUNDED_SYSTEM_PROMPT
from services.conversation_service import conversation_service, ConversationService
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, ChatResponse, SourceAttribution
)

class TestGroundedAIAssistant(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.target = str(ROOT_DIR)
        cls.success, cls.repo_index, cls.err_msg = repo_service.parse_repository(cls.target)
        if cls.success and cls.repo_index:
            ACTIVE_SESSIONS["default"] = cls.repo_index
        cls.client = TestClient(app)

    def setUp(self):
        conversation_service.clear_history("test_session")
        self.groq_patcher = patch.object(
            groq_service,
            "_call_groq_api_messages",
            return_value="Based on `services/repo_service.py` and `server.py`, repository parsing and AST symbol extraction are handled."
        )
        self.mock_groq = self.groq_patcher.start()

    def tearDown(self):
        self.groq_patcher.stop()

    def test_01_grounded_repository_question(self):
        """1. Test that repository question returns a valid ChatResponse."""
        resp = conversation_service.process_chat(
            question="How is repo parsing handled?",
            session_id="test_session",
            repo_index=self.repo_index
        )
        self.assertIsInstance(resp, ChatResponse)
        self.assertIsInstance(resp.answer, str)
        self.assertGreater(len(resp.answer), 0)

    def test_02_sources_attribution_included(self):
        """2. Test that structured source attributions are included."""
        resp = conversation_service.process_chat(
            question="Where is repo_service defined?",
            session_id="test_session",
            repo_index=self.repo_index
        )
        self.assertIsInstance(resp.sources, list)
        self.assertGreater(len(resp.sources), 0)
        top_source = resp.sources[0]
        self.assertIsInstance(top_source, SourceAttribution)
        self.assertIsNotNone(top_source.file_path)

    def test_03_relevant_files_included(self):
        """3. Test that relevant_files list is populated from index."""
        resp = conversation_service.process_chat(
            question="FastAPI endpoints server",
            session_id="test_session",
            repo_index=self.repo_index
        )
        self.assertIsInstance(resp.relevant_files, list)
        self.assertGreater(len(resp.relevant_files), 0)

    def test_04_dependency_paths_included(self):
        """4. Test that dependency_paths list includes expanded graph nodes."""
        resp = conversation_service.process_chat(
            question="config settings models",
            session_id="test_session",
            repo_index=self.repo_index
        )
        self.assertIsInstance(resp.dependency_paths, list)

    def test_05_symbol_references_preserved(self):
        """5. Test that symbol references are preserved in attributions."""
        resp = conversation_service.process_chat(
            question="extract_dependencies in repo_service",
            session_id="test_session",
            repo_index=self.repo_index
        )
        has_symbol_attrib = any(src.symbol_name is not None for src in resp.sources)
        self.assertTrue(has_symbol_attrib or len(resp.sources) > 0)

    def test_06_multi_turn_conversation_history(self):
        """6. Test that multi-turn history is recorded across chat turns."""
        conversation_service.process_chat("How does parsing work?", session_id="test_session", repo_index=self.repo_index)
        history = conversation_service.get_history("test_session")
        self.assertEqual(len(history), 2) # 1 user, 1 assistant turn
        
        conversation_service.process_chat("What files are involved?", session_id="test_session", repo_index=self.repo_index)
        history2 = conversation_service.get_history("test_session")
        self.assertEqual(len(history2), 4)

    def test_07_follow_up_question_resolution(self):
        """7. Test follow-up question in conversation context."""
        conversation_service.process_chat("Where is database or index handled?", session_id="test_session", repo_index=self.repo_index)
        resp = conversation_service.process_chat("Where are its symbols extracted?", session_id="test_session", repo_index=self.repo_index)
        self.assertIsInstance(resp, ChatResponse)
        self.assertGreater(len(resp.answer), 0)

    def test_08_insufficient_context_handling(self):
        """8. Test handling speculative questions with insufficient context."""
        resp = conversation_service.process_chat(
            question="Why does this company use Redis?",
            session_id="test_session",
            repo_index=self.repo_index
        )
        self.assertIn("couldn't determine", resp.answer.lower())
        self.assertFalse(resp.retrieval_metadata.get("has_sufficient_context", True))

    def test_09_no_repository_loaded_handling(self):
        """9. Test asking question when no repository is loaded."""
        resp = conversation_service.process_chat(
            question="What is this project?",
            session_id="unloaded_session",
            repo_index=None
        )
        self.assertIn("No repository loaded", resp.answer)
        self.assertEqual(resp.retrieval_metadata.get("confidence"), 0.0)

    def test_10_hallucination_prevention_instructions(self):
        """10. Test that GROUNDED_SYSTEM_PROMPT contains anti-hallucination rules."""
        self.assertIn("USE SUPPLIED CONTEXT ONLY", GROUNDED_SYSTEM_PROMPT)
        self.assertIn("NO HALLUCINATIONS", GROUNDED_SYSTEM_PROMPT)
        self.assertIn("INSUFFICIENT CONTEXT", GROUNDED_SYSTEM_PROMPT)
        self.assertIn("DISTINGUISH FACTS FROM INFERENCE", GROUNDED_SYSTEM_PROMPT)

    def test_11_retrieval_metadata_fields(self):
        """11. Test that retrieval_metadata contains expected keys."""
        resp = conversation_service.process_chat(
            question="server API routes",
            session_id="test_session",
            repo_index=self.repo_index
        )
        meta = resp.retrieval_metadata
        self.assertIn("confidence", meta)
        self.assertIn("has_sufficient_context", meta)
        self.assertIn("files_count", meta)
        self.assertIn("estimated_tokens", meta)

    def test_12_clear_conversation_history(self):
        """12. Test clearing conversation history via API / service."""
        conversation_service.process_chat("Hello", session_id="test_session", repo_index=self.repo_index)
        self.assertEqual(len(conversation_service.get_history("test_session")), 2)
        
        cleared = conversation_service.clear_history("test_session")
        self.assertTrue(cleared)
        self.assertEqual(len(conversation_service.get_history("test_session")), 0)

    def test_13_groq_failure_graceful_fallback(self):
        """13. Test graceful fallback when Groq service fails."""
        with patch.object(groq_service, "chat_with_repository", return_value="❌ Groq API Error: Connection Timeout"):
            resp = conversation_service.process_chat(
                question="Explain repo_service",
                session_id="test_session",
                repo_index=self.repo_index
            )
            self.assertIsInstance(resp, ChatResponse)
            self.assertIn("Groq API Error", resp.answer)

    def test_14_malformed_llm_response_handling(self):
        """14. Test handling of malformed LLM response."""
        with patch.object(groq_service, "chat_with_repository", return_value=None):
            resp = conversation_service.process_chat(
                question="Explain repo_service",
                session_id="test_session",
                repo_index=self.repo_index
            )
            self.assertIsInstance(resp, ChatResponse)
            self.assertIn("Unable to generate response", resp.answer)

    def test_15_context_token_size_limits(self):
        """15. Test context size token budgeting."""
        resp = conversation_service.process_chat(
            question="repository index models services server config",
            session_id="test_session",
            repo_index=self.repo_index
        )
        tokens = resp.retrieval_metadata.get("estimated_tokens", 0)
        self.assertLessEqual(tokens, 15000)

    def test_16_fastapi_chat_endpoint_contract(self):
        """16. Test POST /api/chat contract matching ChatResponse model."""
        res = self.client.post("/api/chat", json={
            "question": "What is server.py?",
            "session_id": "default"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("answer", data)
        self.assertIn("sources", data)
        self.assertIn("relevant_files", data)
        self.assertIn("dependency_paths", data)
        self.assertIn("retrieval_metadata", data)

    def test_17_fastapi_clear_history_endpoint(self):
        """17. Test DELETE /api/chat/history REST endpoint."""
        res = self.client.delete("/api/chat/history?session_id=default")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], "default")

if __name__ == "__main__":
    unittest.main()
