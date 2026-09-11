import sys
import os
import unittest
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.repo_service import repo_service
from models.repository_index import RepositoryIndex, FileInfo, Symbol

class TestM1RepositoryIntelligenceCore(unittest.TestCase):

    def test_parse_local_onboarding_repository(self):
        """Test M1 core on local onboarding repository."""
        target = str(Path(__file__).parent.parent.resolve())
        success, repo_index, err_msg = repo_service.parse_repository(target)
        
        self.assertTrue(success, f"Failed to parse repository: {err_msg}")
        self.assertIsNotNone(repo_index)
        self.assertIsInstance(repo_index, RepositoryIndex)
        
        # Check basic stats
        self.assertGreater(repo_index.total_files, 0)
        self.assertGreater(repo_index.total_lines, 0)
        
        # Check entry point detection
        self.assertIsInstance(repo_index.entry_points, list)
        self.assertGreater(len(repo_index.entry_points), 0, "No entry points detected.")
        print(f"\n[PASS] Local onboarding repository index created successfully!")
        print(f"       Files: {repo_index.total_files}, Lines: {repo_index.total_lines}")
        print(f"       Entry points detected: {repo_index.entry_points}")
        print(f"       Languages: {repo_index.languages_breakdown}")

    def test_parse_persistent_multiagent_repository(self):
        """Test M1 core on Persistent Multi-Agent Workflow repository."""
        target = r"d:\Persistent Multi-Agent Workflow"
        if not os.path.exists(target):
            self.skipTest("Persistent Multi-Agent Workflow directory does not exist on disk.")
            
        success, repo_index, err_msg = repo_service.parse_repository(target)
        
        self.assertTrue(success, f"Failed to parse repository: {err_msg}")
        self.assertIsNotNone(repo_index)
        self.assertIsInstance(repo_index, RepositoryIndex)
        
        # Verify symbol parsing
        server_file = next((f for f in repo_index.files if f.file_name == "server.py"), None)
        self.assertIsNotNone(server_file, "server.py not found in index.")
        self.assertGreater(len(server_file.symbols), 0, "No symbols parsed for server.py")
        
        # Verify normalized Git activity scores (0-100)
        for f in repo_index.files:
            self.assertGreaterEqual(f.activity_score, 0.0)
            self.assertLessEqual(f.activity_score, 100.0)

        print(f"\n[PASS] Persistent Multi-Agent Workflow index created successfully!")
        print(f"       Files: {repo_index.total_files}, Lines: {repo_index.total_lines}")
        print(f"       Detected entry points: {repo_index.entry_points}")

    def test_symbol_and_dependency_models(self):
        """Test Pydantic model validation on mock data."""
        sym = Symbol(
            name="test_func",
            type="function",
            line_number=10,
            parameters=["req", "config"],
            docstring="Test docstring"
        )
        self.assertEqual(sym.name, "test_func")
        self.assertEqual(sym.parameters, ["req", "config"])

if __name__ == "__main__":
    unittest.main()
