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
    PIPELINE_NODES,
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
        assert state.current_node is None
        assert state.current_query is None
        assert state.steps == []
        assert isinstance(state.metrics, AgentMetrics)
        assert state.last_error is None
        assert len(state.pipeline_nodes) > 0

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
        assert "pipeline_nodes" in result

    def test_to_dict_pipeline_node_statuses(self):
        """Test that to_dict correctly maps step statuses to pipeline nodes."""
        state = AgentState()
        state.steps.append(StepRecord(node="retrieve", status="complete"))
        state.steps.append(StepRecord(node="draft", status="running"))

        result = state.to_dict()

        # Find the pipeline nodes in result
        retrieve_node = next(
            (n for n in result["pipeline_nodes"] if n["id"] == "retrieve"), None
        )
        draft_node = next(
            (n for n in result["pipeline_nodes"] if n["id"] == "draft"), None
        )
        rerank_node = next(
            (n for n in result["pipeline_nodes"] if n["id"] == "rerank"), None
        )

        assert retrieve_node is not None
        assert retrieve_node["status"] == "complete"
        assert draft_node is not None
        assert draft_node["status"] == "running"
        assert rerank_node is not None
        assert rerank_node["status"] == "pending"


class TestAgentStateStore:
    """Tests for AgentStateStore class."""

    def test_init(self):
        """Test AgentStateStore initialization."""
        store = AgentStateStore()

        assert store.state.status == AgentStatus.IDLE
        assert store.get_state()["status"] == "idle"

    def test_reset(self):
        """Test state reset functionality."""
        store = AgentStateStore()
        store._state.status = AgentStatus.RUNNING
        store._state.steps.append(StepRecord(node="test", status="complete"))

        store.reset()

        assert store.state.status == AgentStatus.IDLE
        assert store.state.steps == []

    def test_get_state_returns_dict(self):
        """Test get_state returns a dictionary."""
        store = AgentStateStore()
        store._state.status = AgentStatus.RUNNING

        result = store.get_state()

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
        store.update({"event": "agent_start", "timestamp": datetime.now().isoformat()})

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

        store.update({"event": "agent_start", "timestamp": datetime.now().isoformat()})

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
        store.update({"event": "agent_start", "timestamp": datetime.now().isoformat()})

        assert len(good_events) == 1


class TestAgentStateStoreUpdate:
    """Tests for AgentStateStore.update() method."""

    def test_update_agent_start(self):
        """Test handling agent_start event."""
        store = AgentStateStore()

        store.update({
            "event": "agent_start",
            "timestamp": "2024-01-01T00:00:00",
            "data": {"query": "Test query"},
        })

        assert store.state.status == AgentStatus.RUNNING
        assert store.state.metrics.start_time == "2024-01-01T00:00:00"
        assert store.state.current_query == "Test query"

    def test_update_agent_complete(self):
        """Test handling agent_complete event."""
        store = AgentStateStore()
        store._state.status = AgentStatus.RUNNING
        store._state.metrics.start_time = "2024-01-01T00:00:00"

        store.update({
            "event": "agent_complete",
            "timestamp": "2024-01-01T00:00:10",
        })

        assert store.state.status == AgentStatus.COMPLETE
        assert store.state.metrics.end_time == "2024-01-01T00:00:10"
        assert store.state.current_node is None
        assert store.state.metrics.total_duration_ms is not None

    def test_update_agent_error(self):
        """Test handling agent_error event."""
        store = AgentStateStore()
        store._state.status = AgentStatus.RUNNING

        store.update({
            "event": "agent_error",
            "timestamp": "2024-01-01T00:00:05",
            "error": "Something went wrong",
        })

        assert store.state.status == AgentStatus.ERROR
        assert store.state.last_error == "Something went wrong"
        assert store.state.current_node is None

    def test_update_model_start(self):
        """Test handling model_start event."""
        store = AgentStateStore()

        store.update({
            "event": "model_start",
            "node": "Draft",
            "timestamp": "2024-01-01T00:00:01",
            "data": {"type": "model"},
        })

        assert store.state.current_node == "Draft"
        assert store.state.metrics.model_calls == 1
        assert store.state.metrics.total_steps == 1
        assert len(store.state.steps) == 1
        assert store.state.steps[0].node == "Draft"
        assert store.state.steps[0].status == NodeStatus.RUNNING.value

    def test_update_model_complete(self):
        """Test handling model_complete event."""
        store = AgentStateStore()

        # First, start a model
        store.update({
            "event": "model_start",
            "node": "Draft",
            "timestamp": "2024-01-01T00:00:01",
        })

        # Then complete it
        store.update({
            "event": "model_complete",
            "node": "Draft",
            "data": {"duration_ms": 500},
        })

        assert len(store.state.steps) == 1
        assert store.state.steps[0].status == NodeStatus.COMPLETE.value
        assert store.state.steps[0].duration_ms == 500

    def test_update_tool_start(self):
        """Test handling tool_start event."""
        store = AgentStateStore()

        store.update({
            "event": "tool_start",
            "node": "search_documents",
            "timestamp": "2024-01-01T00:00:01",
            "data": {"type": "tool", "input_preview": "test query"},
        })

        assert store.state.current_node == "search_documents"
        assert store.state.metrics.tool_calls == 1
        assert store.state.metrics.total_steps == 1
        assert len(store.state.steps) == 1
        assert store.state.steps[0].node == "search_documents"

    def test_update_tool_complete(self):
        """Test handling tool_complete event."""
        store = AgentStateStore()

        store.update({
            "event": "tool_start",
            "node": "search_documents",
            "timestamp": "2024-01-01T00:00:01",
        })
        store.update({
            "event": "tool_complete",
            "node": "search_documents",
            "data": {"duration_ms": 200, "result_preview": "Found 5 results"},
        })

        assert store.state.steps[0].status == NodeStatus.COMPLETE.value
        assert store.state.steps[0].duration_ms == 200
        assert store.state.steps[0].data.get("result_preview") == "Found 5 results"

    def test_update_tool_error(self):
        """Test handling tool_error event."""
        store = AgentStateStore()

        store.update({
            "event": "tool_start",
            "node": "search_documents",
            "timestamp": "2024-01-01T00:00:01",
        })
        store.update({
            "event": "tool_error",
            "node": "search_documents",
            "error": "API timeout",
            "data": {"duration_ms": 5000},
        })

        assert store.state.steps[0].status == NodeStatus.ERROR.value
        assert store.state.steps[0].data.get("error") == "API timeout"


class TestAgentStateStoreThreadSafety:
    """Tests for thread safety of AgentStateStore."""

    def test_concurrent_updates(self):
        """Test that concurrent updates don't corrupt state."""
        import threading

        store = AgentStateStore()
        errors = []

        def update_worker(worker_id):
            try:
                for i in range(10):
                    store.update({
                        "event": "tool_start",
                        "node": f"tool_{worker_id}_{i}",
                        "timestamp": datetime.now().isoformat(),
                    })
                    store.update({
                        "event": "tool_complete",
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
        assert store.state.metrics.tool_calls == 30


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
        store._state.status = AgentStatus.RUNNING
        store._state.steps.append(StepRecord(node="test", status="complete"))

        reset_global_state_store()

        assert store.state.status == AgentStatus.IDLE
        assert store.state.steps == []


class TestPipelineNodes:
    """Tests for PIPELINE_NODES constant."""

    def test_pipeline_nodes_defined(self):
        """Test that PIPELINE_NODES is defined correctly."""
        assert len(PIPELINE_NODES) > 0

        # Check required nodes exist
        node_ids = [n["id"] for n in PIPELINE_NODES]
        expected_ids = ["retrieve", "rerank", "cite_map", "draft", "reflect", "revise", "verify"]

        for expected in expected_ids:
            assert expected in node_ids, f"Expected node '{expected}' not found"

    def test_pipeline_nodes_have_required_fields(self):
        """Test that each pipeline node has required fields."""
        for node in PIPELINE_NODES:
            assert "id" in node
            assert "name" in node
            assert "type" in node
            assert node["type"] in ["tool", "model"]
