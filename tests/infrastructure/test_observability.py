# -*- coding: utf-8 -*-
"""
Tests for observability infrastructure.

Tests for InMemoryEventStore and StateStoreAdapter.
"""

import pytest
from unittest.mock import Mock
from datetime import datetime

from src.infrastructure.observability.event_store import InMemoryEventStore
from src.infrastructure.observability.state_store_adapter import StateStoreAdapter
from src.application.dto.agent_event import (
    AgentEvent,
    EventType,
    AgentStartedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    ToolStartedEvent,
    ToolCompletedEvent,
)


class TestInMemoryEventStore:
    """Tests for InMemoryEventStore."""

    def setup_method(self):
        """Reset singleton before each test."""
        InMemoryEventStore.reset_instance()

    def teardown_method(self):
        """Reset singleton after each test."""
        InMemoryEventStore.reset_instance()

    def test_emit_and_get_events(self):
        """Test emitting and retrieving events."""
        store = InMemoryEventStore()

        event = AgentStartedEvent(
            session_id="test-session",
            query="What is AI?",
            channel_id="test-channel",
        )

        store.emit(event)

        events = store.get_events("test-session")
        assert len(events) == 1
        assert events[0].event_type == EventType.AGENT_STARTED
        assert events[0].data["query"] == "What is AI?"

    def test_get_latest_event(self):
        """Test getting the latest event."""
        store = InMemoryEventStore()

        # Emit multiple events
        store.emit(AgentStartedEvent(
            session_id="test-session",
            query="Query 1",
            channel_id="channel",
        ))
        store.emit(AgentCompletedEvent(
            session_id="test-session",
            response="Answer",
            sources=[],
            iterations=1,
        ))

        latest = store.get_latest_event("test-session")
        assert latest is not None
        assert latest.event_type == EventType.AGENT_COMPLETED

    def test_clear_session(self):
        """Test clearing session events."""
        store = InMemoryEventStore()

        store.emit(AgentStartedEvent(
            session_id="test-session",
            query="Query",
            channel_id="channel",
        ))

        assert len(store.get_events("test-session")) == 1

        store.clear_session("test-session")

        assert len(store.get_events("test-session")) == 0

    def test_separate_sessions(self):
        """Test that sessions are properly isolated."""
        store = InMemoryEventStore()

        store.emit(AgentStartedEvent(
            session_id="session-1",
            query="Query 1",
            channel_id="channel",
        ))
        store.emit(AgentStartedEvent(
            session_id="session-2",
            query="Query 2",
            channel_id="channel",
        ))

        events1 = store.get_events("session-1")
        events2 = store.get_events("session-2")

        assert len(events1) == 1
        assert len(events2) == 1
        assert events1[0].data["query"] == "Query 1"
        assert events2[0].data["query"] == "Query 2"


class TestStateStoreAdapter:
    """Tests for StateStoreAdapter."""

    def test_emit_agent_started(self):
        """Test adapter converts agent_started event."""
        mock_state_store = Mock()
        adapter = StateStoreAdapter(mock_state_store)

        event = AgentStartedEvent(
            session_id="test-session",
            query="What is AI?",
            channel_id="test-channel",
        )

        adapter.emit(event)

        # Verify state_store.update was called
        mock_state_store.update.assert_called_once()
        call_args = mock_state_store.update.call_args[0][0]
        assert call_args["event"] == "agent_start"

    def test_emit_agent_completed(self):
        """Test adapter converts agent_completed event."""
        mock_state_store = Mock()
        adapter = StateStoreAdapter(mock_state_store)

        event = AgentCompletedEvent(
            session_id="test-session",
            response="This is the answer.",
            sources=[{"source": "doc.pdf"}],
            iterations=2,
        )

        adapter.emit(event)

        mock_state_store.update.assert_called_once()
        call_args = mock_state_store.update.call_args[0][0]
        assert call_args["event"] == "agent_complete"
        assert call_args["data"]["response"] == "This is the answer."

    def test_emit_agent_error(self):
        """Test adapter converts agent_error event."""
        mock_state_store = Mock()
        adapter = StateStoreAdapter(mock_state_store)

        event = AgentErrorEvent(
            session_id="test-session",
            error="Something went wrong",
            error_type="RuntimeError",
        )

        adapter.emit(event)

        mock_state_store.update.assert_called_once()
        call_args = mock_state_store.update.call_args[0][0]
        assert call_args["event"] == "agent_error"
        assert call_args["error"] == "Something went wrong"

    def test_emit_tool_started(self):
        """Test adapter converts tool_started event."""
        mock_state_store = Mock()
        adapter = StateStoreAdapter(mock_state_store)

        event = ToolStartedEvent(
            session_id="test-session",
            tool_name="search_documents",
            tool_input={"query": "test"},
        )

        adapter.emit(event)

        mock_state_store.update.assert_called_once()
        call_args = mock_state_store.update.call_args[0][0]
        assert call_args["event"] == "tool_start"
        assert call_args["node"] == "search_documents"

    def test_emit_tool_completed(self):
        """Test adapter converts tool_completed event."""
        mock_state_store = Mock()
        adapter = StateStoreAdapter(mock_state_store)

        event = ToolCompletedEvent(
            session_id="test-session",
            tool_name="search_documents",
            duration_ms=150.5,
        )

        adapter.emit(event)

        mock_state_store.update.assert_called_once()
        call_args = mock_state_store.update.call_args[0][0]
        assert call_args["event"] == "tool_complete"
        assert call_args["node"] == "search_documents"

    def test_get_events_delegates_to_internal_store(self):
        """Test that get_events works through internal store."""
        mock_state_store = Mock()
        adapter = StateStoreAdapter(mock_state_store)

        # Emit an event
        adapter.emit(AgentStartedEvent(
            session_id="test-session",
            query="Query",
            channel_id="channel",
        ))

        # Get events
        events = adapter.get_events("test-session")
        assert len(events) == 1

    def test_clear_session_resets_state_store(self):
        """Test that clear_session calls reset on state store when channel is associated."""
        mock_state_store = Mock()
        adapter = StateStoreAdapter(mock_state_store)

        # First emit an event to associate a channel with the session
        event = AgentStartedEvent(
            session_id="test-session",
            channel_id="test-channel",
            query="test query",
        )
        adapter.emit(event)

        adapter.clear_session("test-session")

        mock_state_store.reset.assert_called_once_with("test-channel")
