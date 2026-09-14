import sys
import os
import unittest
from pathlib import Path

# Add root directory to sys.path
ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from server import app, ACTIVE_SESSIONS
from services.repo_service import repo_service
from services.retrieval_service import (
    QueryAnalyzer, RepositoryRetriever, DependencyExpander, ContextBuilder, retrieval_engine
)
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, ScoredFile, QueryAnalysis, RetrievedContextPayload
)

class TestContextRetrievalEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.target = str(ROOT_DIR)
        cls.success, cls.repo_index, cls.err_msg = repo_service.parse_repository(cls.target)
        if cls.success and cls.repo_index:
            ACTIVE_SESSIONS["default"] = cls.repo_index
        cls.client = TestClient(app)

    def test_query_analyzer(self):
        """Test QueryAnalyzer tokenization, stop word filtering, and concept expansion."""
        analyzer = QueryAnalyzer()
        qa = analyzer.analyze("Where is database initialization handled?")
        
        self.assertIn("database", qa.normalized_terms)
        self.assertIn("initialization", qa.normalized_terms)
        self.assertNotIn("where", qa.normalized_terms)
        self.assertNotIn("is", qa.normalized_terms)
        self.assertNotIn("handled", qa.normalized_terms)
        
        # Check concept expansion (db -> sql, models, schema)
        self.assertTrue(any(c in qa.expanded_concepts for c in ["db", "models", "init", "setup"]))

    def test_relevance_scoring_and_explainability(self):
        """Test RepositoryRetriever relevance scoring and explainable signal breakdown."""
        retriever = RepositoryRetriever()
        analyzer = QueryAnalyzer()
        qa = analyzer.analyze("How is repo parsing and dependency graph built?")

        scored_files = []
        for f in self.repo_index.files:
            sf = retriever.score_file(f, qa, self.target)
            if sf.total_score > 0:
                scored_files.append(sf)

        self.assertGreater(len(scored_files), 0)
        scored_files.sort(key=lambda x: x.total_score, reverse=True)
        
        # Check that top candidates have signals and explanations
        top_file = scored_files[0]
        self.assertGreater(top_file.total_score, 0)
        self.assertGreater(len(top_file.signals), 0)
        self.assertGreater(len(top_file.match_explanations), 0)

        # Check explainability details
        for match in top_file.match_explanations:
            self.assertIsNotNone(match.signal_type)
            self.assertGreater(match.score, 0)
            self.assertIsInstance(match.details, str)

    def test_dependency_aware_expansion(self):
        """Test DependencyExpander adding related upstream/downstream files from M2 graph."""
        retriever = RepositoryRetriever()
        expander = DependencyExpander()
        analyzer = QueryAnalyzer()
        qa = analyzer.analyze("config settings")

        _, primary = retriever.retrieve(self.repo_index, "config settings", top_n=3)
        self.assertGreater(len(primary), 0)

        expanded = expander.expand(primary, self.repo_index, max_related_files=3)
        self.assertGreaterEqual(len(expanded), len(primary))

        # Verify expansion tags
        has_expansion = any(sf.is_expanded_dependency for sf in expanded)
        if len(expanded) > len(primary):
            self.assertTrue(has_expansion)
            for sf in expanded:
                if sf.is_expanded_dependency:
                    self.assertIsNotNone(sf.expansion_reason)

    def test_context_builder_formatting(self):
        """Test ContextBuilder output Markdown formatting and token budget truncation."""
        engine = retrieval_engine
        payload = engine.process_query(
            repo_index=self.repo_index,
            query="FastAPI routes server endpoints",
            max_files=5
        )

        self.assertIsInstance(payload, RetrievedContextPayload)
        self.assertEqual(payload.repo_name, self.repo_index.repo_name)
        self.assertGreater(len(payload.formatted_context), 0)
        self.assertIn("# Repository Context for Developer Question", payload.formatted_context)
        self.assertGreater(payload.estimated_tokens, 0)

    def test_fastapi_retrieve_endpoint(self):
        """Test POST /api/retrieve REST endpoint."""
        res = self.client.post("/api/retrieve", json={
            "query": "Where is repo parsing done?",
            "max_files": 5,
            "expand_dependencies": True
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("repo_name", data)
        self.assertIn("scored_files", data)
        self.assertIn("formatted_context", data)
        self.assertGreater(len(data["scored_files"]), 0)

    def test_fastapi_chat_with_retrieval_context(self):
        """Test POST /api/chat utilizing retrieval engine context."""
        res = self.client.post("/api/chat", json={
            "question": "What does repo_service do?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("answer", data)
        self.assertIsInstance(data["answer"], str)

if __name__ == "__main__":
    unittest.main()
