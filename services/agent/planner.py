import json
import re
from typing import Any, Dict, List, Optional

from config import settings
from models.repository_index import AgentState, ToolCall
from services.agent.tool_executor import ToolExecutor
from services.agent.tool_registry import RepositoryToolRegistry
from services.groq_service import groq_service


class AgentPlanner:
    """Plans read-only repository investigations with an LLM-first, deterministic-fallback strategy."""

    def create_initial_plan(self, query: str, tool_schemas: List[Dict[str, Any]]) -> List[str]:
        llm_plan = self._llm_initial_plan(query, tool_schemas)
        if llm_plan:
            return llm_plan

        query_lower = query.lower()
        plan = ["Search repository evidence related to the developer question."]

        if any(term in query_lower for term in ["request", "flow", "api", "endpoint", "route", "start", "entry"]):
            plan = [
                "Find likely entry points.",
                "Search for API, router, or flow-related modules.",
                "Inspect the most relevant files and symbols.",
                "Trace dependency relationships.",
                "Find related tests.",
                "Synthesize a grounded answer."
            ]
        elif any(term in query_lower for term in ["architecture", "dependency", "dependencies", "graph", "circular"]):
            plan = [
                "Inspect the repository architecture summary.",
                "Find entry points and core modules.",
                "Inspect dependency relationships.",
                "Synthesize a grounded answer."
            ]
        elif any(term in query_lower for term in ["test", "tests", "coverage", "spec"]):
            plan = [
                "Search for the feature or module under discussion.",
                "Find related test files.",
                "Inspect relevant source and tests.",
                "Synthesize a grounded answer."
            ]
        else:
            plan.extend([
                "Inspect top matching files and symbols.",
                "Find references and dependency relationships.",
                "Check related tests where applicable.",
                "Synthesize a grounded answer."
            ])
        return plan

    def select_next_tool(self, state: AgentState, registry: RepositoryToolRegistry) -> Optional[ToolCall]:
        llm_call = self._llm_next_tool(state, registry)
        if llm_call and registry.get(llm_call.tool_name):
            return llm_call

        candidates = self._deterministic_candidates(state)
        executed = {
            ToolExecutor.normalized_signature(call.tool_name, call.arguments)
            for call in state.tool_calls
        }

        for tool_name, arguments in candidates:
            if not registry.get(tool_name):
                continue
            signature = ToolExecutor.normalized_signature(tool_name, arguments)
            if signature not in executed:
                return ToolCall(
                    call_id=f"call_{len(state.tool_calls) + 1}",
                    tool_name=tool_name,
                    arguments=arguments
                )
        return None

    def should_stop(self, state: AgentState, max_iterations: int, max_tool_calls: int, max_files: int) -> bool:
        if state.iteration >= max_iterations:
            return True
        if len(state.tool_calls) >= max_tool_calls:
            return True
        if len(state.discovered_files) >= max_files:
            return True
        if len(state.sources) >= 3 and len(state.observations) >= 4:
            return True
        if len(state.sources) >= 1 and any(obs.tool_name == "get_architecture" for obs in state.observations):
            return len(state.observations) >= 2
        return False

    def _llm_initial_plan(self, query: str, tool_schemas: List[Dict[str, Any]]) -> List[str]:
        if not settings.is_groq_configured:
            return []
        prompt = (
            "Return only JSON with a 'plan' array of concise public investigation steps. "
            "Use only these read-only repository tools as possible evidence sources:\n"
            f"{json.dumps(tool_schemas, indent=2)}\n\n"
            f"Developer question: {query}"
        )
        try:
            raw = groq_service._call_groq_api(
                "You are a repository investigation planner. Return valid JSON only. Do not include hidden reasoning.",
                prompt,
                temperature=0.1
            )
            data = self._parse_json(raw)
            plan = data.get("plan", []) if isinstance(data, dict) else []
            return [str(item)[:180] for item in plan if str(item).strip()][:8]
        except Exception:
            return []

    def _llm_next_tool(self, state: AgentState, registry: RepositoryToolRegistry) -> Optional[ToolCall]:
        if not settings.is_groq_configured:
            return None
        memory = self._planner_memory(state)
        prompt = (
            "Return only JSON for the next read-only repository tool call, or {\"finish\": true}. "
            "Allowed tools and schemas:\n"
            f"{json.dumps(registry.schemas(), indent=2)}\n\n"
            f"Investigation memory:\n{memory}"
        )
        try:
            raw = groq_service._call_groq_api(
                "You select one safe repository tool call at a time. Return valid JSON only.",
                prompt,
                temperature=0.1
            )
            data = self._parse_json(raw)
            if not isinstance(data, dict) or data.get("finish") is True:
                return None
            tool_name = data.get("tool_name")
            arguments = data.get("arguments", {})
            if isinstance(tool_name, str) and isinstance(arguments, dict):
                return ToolCall(call_id=f"call_{len(state.tool_calls) + 1}", tool_name=tool_name, arguments=arguments)
        except Exception:
            return None
        return None

    def _deterministic_candidates(self, state: AgentState) -> List[tuple[str, Dict[str, Any]]]:
        query = state.user_query
        query_lower = query.lower()
        candidates: List[tuple[str, Dict[str, Any]]] = []
        last_success = next((obs for obs in reversed(state.observations) if obs.success), None)

        if not state.tool_calls:
            if any(term in query_lower for term in ["architecture", "dependency", "dependencies", "graph", "circular"]):
                candidates.append(("get_architecture", {}))
            if any(term in query_lower for term in ["request", "flow", "api", "endpoint", "route", "entry", "start"]):
                candidates.append(("find_entry_points", {"limit": 8}))
            if any(term in query_lower for term in ["test", "tests", "coverage", "spec"]):
                candidates.append(("find_tests", {"query": query, "limit": 10}))
            candidates.append(("search_repository", {"query": query, "limit": 8}))
            return candidates

        if last_success:
            data = last_success.data
            if last_success.tool_name == "get_architecture":
                candidates.append(("find_entry_points", {"limit": 8}))
                for path in data.get("entry_points", [])[:3]:
                    candidates.append(("get_dependencies", {"file_path": path}))

            if last_success.tool_name == "find_entry_points":
                for entry in data.get("entry_points", [])[:4]:
                    path = entry.get("file_path")
                    if path:
                        candidates.append(("get_file", {"file_path": path, "max_chars": 5000}))
                        candidates.append(("get_dependencies", {"file_path": path}))
                candidates.append(("search_repository", {"query": query, "limit": 8}))

            if last_success.tool_name == "search_repository":
                for result in data.get("results", [])[:5]:
                    path = result.get("file_path")
                    if path:
                        candidates.append(("get_file", {"file_path": path, "max_chars": 5000}))
                    for sym in result.get("matched_symbols", [])[:2]:
                        clean = self._clean_symbol_name(sym)
                        if path and clean:
                            candidates.append(("get_symbol", {"file_path": path, "symbol_name": clean}))

            if last_success.tool_name == "get_file":
                path = data.get("file_path")
                symbols = data.get("symbols", [])
                matching_symbol = self._best_symbol_for_query(query, symbols)
                if path and matching_symbol:
                    candidates.append(("get_symbol", {"file_path": path, "symbol_name": matching_symbol}))
                if path:
                    candidates.append(("get_dependencies", {"file_path": path}))
                    candidates.append(("get_dependants", {"file_path": path}))
                    candidates.append(("find_tests", {"file_path": path, "limit": 10}))

            if last_success.tool_name == "get_symbol":
                symbol = data.get("symbol", {})
                name = symbol.get("name")
                if name:
                    candidates.append(("find_references", {"symbol_name": name, "limit": 20}))
                path = data.get("file_path")
                if path:
                    candidates.append(("get_dependencies", {"file_path": path}))

            if last_success.tool_name == "find_references":
                for ref in data.get("references", [])[:4]:
                    path = ref.get("file_path")
                    if path:
                        candidates.append(("get_file", {"file_path": path, "max_chars": 4000}))

            if last_success.tool_name in {"get_dependencies", "get_dependants"}:
                for dep_path in data.get("dependency_paths", [])[:5]:
                    for path in re.split(r"\s*->\s*", dep_path):
                        if path and path not in state.discovered_files:
                            candidates.append(("get_file", {"file_path": path, "max_chars": 4000}))
                file_path = data.get("file_path")
                if file_path:
                    candidates.append(("find_tests", {"file_path": file_path, "limit": 10}))

            if last_success.tool_name == "find_tests":
                for test in data.get("tests", [])[:3]:
                    path = test.get("file_path")
                    if path:
                        candidates.append(("get_file", {"file_path": path, "max_chars": 3500}))

        for path in state.discovered_files[:8]:
            candidates.append(("get_dependencies", {"file_path": path}))
            candidates.append(("find_tests", {"file_path": path, "limit": 10}))
        candidates.append(("get_git_activity", {"limit": 8}))
        return candidates

    def _planner_memory(self, state: AgentState) -> str:
        observed = [
            {
                "tool": obs.tool_name,
                "success": obs.success,
                "keys": list(obs.data.keys())[:8],
                "error": obs.error
            }
            for obs in state.observations[-6:]
        ]
        return json.dumps({
            "query": state.user_query,
            "plan": state.investigation_plan,
            "already_inspected": state.discovered_files[-12:],
            "discovered_symbols": state.discovered_symbols[-12:],
            "dependency_paths": state.dependency_paths[-8:],
            "findings": [finding.finding for finding in state.findings[-8:]],
            "recent_observations": observed
        }, indent=2)

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        if not raw or not isinstance(raw, str):
            return {}
        text = raw.strip()
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            text = match.group(0)
        return json.loads(text)

    @staticmethod
    def _clean_symbol_name(symbol: str) -> str:
        return str(symbol).split("(")[0].split("[")[0].strip()

    @staticmethod
    def _best_symbol_for_query(query: str, symbols: List[Dict[str, Any]]) -> Optional[str]:
        query_lower = query.lower()
        for sym in symbols:
            name = str(sym.get("name", ""))
            if name and name.lower() in query_lower:
                return name
        for sym in symbols:
            name = str(sym.get("name", ""))
            parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", name)
            if name and any(part.lower() in query_lower for part in parts if len(part) > 2):
                return name
        if symbols:
            return str(symbols[0].get("name", "")) or None
        return None
