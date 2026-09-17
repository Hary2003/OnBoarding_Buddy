from models.repository_index import AgentState, AgentTraceEvent


class AgentTracer:
    def add(self, state: AgentState, status: str, description: str, tool: str | None = None) -> AgentTraceEvent:
        event = AgentTraceEvent(
            step=len(state.trace) + 1,
            tool=tool,
            status=status,
            description=description[:240]
        )
        state.trace.append(event)
        return event
