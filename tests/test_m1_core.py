import sys
import os
import unittest
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.repo_service import repo_service
from models.repository_index import RepositoryIndex, FileInfo, Symbol

class TestEnhancedDependencyGraphCore(unittest.TestCase):

    def test_parse_local_onboarding_repository_graph_metrics(self):
        """Test dependency graph metrics (in_degree, out_degree, circular flags)."""
        target = str(Path(__file__).parent.parent.resolve())
        success, repo_index, err_msg = repo_service.parse_repository(target)
        
        self.assertTrue(success, f"Failed to parse repository: {err_msg}")
        self.assertIsNotNone(repo_index)
        
        # Verify graph structure payload
        graph_data = repo_index.dependency_graph
        self.assertIn("nodes", graph_data)
        self.assertIn("edges", graph_data)
        self.assertGreater(len(graph_data["nodes"]), 0)

        # Check in_degree & out_degree on FileInfo objects
        for f in repo_index.files:
            self.assertGreaterEqual(f.in_degree, 0)
            self.assertGreaterEqual(f.out_degree, 0)
            self.assertIsInstance(f.is_circular, bool)

        # Print centrality report
        top_in_degree = sorted(repo_index.files, key=lambda f: f.in_degree, reverse=True)[:3]
        print(f"\n[PASS] Dependency graph extracted successfully for onboarding repository!")
        print(f"       Total nodes: {len(graph_data['nodes'])}, edges: {len(graph_data['edges'])}")
        print(f"       Top central modules (In-Degree): {[f.relative_path for f in top_in_degree]}")

    def test_parse_persistent_multiagent_graph_metrics(self):
        """Test dependency graph metrics on Persistent Multi-Agent Workflow repository."""
        target = r"d:\Persistent Multi-Agent Workflow"
        if not os.path.exists(target):
            self.skipTest("Persistent Multi-Agent Workflow directory does not exist on disk.")
            
        success, repo_index, err_msg = repo_service.parse_repository(target)
        
        self.assertTrue(success, f"Failed to parse repository: {err_msg}")
        self.assertIsNotNone(repo_index)
        
        graph_data = repo_index.dependency_graph
        self.assertGreater(len(graph_data["nodes"]), 0)
        self.assertGreater(len(graph_data["edges"]), 0)

        print(f"\n[PASS] Persistent Multi-Agent Workflow graph metrics verified!")
        print(f"       Total nodes: {len(graph_data['nodes'])}, edges: {len(graph_data['edges'])}")

if __name__ == "__main__":
    unittest.main()
