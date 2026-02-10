# -*- coding: utf-8 -*-
"""
Observability Port.

This port defines the interface for agent event observation.
It's a cross-cutting concern separated from business logic.

"에이전트 실행은 application 정책이지만, 관측은 교차 관심사(cross-cutting concern)라서
포트로 분리했고, 미들웨어는 이벤트를 포트로 발행만 한다."

Benefits:
- Storage agnostic: InMemory → Redis → PostgreSQL without code changes
- UI independent: FastAPI dashboard and MCP Apps consume the same event stream
- Testable: Mock EventSink to verify event emission in tests
"""

from abc import ABC, abstractmethod

from src.shared.kernel.contracts.dto.agent_event import AgentEvent


class AgentEventSinkPort(ABC):
    """Abstract interface for agent event observation.

    Implementations of this port handle the storage and retrieval
    of agent execution events. This allows the application layer
    to emit events without knowing how they are stored or consumed.

    Example usage:
        event_sink = InMemoryEventStore()
        event_sink.emit(AgentStartedEvent(session_id="abc", query="Hello"))

        # Later, retrieve events
        events = event_sink.get_events("abc")
    """

    @abstractmethod
    def emit(self, event: AgentEvent) -> None:
        """Emit an agent event.

        Args:
            event: The event to emit
        """
        pass

    @abstractmethod
    def get_events(self, session_id: str) -> list[AgentEvent]:
        """Get all events for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of events in chronological order
        """
        pass

    @abstractmethod
    def get_latest_event(self, session_id: str) -> AgentEvent | None:
        """Get the most recent event for a session.

        Args:
            session_id: The session identifier

        Returns:
            The latest event, or None if no events exist
        """
        pass

    @abstractmethod
    def clear_session(self, session_id: str) -> None:
        """Clear all events for a session.

        Args:
            session_id: The session identifier
        """
        pass

    def get_current_state(self, session_id: str) -> dict:
        """Get the current state derived from events.

        This is a convenience method that reconstructs the current
        agent state from the event history.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary representing current state
        """
        events = self.get_events(session_id)
        if not events:
            return {
                "status": "idle",
                "session_id": session_id,
                "events": [],
            }

        latest = events[-1]
        status = "idle"

        if latest.event_type.value == "agent_started":
            status = "running"
        elif latest.event_type.value == "agent_completed":
            status = "complete"
        elif latest.event_type.value == "agent_error":
            status = "error"
        elif latest.event_type.value == "tool_started":
            status = "running"
        elif latest.event_type.value == "tool_completed":
            status = "running"

        return {
            "status": status,
            "session_id": session_id,
            "current_event": latest.to_dict(),
            "event_count": len(events),
            "events": [e.to_dict() for e in events],
        }
