# -*- coding: utf-8 -*-
"""
State Store Adapter.

Bridges the new AgentEventSinkPort (Clean Architecture) with the existing
AgentStateStore (legacy MCP dashboard). This allows gradual migration
without breaking existing functionality.

Usage:
    from src.infrastructure.observability import StateStoreAdapter
    from src.mcp_server.state import get_global_state_store

    # Create adapter that wraps existing state store
    adapter = StateStoreAdapter(get_global_state_store())

    # Use as AgentEventSinkPort
    adapter.emit(AgentStartedEvent(...))

    # Legacy dashboard still works via get_global_state_store().get_state()
"""

from datetime import datetime

from src.application.ports.observability import AgentEventSinkPort
from src.application.dto.agent_event import (
    AgentEvent,
    EventType,
    AgentStartedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    ToolStartedEvent,
    ToolCompletedEvent,
)
from src.mcp_server.state import AgentStateStore


class StateStoreAdapter(AgentEventSinkPort):
    """Adapter that bridges AgentEventSinkPort to legacy AgentStateStore.

    This adapter converts the new event-based approach to the existing
    event dictionary format expected by AgentStateStore.update().

    This is a temporary solution during migration. Eventually, the
    AgentStateStore should be replaced with a proper implementation
    of AgentEventSinkPort (like InMemoryEventStore or RedisEventBus).
    """

    def __init__(self, state_store: AgentStateStore):
        """Initialize adapter with existing state store.

        Args:
            state_store: The legacy AgentStateStore to wrap
        """
        self._state_store = state_store
        self._events: dict[str, list[AgentEvent]] = {}
        # Track channel_id per session for events that don't include it
        self._session_channels: dict[str, str] = {}

    def emit(self, event: AgentEvent) -> None:
        """Emit an event by converting it to legacy format and updating state store.

        Args:
            event: The AgentEvent to emit
        """
        # Store event in our internal list (for get_events())
        if event.session_id not in self._events:
            self._events[event.session_id] = []
        self._events[event.session_id].append(event)

        # Track channel_id from AGENT_STARTED event
        if event.event_type == EventType.AGENT_STARTED:
            channel_id = event.data.get("channel_id")
            if channel_id:
                self._session_channels[event.session_id] = channel_id

        # Convert to legacy event format and update state store
        legacy_event = self._convert_to_legacy_event(event)
        self._state_store.update(legacy_event)

    def get_events(self, session_id: str) -> list[AgentEvent]:
        """Get all events for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of events in chronological order
        """
        return list(self._events.get(session_id, []))

    def get_latest_event(self, session_id: str) -> AgentEvent | None:
        """Get the most recent event for a session.

        Args:
            session_id: The session identifier

        Returns:
            The latest event, or None if no events exist
        """
        events = self._events.get(session_id, [])
        return events[-1] if events else None

    def clear_session(self, session_id: str) -> None:
        """Clear all events for a session.

        Args:
            session_id: The session identifier
        """
        # Get channel_id before clearing
        channel_id = self._session_channels.get(session_id)

        if session_id in self._events:
            del self._events[session_id]
        if session_id in self._session_channels:
            del self._session_channels[session_id]

        # Reset the state store for this channel
        if channel_id:
            self._state_store.reset(channel_id)

    def _convert_to_legacy_event(self, event: AgentEvent) -> dict:
        """Convert AgentEvent to legacy event dictionary format.

        Args:
            event: The new-style AgentEvent

        Returns:
            Dictionary in legacy format for AgentStateStore.update()
        """
        timestamp = event.timestamp.isoformat()

        # Get channel_id from event data or tracked sessions
        channel_id = event.data.get("channel_id") or self._session_channels.get(
            event.session_id
        )

        if event.event_type == EventType.AGENT_STARTED:
            return {
                "event": "agent_start",
                "timestamp": timestamp,
                "channel_id": channel_id,
                "data": event.data,
            }

        elif event.event_type == EventType.AGENT_COMPLETED:
            return {
                "event": "agent_complete",
                "timestamp": timestamp,
                "channel_id": channel_id,
                "data": event.data,
            }

        elif event.event_type == EventType.AGENT_ERROR:
            return {
                "event": "agent_error",
                "timestamp": timestamp,
                "channel_id": channel_id,
                "error": event.data.get("error", "Unknown error"),
                "data": event.data,
            }

        elif event.event_type == EventType.TOOL_STARTED:
            return {
                "event": "tool_start",
                "timestamp": timestamp,
                "channel_id": channel_id,
                "node": event.data.get("tool_name", "unknown"),
                "data": event.data,
            }

        elif event.event_type == EventType.TOOL_COMPLETED:
            return {
                "event": "tool_complete",
                "timestamp": timestamp,
                "channel_id": channel_id,
                "node": event.data.get("tool_name", "unknown"),
                "data": {
                    "duration_ms": event.data.get("duration_ms"),
                    "result_preview": event.data.get("tool_output"),
                },
            }

        # Unknown event type
        return {
            "event": event.event_type.value,
            "timestamp": timestamp,
            "channel_id": channel_id,
            "data": event.data,
        }


def get_event_sink_adapter() -> StateStoreAdapter:
    """Get a StateStoreAdapter wrapping the global state store.

    This is a convenience function for use in dependency injection.

    Returns:
        StateStoreAdapter wrapping the global AgentStateStore
    """
    from src.mcp_server.state import get_global_state_store
    return StateStoreAdapter(get_global_state_store())
