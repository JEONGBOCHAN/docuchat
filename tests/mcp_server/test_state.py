# -*- coding: utf-8 -*-
"""Tests for the MCP Server state store module."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from src.mcp_server.state import (
    AgentStateStore,
    AgentState,
    AgentStatus,
    NodeStatus,
    StepRecord,
    AgentMetrics,
    get_global_state_store,
    reset_global_state_store,
)


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_status_values(self):
        """Test that AgentStatus has expected values."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.COMPLETE.value == "complete"
        assert AgentStatus.ERROR.value == "error"


class TestNodeStatus:
    """Tests for NodeStatus enum."""

    def test_status_values(self):
        """Test that NodeStatus has expected values."""
        assert NodeStatus.PENDING.value == "pending"
        assert NodeStatus.RUNNING.value == "running"
        assert NodeStatus.COMPLETE.value == "complete"
        assert NodeStatus.ERROR.value == "error"


class TestStepRecord:
    """Tests for StepRecord dataclass."""

    def test_default_values(self):
        """Test StepRecord default values."""
        step = StepRecord(node="Draft", status="running")

        assert step.node == "Draft"
        assert step.status == "running"
        assert step.timestamp is not None
        assert step.duration_ms is None
        assert step.data == {}

    def test_with_custom_values(self):
        """Test StepRecord with custom values."""
        step = StepRecord(
            node="Retrieve",
            status="complete",
            timestamp="2024-01-01T00:00:00",
            duration_ms=150.5,
            data={"query": "test"},
        )

        assert step.node == "Retrieve"
        assert step.status == "complete"
        assert step.timestamp == "2024-01-01T00:00:00"
        assert step.duration_ms == 150.5
        assert step.data == {"query": "test"}


class TestAgentMetrics:
    """Tests for AgentMetrics dataclass."""

    def test_default_values(self):
        """Test AgentMetrics default values."""
        metrics = AgentMetrics()

        assert metrics.total_steps == 0
        assert metrics.model_calls == 0
        assert metrics.tool_calls == 0
        assert metrics.start_time is None
        assert metrics.end_time is None
        assert metrics.total_duration_ms is None


class TestAgentState:
    """Tests for AgentState dataclass."""

    def test_default_values(self):
        """Test AgentState default values."""
        state = AgentState()

        assert state.status == AgentStatus.IDLE
        assert state.channel_id is None
        assert state.current_node is None
        assert state.current_query is None
        assert state.steps == []
        assert isinstance(state.metrics, AgentMetrics)
        assert state.last_error is None

    def test_to_dict(self):
        """Test AgentState serialization to dict."""
        step = StepRecord(
            node="Draft",
            status="complete",
            duration_ms=100.0,
            data={"type": "model"},
        )
        state = AgentState(
            status=AgentStatus.RUNNING,
            current_node="Reflect",
            current_query="What is X?",
            steps=[step],
        )
        state.metrics.total_steps = 1
        state.metrics.model_calls = 1

        result = state.to_dict()

        assert result["status"] == "running"
        assert result["current_node"] == "Reflect"
        assert result["current_query"] == "What is X?"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["node"] == "Draft"
        assert result["steps"][0]["status"] == "complete"
        assert result["metrics"]["total_steps"] == 1
        assert result["metrics"]["model_calls"] == 1

    def test_to_dict_with_channel_id(self):
        """Test that to_dict includes channel_id."""
        state = AgentState(channel_id="test-channel-123")
        result = state.to_dict()
        assert result["channel_id"] == "test-channel-123"


class TestAgentStateStore:
    """Tests for AgentStateStore class."""

    def test_init(self):
        """Test AgentStateStore initialization."""
        store = AgentStateStore()

        # New store should return idle state for any channel
        state = store.get_state("test-channel")
        assert state["status"] == "idle"

    def test_reset(self):
        """Test state reset functionality."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # Add some state
        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": datetime.now().isoformat(),
        })

        # Reset the channel
        store.reset(channel_id)

        state = store.get_state(channel_id)
        assert state["status"] == "idle"

    def test_get_state_returns_dict(self):
        """Test get_state returns a dictionary."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": datetime.now().isoformat(),
        })

        result = store.get_state(channel_id)

        assert isinstance(result, dict)
        assert result["status"] == "running"

    def test_subscribe_and_notify(self):
        """Test subscription and notification mechanism."""
        store = AgentStateStore()
        received_events = []

        def callback(state):
            received_events.append(state)

        store.subscribe(callback)

        # Trigger an update that notifies subscribers
        store.update({
            "event": "agent_start",
            "channel_id": "test-channel",
            "timestamp": datetime.now().isoformat(),
        })

        assert len(received_events) == 1
        assert received_events[0]["status"] == "running"

    def test_unsubscribe(self):
        """Test unsubscribe functionality."""
        store = AgentStateStore()
        received_events = []

        def callback(state):
            received_events.append(state)

        store.subscribe(callback)
        store.unsubscribe(callback)

        store.update({
            "event": "agent_start",
            "channel_id": "test-channel",
            "timestamp": datetime.now().isoformat(),
        })

        assert len(received_events) == 0

    def test_unsubscribe_nonexistent(self):
        """Test unsubscribing a callback that wasn't subscribed."""
        store = AgentStateStore()

        def callback(state):
            pass

        # Should not raise an error
        store.unsubscribe(callback)

    def test_subscriber_error_handling(self):
        """Test that subscriber errors don't break updates."""
        store = AgentStateStore()
        good_events = []

        def bad_callback(state):
            raise RuntimeError("Callback error")

        def good_callback(state):
            good_events.append(state)

        store.subscribe(bad_callback)
        store.subscribe(good_callback)

        # Should not raise, and good callback should still receive
        store.update({
            "event": "agent_start",
            "channel_id": "test-channel",
            "timestamp": datetime.now().isoformat(),
        })

        assert len(good_events) == 1


class TestAgentStateStoreUpdate:
    """Tests for AgentStateStore.update() method."""

    def test_update_agent_start(self):
        """Test handling agent_start event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:00",
            "data": {"query": "Test query"},
        })

        state = store.get_state(channel_id)
        assert state["status"] == "running"
        assert state["metrics"]["start_time"] == "2024-01-01T00:00:00"
        assert state["current_query"] == "Test query"

    def test_update_agent_complete(self):
        """Test handling agent_complete event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # First start the agent
        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:00",
        })

        store.update({
            "event": "agent_complete",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:10",
        })

        state = store.get_state(channel_id)
        assert state["status"] == "complete"
        assert state["metrics"]["end_time"] == "2024-01-01T00:00:10"
        assert state["current_node"] is None
        assert state["metrics"]["total_duration_ms"] is not None

    def test_update_agent_error(self):
        """Test handling agent_error event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # First start the agent
        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:00",
        })

        store.update({
            "event": "agent_error",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:05",
            "error": "Something went wrong",
        })

        state = store.get_state(channel_id)
        assert state["status"] == "error"
        assert state["last_error"] == "Something went wrong"
        assert state["current_node"] is None

    def test_update_model_start(self):
        """Test handling model_start event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "model_start",
            "channel_id": channel_id,
            "node": "Draft",
            "timestamp": "2024-01-01T00:00:01",
            "data": {"type": "model"},
        })

        state = store.get_state(channel_id)
        assert state["current_node"] == "Draft"
        assert state["metrics"]["model_calls"] == 1
        assert state["metrics"]["total_steps"] == 1
        assert len(state["steps"]) == 1
        assert state["steps"][0]["node"] == "Draft"
        assert state["steps"][0]["status"] == "running"

    def test_update_model_complete(self):
        """Test handling model_complete event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # First, start a model
        store.update({
            "event": "model_start",
            "channel_id": channel_id,
            "node": "Draft",
            "timestamp": "2024-01-01T00:00:01",
        })

        # Then complete it
        store.update({
            "event": "model_complete",
            "channel_id": channel_id,
            "node": "Draft",
            "data": {"duration_ms": 500},
        })

        state = store.get_state(channel_id)
        assert len(state["steps"]) == 1
        assert state["steps"][0]["status"] == "complete"
        assert state["steps"][0]["duration_ms"] == 500

    def test_update_tool_start(self):
        """Test handling tool_start event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "tool_start",
            "channel_id": channel_id,
            "node": "search_documents",
            "timestamp": "2024-01-01T00:00:01",
            "data": {"type": "tool", "input_preview": "test query"},
        })

        state = store.get_state(channel_id)
        assert state["current_node"] == "search_documents"
        assert state["metrics"]["tool_calls"] == 1
        assert state["metrics"]["total_steps"] == 1
        assert len(state["steps"]) == 1
        assert state["steps"][0]["node"] == "search_documents"

    def test_update_tool_complete(self):
        """Test handling tool_complete event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "tool_start",
            "channel_id": channel_id,
            "node": "search_documents",
            "timestamp": "2024-01-01T00:00:01",
        })
        store.update({
            "event": "tool_complete",
            "channel_id": channel_id,
            "node": "search_documents",
            "data": {"duration_ms": 200, "result_preview": "Found 5 results"},
        })

        state = store.get_state(channel_id)
        assert state["steps"][0]["status"] == "complete"
        assert state["steps"][0]["duration_ms"] == 200
        assert state["steps"][0]["data"].get("result_preview") == "Found 5 results"

    def test_update_tool_error(self):
        """Test handling tool_error event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "tool_start",
            "channel_id": channel_id,
            "node": "search_documents",
            "timestamp": "2024-01-01T00:00:01",
        })
        store.update({
            "event": "tool_error",
            "channel_id": channel_id,
            "node": "search_documents",
            "error": "API timeout",
            "data": {"duration_ms": 5000},
        })

        state = store.get_state(channel_id)
        assert state["steps"][0]["status"] == "error"
        assert state["steps"][0]["data"].get("error") == "API timeout"

    def test_update_llm_start(self):
        """Test handling llm_start event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "llm_start",
            "channel_id": channel_id,
            "node": "llm_draft",
            "timestamp": "2024-01-01T00:00:01",
            "data": {"type": "llm", "prompt_length": 100},
        })

        state = store.get_state(channel_id)
        assert state["current_node"] == "llm_draft"
        assert state["metrics"]["model_calls"] == 1
        assert state["metrics"]["total_steps"] == 1
        assert len(state["steps"]) == 1
        assert state["steps"][0]["node"] == "llm_draft"
        assert state["steps"][0]["status"] == "running"
        assert state["steps"][0]["data"]["type"] == "llm"

    def test_update_llm_complete(self):
        """Test handling llm_complete event."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # First, start an LLM call
        store.update({
            "event": "llm_start",
            "channel_id": channel_id,
            "node": "llm_reflect",
            "timestamp": "2024-01-01T00:00:01",
            "data": {"type": "llm"},
        })

        # Then complete it
        store.update({
            "event": "llm_complete",
            "channel_id": channel_id,
            "node": "llm_reflect",
            "data": {"type": "llm", "duration_ms": 2500},
        })

        state = store.get_state(channel_id)
        assert len(state["steps"]) == 1
        assert state["steps"][0]["status"] == "complete"
        assert state["steps"][0]["duration_ms"] == 2500

    def test_update_llm_sequence(self):
        """Test handling sequence of LLM events (draft -> reflect -> revise)."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # Draft
        store.update({
            "event": "llm_start",
            "channel_id": channel_id,
            "node": "llm_draft",
            "timestamp": "2024-01-01T00:00:01",
            "data": {"type": "llm"},
        })
        store.update({
            "event": "llm_complete",
            "channel_id": channel_id,
            "node": "llm_draft",
            "data": {"type": "llm", "duration_ms": 1000},
        })

        # Reflect
        store.update({
            "event": "llm_start",
            "channel_id": channel_id,
            "node": "llm_reflect",
            "timestamp": "2024-01-01T00:00:02",
            "data": {"type": "llm"},
        })
        store.update({
            "event": "llm_complete",
            "channel_id": channel_id,
            "node": "llm_reflect",
            "data": {"type": "llm", "duration_ms": 800},
        })

        # Revise
        store.update({
            "event": "llm_start",
            "channel_id": channel_id,
            "node": "llm_revise",
            "timestamp": "2024-01-01T00:00:03",
            "data": {"type": "llm"},
        })
        store.update({
            "event": "llm_complete",
            "channel_id": channel_id,
            "node": "llm_revise",
            "data": {"type": "llm", "duration_ms": 1200},
        })

        state = store.get_state(channel_id)
        assert state["metrics"]["model_calls"] == 3
        assert state["metrics"]["total_steps"] == 3
        assert len(state["steps"]) == 3

        # Verify all steps
        assert state["steps"][0]["node"] == "llm_draft"
        assert state["steps"][0]["status"] == "complete"
        assert state["steps"][1]["node"] == "llm_reflect"
        assert state["steps"][1]["status"] == "complete"
        assert state["steps"][2]["node"] == "llm_revise"
        assert state["steps"][2]["status"] == "complete"


class TestAgentStateStoreThreadSafety:
    """Tests for thread safety of AgentStateStore."""

    def test_concurrent_updates(self):
        """Test that concurrent updates don't corrupt state."""
        import threading

        store = AgentStateStore()
        channel_id = "test-channel"
        errors = []

        def update_worker(worker_id):
            try:
                for i in range(10):
                    store.update({
                        "event": "tool_start",
                        "channel_id": channel_id,
                        "node": f"tool_{worker_id}_{i}",
                        "timestamp": datetime.now().isoformat(),
                    })
                    store.update({
                        "event": "tool_complete",
                        "channel_id": channel_id,
                        "node": f"tool_{worker_id}_{i}",
                        "data": {"duration_ms": 10},
                    })
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0

        # Should have 30 tool calls (3 workers * 10 calls each)
        state = store.get_state(channel_id)
        assert state["metrics"]["tool_calls"] == 30


class TestGlobalStateStore:
    """Tests for global state store functions."""

    def test_get_global_state_store(self):
        """Test that get_global_state_store returns same instance."""
        store1 = get_global_state_store()
        store2 = get_global_state_store()

        assert store1 is store2

    def test_reset_global_state_store(self):
        """Test that reset_global_state_store resets the state."""
        store = get_global_state_store()
        channel_id = "test-channel"

        # Add some state
        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": datetime.now().isoformat(),
        })

        reset_global_state_store(channel_id)

        state = store.get_state(channel_id)
        assert state["status"] == "idle"
        assert state["steps"] == []
