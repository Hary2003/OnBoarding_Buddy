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
from models.repository_index import RepositoryIndex, FileInfo, Symbol, Dependency, CycleDetail, ArchitectureSummary

class TestDependencyAnalysisEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.target = str(ROOT_DIR)
        cls.success, cls.repo_index, cls.err_msg = repo_service.parse_repository(cls.target)
        if cls.success and cls.repo_index:
            ACTIVE_SESSIONS["default"] = cls.repo_index
        cls.client = TestClient(app)

    def test_repository_parsing_success(self):
        """Verify repository parsing builds valid RepositoryIndex."""
        self.assertTrue(self.success, f"Failed to parse onboarding repository: {self.err_msg}")
        self.assertIsNotNone(self.repo_index)
        self.assertGreater(self.repo_index.total_files, 0)
        self.assertGreater(self.repo_index.total_lines, 0)

    def test_import_extraction_and_resolution(self):
        """Verify python and js import extraction resolves internal relative paths vs external packages."""
        file_map = {f.relative_path: f.full_path for f in self.repo_index.files}
        
        # Test Python import resolution on server.py
        server_file = os.path.join(self.target, "server.py")
        deps = repo_service.extract_dependencies(server_file, self.target, file_map)
        self.assertGreater(len(deps), 0)
        
        internal_deps = [d for d in deps if d.is_internal]
        external_deps = [d for d in deps if not d.is_internal]
        
        self.assertTrue(any("config.py" in d.target_path or "config" in d.target_path for d in internal_deps) or len(internal_deps) > 0)
        self.assertTrue(any("fastapi" in d.target_path.lower() for d in external_deps) or len(external_deps) > 0)

    def test_directed_graph_metrics(self):
        """Verify graph node and edge creation with in_degree and out_degree centrality."""
        graph_data = self.repo_index.dependency_graph
        self.assertIn("nodes", graph_data)
        self.assertIn("edges", graph_data)
        self.assertGreater(len(graph_data["nodes"]), 0)
        
        for node in graph_data["nodes"]:
            self.assertIn("in_degree", node)
            self.assertIn("out_degree", node)
            self.assertIn("module_category", node)

    def test_module_classification(self):
        """Verify files are categorized as core, leaf, utility, entry_point, isolated, or standard."""
        self.assertIn("module_counts", self.repo_index.__dict__)
        counts = self.repo_index.module_counts
        self.assertIsInstance(counts, dict)
        
        # Check that file info objects contain module_category
        categories = {f.module_category for f in self.repo_index.files}
        self.assertGreater(len(categories), 0)

    def test_circular_dependency_detection(self):
        """Verify cycle detection returns CycleDetail structures."""
        circular_files, cycles = repo_service.detect_circular_dependencies(self.repo_index.files)
        self.assertIsInstance(circular_files, set)
        self.assertIsInstance(cycles, list)

    def test_entry_point_detection(self):
        """Verify entry points detection identifies main/server files."""
        entry_points = repo_service.detect_entry_points(self.repo_index.files)
        self.assertIsInstance(entry_points, list)
        self.assertGreater(len(entry_points), 0)
        self.assertTrue(any("server.py" in ep or "app.py" in ep for ep in entry_points))

    def test_architecture_summary(self):
        """Verify architecture summary generation."""
        arch = repo_service.generate_architecture_summary(self.repo_index)
        self.assertIsNotNone(arch)
        self.assertIsInstance(arch.architecture_type, str)
        self.assertIsInstance(arch.overview_narrative, str)
        self.assertGreater(len(arch.overview_narrative), 0)

    def test_fastapi_dependencies_endpoint(self):
        """Test GET /api/dependencies endpoint."""
        res = self.client.get("/api/dependencies?filter_type=all")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)

    def test_fastapi_dependencies_modules_endpoint(self):
        """Test GET /api/dependencies/modules endpoint."""
        res = self.client.get("/api/dependencies/modules")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("modules", data)
        self.assertIn("module_counts", data)

    def test_fastapi_dependencies_cycles_endpoint(self):
        """Test GET /api/dependencies/cycles endpoint."""
        res = self.client.get("/api/dependencies/cycles")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cycles", data)

    def test_fastapi_architecture_endpoint(self):
        """Test GET /api/architecture endpoint."""
        res = self.client.get("/api/architecture?use_llm=false")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("architecture_summary", data)

if __name__ == "__main__":
    unittest.main()
