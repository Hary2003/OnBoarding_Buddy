import json
from typing import Any, Dict

from models.repository_index import ToolCall, ToolResult
from services.agent.tool_registry import RepositoryToolRegistry


class ToolExecutor:
    def __init__(self, registry: RepositoryToolRegistry):
        self.registry = registry

    @staticmethod
    def normalized_signature(tool_name: str, arguments: Dict[str, Any]) -> str:
        normalized_args = json.dumps(arguments or {}, sort_keys=True, default=str)
        return f"{tool_name}:{normalized_args}"

    def execute(self, call: ToolCall) -> ToolResult:
        spec = self.registry.get(call.tool_name)
        if not spec:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                data={},
                error=f"Unknown repository tool: {call.tool_name}"
            )

        try:
            data = spec.handler(**(call.arguments or {}))
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=True,
                data=data or {},
                error=None
            )
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                data={},
                error=str(exc)
            )
