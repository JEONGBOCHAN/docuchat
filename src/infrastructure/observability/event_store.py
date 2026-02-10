# -*- coding: utf-8 -*-
"""
In-Memory Event Store.

A simple in-memory implementation of AgentEventSinkPort.
Suitable for development and single-instance deployments.

For production with multiple instances, use RedisEventBus instead.
"""

from collections import defaultdict
from threading import Lock
from typing import ClassVar

from src.shared.kernel.contracts.ports.observability import AgentEventSinkPort
from src.shared.kernel.contracts.dto.agent_event import AgentEvent


class InMemoryEventStore(AgentEventSinkPort):
    """In-memory implementation of AgentEventSinkPort.

    Thread-safe storage for agent events. Events are stored per session
    and can be retrieved for dashboard display or debugging.

    Note: Events are lost on restart. For persistence, use a different
    implementation (e.g., PostgresEventStore, RedisEventStore).

    Attributes:
        max_events_per_session: Maximum events to keep per session (FIFO)
    """

    # Singleton instance for global access
    _instance: ClassVar["InMemoryEventStore | None"] = None
    _lock: ClassVar[Lock] = Lock()

    def __new__(cls, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_events_per_session: int = 100):
        """Initialize the event store.

        Args:
            max_events_per_session: Maximum events to keep per session
        """
        # Only initialize once (singleton)
        if getattr(self, "_initialized", False):
            return

        self._events: dict[str, list[AgentEvent]] = defaultdict(list)
        self._max_events = max_events_per_session
        self._lock = Lock()
        self._initialized = True

    def emit(self, event: AgentEvent) -> None:
        """Emit an agent event.

        Events are stored in memory, keyed by session_id.
        Old events are removed if max_events_per_session is exceeded.

        Args:
            event: The event to emit
        """
        with self._lock:
            session_events = self._events[event.session_id]
            session_events.append(event)

            # Trim old events if we exceed the limit
            if len(session_events) > self._max_events:
                self._events[event.session_id] = session_events[-self._max_events :]

    def get_events(self, session_id: str) -> list[AgentEvent]:
        """Get all events for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of events in chronological order (oldest first)
        """
        with self._lock:
            return list(self._events.get(session_id, []))

    def get_latest_event(self, session_id: str) -> AgentEvent | None:
        """Get the most recent event for a session.

        Args:
            session_id: The session identifier

        Returns:
            The latest event, or None if no events exist
        """
        with self._lock:
            events = self._events.get(session_id, [])
            return events[-1] if events else None

    def clear_session(self, session_id: str) -> None:
        """Clear all events for a session.

        Args:
            session_id: The session identifier
        """
        with self._lock:
            if session_id in self._events:
                del self._events[session_id]

    def clear_all(self) -> None:
        """Clear all events from all sessions.

        Useful for testing or resetting state.
        """
        with self._lock:
            self._events.clear()

    def get_all_sessions(self) -> list[str]:
        """Get all session IDs with stored events.

        Returns:
            List of session IDs
        """
        with self._lock:
            return list(self._events.keys())

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance.

        Useful for testing. Not recommended in production.
        """
        with cls._lock:
            cls._instance = None


# Global accessor function (for compatibility with existing code pattern)
_global_event_store: InMemoryEventStore | None = None


def get_event_store() -> InMemoryEventStore:
    """Get the global event store instance.

    This provides a clean way to access the event store from anywhere
    in the application, similar to the existing get_global_state_store().

    Returns:
        The global InMemoryEventStore instance
    """
    global _global_event_store
    if _global_event_store is None:
        _global_event_store = InMemoryEventStore()
    return _global_event_store
