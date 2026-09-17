import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from config import settings
from models.repository_index import AgentState, RepositoryIndex, SourceAttribution, ToolCall, ToolResult
from server import ACTIVE_SESSIONS, app
from services.agent.agent import agent_service
from services.agent.planner import AgentPlanner
from services.agent.tool_executor import ToolExecutor
from services.agent.tools import build_repository_tool_registry
from services.groq_service import groq_service
from services.repo_service import repo_service


class TestAgenticRepositoryExploration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.success, cls.repo_index, cls.err_msg = repo_service.parse_repository(str(ROOT_DIR))
        if cls.success and cls.repo_index:
            ACTIVE_SESSIONS["default"] = cls.repo_index
        cls.client = TestClient(app)

    def setUp(self):
        self.assertTrue(self.success, self.err_msg)
        self.registry = build_repository_tool_registry(self.repo_index)
        self.executor = ToolExecutor(self.registry)
        self.groq_chat_patch = patch.object(
            groq_service,
            "chat_with_repository",
            return_value="Grounded answer from collected agent evidence."
        )
        self.groq_chat_patch.start()
        self.key_patch = patch.object(settings, "GROQ_API_KEY", "")
        self.key_patch.start()

    def tearDown(self):
        self.groq_chat_patch.stop()
        self.key_patch.stop()

    def test_01_search_repository_tool(self):
        result = self.registry.get("search_repository").handler(query="repo service parsing", limit=5)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["results"]), 0)
        self.assertIn("file_path", result["results"][0])

    def test_02_get_file_tool(self):
        result = self.registry.get("get_file").handler(file_path="services/repo_service.py")
        self.assertTrue(result["success"])
        self.assertEqual(result["file_path"], "services/repo_service.py")
        self.assertIn("class RepoService", result["content"])

    def test_03_get_symbol_tool(self):
        result = self.registry.get("get_symbol").handler(
            file_path="services/repo_service.py",
            symbol_name="RepoService"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["symbol"]["name"], "RepoService")
        self.assertGreater(result["symbol"]["line_number"], 0)

    def test_04_find_references_tool(self):
        result = self.registry.get("find_references").handler(symbol_name="parse_repository", limit=10)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["references"]), 0)

    def test_05_get_dependencies_tool(self):
        result = self.registry.get("get_dependencies").handler(file_path="server.py")
        self.assertTrue(result["success"])
        self.assertIn("dependencies", result)
        self.assertTrue(any(dep["is_internal"] for dep in result["dependencies"]))

    def test_06_get_dependants_tool(self):
        result = self.registry.get("get_dependants").handler(file_path="services/repo_service.py")
        self.assertTrue(result["success"])
        self.assertGreater(len(result["dependants"]), 0)

    def test_07_find_entry_points_tool(self):
        result = self.registry.get("find_entry_points").handler()
        self.assertTrue(result["success"])
        self.assertTrue(any("server.py" in item["file_path"] or "app.py" in item["file_path"] for item in result["entry_points"]))

    def test_08_find_tests_tool(self):
        result = self.registry.get("find_tests").handler(file_path="services/repo_service.py")
        self.assertTrue(result["success"])
        self.assertGreater(len(result["tests"]), 0)

    def test_09_get_architecture_tool(self):
        result = self.registry.get("get_architecture").handler()
        self.assertTrue(result["success"])
        self.assertIn("architecture_summary", result)
        self.assertGreater(result["total_files"], 0)

    def test_10_get_git_activity_tool(self):
        result = self.registry.get("get_git_activity").handler(limit=3)
        self.assertTrue(result["success"])
        self.assertLessEqual(len(result["files"]), 3)

    def test_11_registry_exposes_clear_schemas(self):
        schemas = self.registry.schemas()
        self.assertGreaterEqual(len(schemas), 10)
        self.assertTrue(all("name" in schema and "schema" in schema for schema in schemas))

    def test_12_initial_plan_generation(self):
        planner = AgentPlanner()
        plan = planner.create_initial_plan("How does an API request flow through this repository?", self.registry.schemas())
        self.assertGreater(len(plan), 1)
        self.assertTrue(any("entry" in step.lower() or "api" in step.lower() for step in plan))

    def test_13_tool_selection_initial(self):
        planner = AgentPlanner()
        state = AgentState(user_query="Where is repo parsing handled?")
        call = planner.select_next_tool(state, self.registry)
        self.assertIsNotNone(call)
        self.assertEqual(call.tool_name, "search_repository")

    def test_14_dynamic_replanning_after_observation(self):
        planner = AgentPlanner()
        state = AgentState(user_query="Where is repo parsing handled?")
        state.tool_calls.append(ToolCall(call_id="call_1", tool_name="search_repository", arguments={"query": state.user_query, "limit": 8}))
        state.observations.append(ToolResult(
            call_id="call_1",
            tool_name="search_repository",
            success=True,
            data={"results": [{"file_path": "services/repo_service.py", "matched_symbols": ["RepoService() [class]"]}]}
        ))
        call = planner.select_next_tool(state, self.registry)
        self.assertEqual(call.tool_name, "get_file")
        self.assertEqual(call.arguments["file_path"], "services/repo_service.py")

    def test_15_different_questions_produce_different_investigations(self):
        planner = AgentPlanner()
        api_call = planner.select_next_tool(AgentState(user_query="How does an API request flow?"), self.registry)
        test_call = planner.select_next_tool(AgentState(user_query="What tests cover repo_service?"), self.registry)
        self.assertNotEqual(api_call.tool_name, test_call.tool_name)

    def test_16_single_step_investigation(self):
        response = agent_service.explore("Where is repo parsing handled?", self.repo_index, max_iterations=1)
        self.assertEqual(response.iterations, 1)
        self.assertTrue(response.metadata["limited"])

    def test_17_multi_step_investigation(self):
        response = agent_service.explore("Where is repo parsing handled?", self.repo_index, max_iterations=5)
        self.assertGreater(response.iterations, 1)
        self.assertGreater(len(response.tools_used), 1)

    def test_18_observation_updates_state(self):
        state = AgentState(user_query="repo parsing")
        result = ToolResult(
            call_id="call_1",
            tool_name="get_file",
            success=True,
            data={"file_path": "services/repo_service.py", "language": "python", "module_category": "core", "symbols": [{"name": "RepoService"}]}
        )
        agent_service._absorb_observation(state, result)
        self.assertIn("services/repo_service.py", state.discovered_files)
        self.assertIn("RepoService", state.discovered_symbols)

    def test_19_agent_stops_when_sufficient_evidence_exists(self):
        response = agent_service.explore("Explain repository architecture dependencies", self.repo_index, max_iterations=8)
        self.assertLessEqual(response.iterations, 8)
        self.assertGreater(len(response.sources), 0)

    def test_20_maximum_iteration_limit(self):
        response = agent_service.explore("Explain repo parsing and dependency graph", self.repo_index, max_iterations=1)
        self.assertEqual(response.metadata["limit_reason"], "maximum iteration limit reached")

    def test_21_maximum_tool_call_limit(self):
        response = agent_service.explore("Explain repo parsing and dependency graph", self.repo_index, max_tool_calls=1)
        self.assertEqual(response.metadata["limit_reason"], "maximum tool-call limit reached")

    def test_22_duplicate_tool_call_prevention(self):
        planner = AgentPlanner()
        state = AgentState(user_query="Where is repo parsing handled?")
        state.tool_calls.append(ToolCall(call_id="call_1", tool_name="search_repository", arguments={"query": state.user_query, "limit": 8}))
        call = planner.select_next_tool(state, self.registry)
        self.assertNotEqual(call.arguments, {"query": state.user_query, "limit": 8})

    def test_23_evidence_preserved(self):
        response = agent_service.explore("Where is RepoService defined?", self.repo_index, max_iterations=4)
        self.assertGreater(len(response.findings), 0)

    def test_24_sources_included(self):
        response = agent_service.explore("Where is RepoService defined?", self.repo_index, max_iterations=4)
        self.assertGreater(len(response.sources), 0)
        self.assertIsInstance(response.sources[0], SourceAttribution)

    def test_25_unsupported_claims_rejected_when_no_evidence(self):
        response = agent_service.explore(f"runtime_missing_{uuid.uuid4().hex}", self.repo_index, max_iterations=1, max_tool_calls=1)
        self.assertIn("could not establish", response.answer.lower())

    def test_26_existing_source_attribution_model_reused(self):
        response = agent_service.explore("Where is RepoService defined?", self.repo_index, max_iterations=4)
        self.assertTrue(all(isinstance(source, SourceAttribution) for source in response.sources))

    def test_27_tool_failure_invalid_file(self):
        call = ToolCall(call_id="bad", tool_name="get_file", arguments={"file_path": "../outside.py"})
        result = self.executor.execute(call)
        self.assertFalse(result.success)
        self.assertIn("not part of the repository index", result.error)

    def test_28_invalid_tool_arguments(self):
        call = ToolCall(call_id="bad", tool_name="search_repository", arguments={})
        result = self.executor.execute(call)
        self.assertFalse(result.success)

    def test_29_malformed_llm_response_falls_back(self):
        with patch.object(settings, "GROQ_API_KEY", "test-key"):
            with patch.object(groq_service, "_call_groq_api", return_value="not json"):
                planner = AgentPlanner()
                plan = planner.create_initial_plan("How does the API flow?", self.registry.schemas())
        self.assertGreater(len(plan), 0)

    def test_30_groq_unavailable_fallback_answer(self):
        with patch.object(groq_service, "chat_with_repository", return_value="Groq API Key missing"):
            response = agent_service.explore("Where is RepoService defined?", self.repo_index, max_iterations=4)
        self.assertIn("Repository evidence", response.answer)

    def test_31_repository_not_loaded_service_error(self):
        with self.assertRaises(ValueError):
            agent_service.explore("What is this?", None)

    def test_32_repository_not_loaded_api_error(self):
        res = self.client.post("/api/agent/explore", json={"query": "What is this?", "session_id": "missing"})
        self.assertEqual(res.status_code, 404)

    def test_33_empty_repository_error(self):
        empty = RepositoryIndex(repo_name="empty", repo_path=str(ROOT_DIR), files=[])
        with self.assertRaises(ValueError):
            agent_service.explore("Anything here?", empty)

    def test_34_security_no_dangerous_tools_registered(self):
        names = set(self.registry.names())
        self.assertNotIn("execute_shell", names)
        self.assertNotIn("run_python", names)
        self.assertNotIn("modify_file", names)

    def test_35_security_cannot_access_arbitrary_path(self):
        with self.assertRaises(ValueError):
            self.registry.get("get_file").handler(file_path=str(ROOT_DIR.parent / "secret.py"))

    def test_36_agent_api_contract(self):
        ACTIVE_SESSIONS["default"] = self.repo_index
        res = self.client.post("/api/agent/explore", json={
            "query": "Where is RepoService defined?",
            "session_id": "default",
            "max_iterations": 3
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("answer", data)
        self.assertIn("sources", data)
        self.assertIn("findings", data)
        self.assertIn("trace", data)
        self.assertIn("tools_used", data)


if __name__ == "__main__":
    unittest.main()
