import json
from typing import Any, Dict, List, Optional, Set, Tuple

from models.repository_index import (
    AgentExploreResponse,
    AgentFinding,
    AgentState,
    RepositoryIndex,
    SourceAttribution,
    ToolCall,
    ToolResult,
)
from services.agent.planner import AgentPlanner
from services.agent.tool_executor import ToolExecutor
from services.agent.tools import build_repository_tool_registry
from services.agent.trace import AgentTracer
from services.groq_service import groq_service


DEFAULT_MAX_ITERATIONS = 8
DEFAULT_MAX_TOOL_CALLS = 15
DEFAULT_MAX_FILES = 20
DEFAULT_MAX_CONTEXT_TOKENS = 16000


class AgentService:
    def __init__(self):
        self.planner = AgentPlanner()
        self.tracer = AgentTracer()

    def explore(
        self,
        query: str,
        repo_index: Optional[RepositoryIndex],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
        max_files: int = DEFAULT_MAX_FILES,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        diff_text: Optional[str] = None,
    ) -> AgentExploreResponse:
        if not repo_index or not repo_index.files:
            raise ValueError("No active repository index found. Please analyze a repository first.")
        if not query or not query.strip():
            raise ValueError("query is required")

        max_iterations = max(1, min(int(max_iterations or DEFAULT_MAX_ITERATIONS), 20))
        max_tool_calls = max(1, min(int(max_tool_calls or DEFAULT_MAX_TOOL_CALLS), 40))
        max_files = max(1, min(int(max_files or DEFAULT_MAX_FILES), 60))
        max_context_tokens = max(1000, min(int(max_context_tokens or DEFAULT_MAX_CONTEXT_TOKENS), 32000))

        registry = build_repository_tool_registry(repo_index, diff_text=diff_text)
        executor = ToolExecutor(registry)
        state = AgentState(
            user_query=query.strip(),
            conversation_history=conversation_history or []
        )

        self.tracer.add(state, "planned", "Analyzed developer question and prepared repository tools.")
        state.investigation_plan = self.planner.create_initial_plan(query, registry.schemas())
        for step in state.investigation_plan[:8]:
            self.tracer.add(state, "planned", step)

        executed_signatures: Set[str] = set()
        limit_reason = None

        while True:
            if self.planner.should_stop(state, max_iterations, max_tool_calls, max_files):
                limit_reason = self._limit_reason(state, max_iterations, max_tool_calls, max_files)
                break

            call = self.planner.select_next_tool(state, registry)
            if not call:
                break

            signature = executor.normalized_signature(call.tool_name, call.arguments)
            if signature in executed_signatures:
                self.tracer.add(state, "skipped", f"Skipped duplicate tool call: {call.tool_name}", call.tool_name)
                break

            executed_signatures.add(signature)
            state.iteration += 1
            state.current_step = f"Execute {call.tool_name}"
            state.tool_calls.append(call)
            self.tracer.add(state, "running", self._describe_call(call), call.tool_name)

            result = executor.execute(call)
            state.observations.append(result)
            self._absorb_observation(state, result)

            if result.success:
                self.tracer.add(state, "success", self._describe_result(result), result.tool_name)
            else:
                self.tracer.add(state, "error", result.error or f"{result.tool_name} failed", result.tool_name)

            if len(state.tool_calls) >= max_tool_calls:
                limit_reason = "maximum tool-call limit reached"
                break

        if limit_reason:
            self.tracer.add(state, "complete", f"Stopping exploration: {limit_reason}.")
        else:
            self.tracer.add(state, "complete", "Sufficient evidence collected; generating grounded answer.")

        state.final_answer = self._generate_final_answer(state, repo_index, max_context_tokens, limit_reason)

        tools_used = []
        for call in state.tool_calls:
            if call.tool_name not in tools_used:
                tools_used.append(call.tool_name)

        return AgentExploreResponse(
            answer=state.final_answer,
            sources=state.sources,
            findings=state.findings,
            files_inspected=state.discovered_files,
            symbols_inspected=state.discovered_symbols,
            dependency_paths=state.dependency_paths,
            tools_used=tools_used,
            trace=state.trace,
            iterations=state.iteration,
            metadata={
                "tool_calls": len(state.tool_calls),
                "max_iterations": max_iterations,
                "max_tool_calls": max_tool_calls,
                "max_files": max_files,
                "max_context_tokens": max_context_tokens,
                "limited": bool(limit_reason),
                "limit_reason": limit_reason,
                "available_tools": registry.names()
            }
        )

    def _absorb_observation(self, state: AgentState, result: ToolResult):
        if not result.success:
            return

        data = result.data or {}
        new_findings: List[Tuple[str, Optional[SourceAttribution]]] = []

        def add_file(path: Optional[str]):
            if path and path not in state.discovered_files:
                state.discovered_files.append(path)

        def add_symbol(name: Optional[str]):
            if name and name not in state.discovered_symbols:
                state.discovered_symbols.append(name)

        def add_source(source: Optional[SourceAttribution]):
            if not source:
                return
            key = (source.file_path, source.symbol_name, source.line_number)
            existing = {(src.file_path, src.symbol_name, src.line_number) for src in state.sources}
            if key not in existing:
                state.sources.append(source)

        if result.tool_name == "search_repository":
            for item in data.get("results", []):
                path = item.get("file_path")
                add_file(path)
                for symbol in item.get("matched_symbols", []):
                    add_symbol(str(symbol).split("(")[0].split("[")[0].strip())
                source = SourceAttribution(file_path=path, line_number=1, relevance_reason=f"Search match for '{data.get('query', state.user_query)}'") if path else None
                new_findings.append((f"Search found `{path}` as relevant evidence.", source))

        elif result.tool_name == "get_file":
            path = data.get("file_path")
            add_file(path)
            source = SourceAttribution(file_path=path, line_number=1, relevance_reason="Inspected indexed file") if path else None
            add_source(source)
            for sym in data.get("symbols", [])[:12]:
                add_symbol(sym.get("name"))
            if path:
                new_findings.append((f"Inspected `{path}` ({data.get('language', 'unknown')}), category `{data.get('module_category', 'standard')}`.", source))

        elif result.tool_name == "get_symbol":
            path = data.get("file_path")
            sym = data.get("symbol", {})
            add_file(path)
            add_symbol(sym.get("name"))
            source = SourceAttribution(file_path=path, symbol_name=sym.get("name"), line_number=sym.get("line_number"), relevance_reason="Inspected indexed symbol") if path else None
            add_source(source)
            new_findings.append((f"Inspected symbol `{sym.get('name')}` in `{path}`.", source))

        elif result.tool_name == "find_references":
            refs = data.get("references", [])
            for ref in refs:
                path = ref.get("file_path")
                add_file(path)
                source = SourceAttribution(file_path=path, symbol_name=data.get("symbol_name"), line_number=ref.get("line_number"), relevance_reason="Reference match") if path else None
                add_source(source)
            if refs:
                new_findings.append((f"Found {len(refs)} reference(s) to `{data.get('symbol_name')}`.", None))

        elif result.tool_name in {"get_dependencies", "get_dependants"}:
            add_file(data.get("file_path"))
            for dep_path in data.get("dependency_paths", []):
                if dep_path not in state.dependency_paths:
                    state.dependency_paths.append(dep_path)
            for dep_path in data.get("dependency_paths", [])[:5]:
                new_findings.append((f"Established dependency path `{dep_path}`.", None))

        elif result.tool_name == "find_entry_points":
            entries = data.get("entry_points", [])
            for entry in entries:
                path = entry.get("file_path")
                add_file(path)
                source = SourceAttribution(file_path=path, line_number=1, relevance_reason="Detected entry point") if path else None
                add_source(source)
                new_findings.append((f"Detected likely entry point `{path}`.", source))

        elif result.tool_name == "find_tests":
            tests = data.get("tests", [])
            for test in tests:
                path = test.get("file_path")
                add_file(path)
                source = SourceAttribution(file_path=path, line_number=1, relevance_reason=test.get("reason", "Related test file")) if path else None
                add_source(source)
            if tests:
                new_findings.append((f"Found {len(tests)} related test file(s).", None))

        elif result.tool_name == "get_architecture":
            for path in data.get("entry_points", [])[:8]:
                add_file(path)
                add_source(SourceAttribution(file_path=path, line_number=1, relevance_reason="Architecture entry point"))
            summary = data.get("architecture_summary", {})
            arch_type = summary.get("architecture_type", "repository architecture")
            new_findings.append((f"Architecture summary identifies `{arch_type}`.", None))

        elif result.tool_name == "get_git_activity":
            for item in data.get("files", [])[:8]:
                add_file(item.get("file_path"))
            if data.get("files"):
                new_findings.append((f"Reviewed Git activity for {len(data.get('files', []))} active file(s).", None))

        elif result.tool_name == "get_changed_files":
            for f in data.get("files", []):
                p = f.get("file_path")
                add_file(p)
                source = SourceAttribution(file_path=p, line_number=1, relevance_reason=f"PR {f.get('status', 'changed')} file") if p else None
                add_source(source)
                for sym in f.get("modified_symbols", []):
                    add_symbol(sym)
                new_findings.append((f"PR alters `{p}` [{f.get('status')}] with +{f.get('additions')}/-{f.get('deletions')} lines.", source))

        elif result.tool_name == "get_changed_symbols":
            for sym in data.get("symbols", []):
                add_symbol(sym)
                new_findings.append((f"PR modifies symbol `{sym}` in `{data.get('file_path')}`.", None))
            for p, sym_list in data.get("symbols_by_file", {}).items():
                add_file(p)
                for sym in sym_list:
                    add_symbol(sym)
                    new_findings.append((f"PR modifies symbol `{sym}` in `{p}`.", None))

        elif result.tool_name == "review_architecture":
            impact = data.get("architecture_impact", {})
            for ep in impact.get("affected_entry_points", []):
                add_file(ep)
                new_findings.append((f"PR changes impact application entry point `{ep}`.", None))
            for violation in impact.get("layer_violations", []):
                new_findings.append((f"Architectural layer violation: {violation}", None))
            for god in impact.get("god_module_risks", []):
                new_findings.append((f"Coupling/complexity alert: {god}", None))

        elif result.tool_name == "review_security":
            risks = data.get("risks", [])
            for r in risks:
                source = SourceAttribution(file_path=r.get("file_path"), line_number=r.get("line_number") or 1, relevance_reason=f"Security risk: {r.get('title')}")
                add_source(source)
                new_findings.append((f"Security Alert [{r.get('severity')}]: {r.get('title')} in `{r.get('file_path')}`.", source))
            if not risks:
                new_findings.append(("Static security scan passed with no vulnerabilities detected in PR diff.", None))

        elif result.tool_name == "review_tests":
            rec = data.get("test_recommendations", {})
            for missing in rec.get("missing_tests", []):
                new_findings.append((f"Missing test warning: {missing}", None))
            for tf in rec.get("recommended_test_files", []):
                add_file(tf)
                new_findings.append((f"Recommended test file: `{tf}`", None))

        elif result.tool_name == "summarize_changes":
            sum_data = data.get("summary", {})
            if sum_data.get("executive_summary"):
                new_findings.append((f"Executive summary: {sum_data.get('executive_summary')}", None))

        existing_findings = {finding.finding for finding in state.findings}
        for text, source in new_findings:
            if text and text not in existing_findings:
                finding = AgentFinding(finding=text, source=source)
                state.findings.append(finding)
                existing_findings.add(text)
                add_source(source)

    def _generate_final_answer(
        self,
        state: AgentState,
        repo_index: RepositoryIndex,
        max_context_tokens: int,
        limit_reason: Optional[str],
    ) -> str:
        context = self._build_evidence_context(state, repo_index, max_context_tokens)
        if not state.sources and not state.findings:
            return (
                "I could not establish a repository-grounded answer from the collected evidence. "
                "The investigation did not find matching indexed files, symbols, dependencies, or tests."
            )

        llm_answer = groq_service.chat_with_repository(
            question=state.user_query,
            repo_context=context,
            history=state.conversation_history
        )
        if self._is_good_llm_answer(llm_answer):
            if limit_reason:
                return f"{llm_answer}\n\nInvestigation note: exploration stopped because {limit_reason}."
            return llm_answer

        lines = ["## Answer"]
        if limit_reason:
            lines.append(f"Investigation was limited because {limit_reason}; this is the best grounded answer from collected evidence.")
        lines.append("Repository evidence collected by the agent points to these facts:")
        for finding in state.findings[:10]:
            lines.append(f"- {finding.finding}")

        if state.dependency_paths:
            lines.append("\n## Relevant Dependency Paths")
            for dep_path in state.dependency_paths[:8]:
                lines.append(f"- {dep_path}")

        if state.discovered_files:
            lines.append("\n## Relevant Files")
            for path in state.discovered_files[:12]:
                lines.append(f"- `{path}`")

        if state.discovered_symbols:
            lines.append("\n## Relevant Symbols")
            for symbol in state.discovered_symbols[:12]:
                lines.append(f"- `{symbol}`")

        lines.append("\n## Investigation Summary")
        lines.append(f"The agent used {len(state.tool_calls)} read-only tool call(s) across {state.iteration} iteration(s).")
        lines.append("Claims above are limited to indexed repository evidence collected during this investigation.")
        return "\n".join(lines)

    def _build_evidence_context(self, state: AgentState, repo_index: RepositoryIndex, max_context_tokens: int) -> str:
        lines = [
            "# Agent-Collected Repository Evidence",
            f"Repository: {repo_index.repo_name}",
            f"Developer Question: {state.user_query}",
            "",
            "## Investigation Plan",
        ]
        lines.extend([f"- {step}" for step in state.investigation_plan[:8]])
        lines.append("\n## Findings")
        for finding in state.findings:
            source = ""
            if finding.source:
                source = f" Source: {finding.source.file_path}"
                if finding.source.symbol_name:
                    source += f"::{finding.source.symbol_name}"
                if finding.source.line_number:
                    source += f":{finding.source.line_number}"
            lines.append(f"- {finding.finding}{source}")

        lines.append("\n## Sources")
        for source in state.sources[:20]:
            symbol = f"::{source.symbol_name}" if source.symbol_name else ""
            line = f":{source.line_number}" if source.line_number else ""
            lines.append(f"- `{source.file_path}{symbol}{line}` - {source.relevance_reason}")

        lines.append("\n## Dependency Paths")
        for dep_path in state.dependency_paths[:12]:
            lines.append(f"- {dep_path}")

        lines.append("\n## Tool Observations")
        for obs in state.observations[-10:]:
            preview = json.dumps(obs.data, default=str)[:1200] if obs.success else (obs.error or "")
            lines.append(f"### {obs.tool_name} ({'success' if obs.success else 'error'})\n{preview}")

        text = "\n".join(lines)
        char_budget = max_context_tokens * 4
        return text[:char_budget]

    @staticmethod
    def _is_good_llm_answer(answer: Any) -> bool:
        if not answer or not isinstance(answer, str):
            return False
        bad_markers = [
            "Groq API Key missing",
            "Groq API Error",
            "Invalid Groq API Key",
            "Unable to generate"
        ]
        return not any(marker in answer for marker in bad_markers)

    @staticmethod
    def _describe_call(call: ToolCall) -> str:
        if call.tool_name == "search_repository":
            return f"Searching repository for '{call.arguments.get('query', '')}'."
        if call.tool_name == "get_file":
            return f"Inspecting file `{call.arguments.get('file_path', '')}`."
        if call.tool_name == "get_symbol":
            return f"Inspecting symbol `{call.arguments.get('symbol_name', '')}`."
        if call.tool_name == "find_references":
            return f"Finding references to `{call.arguments.get('symbol_name', '')}`."
        return f"Executing repository tool `{call.tool_name}`."

    @staticmethod
    def _describe_result(result: ToolResult) -> str:
        data = result.data or {}
        if result.tool_name == "search_repository":
            return f"Found {len(data.get('results', []))} matching file(s)."
        if result.tool_name == "get_file":
            return f"Inspected `{data.get('file_path', '')}`."
        if result.tool_name == "get_symbol":
            return f"Collected symbol evidence from `{data.get('file_path', '')}`."
        if result.tool_name == "find_references":
            return f"Found {len(data.get('references', []))} reference(s)."
        if result.tool_name == "find_tests":
            return f"Found {len(data.get('tests', []))} related test file(s)."
        if result.tool_name == "find_entry_points":
            return f"Found {len(data.get('entry_points', []))} entry point(s)."
        return f"`{result.tool_name}` completed."

    @staticmethod
    def _limit_reason(state: AgentState, max_iterations: int, max_tool_calls: int, max_files: int) -> Optional[str]:
        if state.iteration >= max_iterations:
            return "maximum iteration limit reached"
        if len(state.tool_calls) >= max_tool_calls:
            return "maximum tool-call limit reached"
        if len(state.discovered_files) >= max_files:
            return "maximum file discovery limit reached"
        return None


agent_service = AgentService()
