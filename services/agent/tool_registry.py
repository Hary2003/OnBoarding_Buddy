from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    description: str
    schema: Dict[str, Any]
    handler: Callable[..., Dict[str, Any]]


class RepositoryToolRegistry:
    def __init__(self):
        self._tools: Dict[str, AgentToolSpec] = {}

    def register(self, spec: AgentToolSpec):
        self._tools[spec.name] = spec

    def get(self, name: str) -> AgentToolSpec | None:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return sorted(self._tools.keys())

    def schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "schema": spec.schema
            }
            for spec in sorted(self._tools.values(), key=lambda item: item.name)
        ]
