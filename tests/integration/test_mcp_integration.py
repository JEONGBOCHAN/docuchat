# -*- coding: utf-8 -*-
"""
MCP Server Integration Tests.

Tests for the MCP Apps server including:
- State store functionality
- Tool registration and execution
- UI resource serving
- Dashboard middleware integration
"""

import json
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.mcp_server.state import (
    AgentStateStore,
    AgentStatus,
    NodeStatus,
    PIPELINE_NODES,
    get_global_state_store,
    reset_global_state_store,
)
from src.mcp_server.tools import (
    get_agent_status,
    reset_agent_state,
)


# ============================================================
# AgentStateStore Tests
# ============================================================

class TestAgentStateStore:
    """Test suite for AgentStateStore functionality."""

    def test_initial_state(self, mcp_state_store):
        """Test that initial state is idle with no steps."""
        state = mcp_state_store.get_state()

        assert state["status"] == "idle"
        assert state["current_node"] is None
        assert state["current_query"] is None
        assert state["steps"] == []
        assert state["metrics"]["total_steps"] == 0
        assert state["metrics"]["model_calls"] == 0
        assert state["metrics"]["tool_calls"] == 0
        assert state["last_error"] is None

    def test_reset_state(self, mcp_state_store):
        """Test that reset clears the state."""
        # Modify state
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        # Verify state changed
        state = mcp_state_store.get_state()
        assert state["status"] == "running"

        # Reset
        mcp_state_store.reset()

        # Verify reset
        state = mcp_state_store.get_state()
        assert state["status"] == "idle"
        assert state["steps"] == []

    def test_pipeline_nodes_in_state(self, mcp_state_store):
        """Test that pipeline nodes are included in state."""
        state = mcp_state_store.get_state()

        assert "pipeline_nodes" in state
        assert len(state["pipeline_nodes"]) == len(PIPELINE_NODES)

        # Verify all nodes are initially pending
        for node in state["pipeline_nodes"]:
            assert node["status"] == "pending"
            assert "id" in node
            assert "name" in node
            assert "type" in node

    def test_agent_start_event(self, mcp_state_store):
        """Test handling of agent_start event."""
        timestamp = datetime.now().isoformat()

        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": timestamp,
            "data": {"query": "What is the document about?"},
        })

        state = mcp_state_store.get_state()

        assert state["status"] == "running"
        assert state["current_query"] == "What is the document about?"
        assert state["metrics"]["start_time"] == timestamp

    def test_agent_complete_event(self, mcp_state_store):
        """Test handling of agent_complete event."""
        # Start first
        start_time = "2024-01-01T10:00:00"
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": start_time,
        })

        # Complete
        end_time = "2024-01-01T10:00:05"
        mcp_state_store.update({
            "event": "agent_complete",
            "timestamp": end_time,
        })

        state = mcp_state_store.get_state()

        assert state["status"] == "complete"
        assert state["current_node"] is None
        assert state["metrics"]["end_time"] == end_time
        assert state["metrics"]["total_duration_ms"] == 5000.0

    def test_agent_error_event(self, mcp_state_store):
        """Test handling of agent_error event."""
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        mcp_state_store.update({
            "event": "agent_error",
            "timestamp": datetime.now().isoformat(),
            "error": "Test error message",
        })

        state = mcp_state_store.get_state()

        assert state["status"] == "error"
        assert state["last_error"] == "Test error message"
        assert state["current_node"] is None

    def test_model_start_event(self, mcp_state_store):
        """Test handling of model_start event."""
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        mcp_state_store.update({
            "event": "model_start",
            "timestamp": datetime.now().isoformat(),
            "node": "Draft",
            "data": {"type": "model"},
        })

        state = mcp_state_store.get_state()

        assert state["current_node"] == "Draft"
        assert state["metrics"]["model_calls"] == 1
        assert state["metrics"]["total_steps"] == 1
        assert len(state["steps"]) == 1
        assert state["steps"][0]["node"] == "Draft"
        assert state["steps"][0]["status"] == "running"

    def test_model_complete_event(self, mcp_state_store):
        """Test handling of model_complete event."""
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        mcp_state_store.update({
            "event": "model_start",
            "timestamp": datetime.now().isoformat(),
            "node": "Draft",
        })

        mcp_state_store.update({
            "event": "model_complete",
            "timestamp": datetime.now().isoformat(),
            "node": "Draft",
            "data": {"duration_ms": 1500.0},
        })

        state = mcp_state_store.get_state()

        assert state["steps"][0]["status"] == "complete"
        assert state["steps"][0]["duration_ms"] == 1500.0

    def test_tool_events(self, mcp_state_store):
        """Test handling of tool_start and tool_complete events."""
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        # Tool start
        mcp_state_store.update({
            "event": "tool_start",
            "timestamp": datetime.now().isoformat(),
            "node": "Retrieve",
            "data": {"type": "tool"},
        })

        state = mcp_state_store.get_state()
        assert state["current_node"] == "Retrieve"
        assert state["metrics"]["tool_calls"] == 1

        # Tool complete
        mcp_state_store.update({
            "event": "tool_complete",
            "timestamp": datetime.now().isoformat(),
            "node": "Retrieve",
            "data": {"duration_ms": 500.0, "result_preview": "Found 5 documents"},
        })

        state = mcp_state_store.get_state()
        assert state["steps"][0]["status"] == "complete"
        assert state["steps"][0]["duration_ms"] == 500.0
        assert state["steps"][0]["data"].get("result_preview") == "Found 5 documents"

    def test_tool_error_event(self, mcp_state_store):
        """Test handling of tool_error event."""
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        mcp_state_store.update({
            "event": "tool_start",
            "timestamp": datetime.now().isoformat(),
            "node": "Retrieve",
        })

        mcp_state_store.update({
            "event": "tool_error",
            "timestamp": datetime.now().isoformat(),
            "node": "Retrieve",
            "error": "Connection failed",
            "data": {"duration_ms": 100.0},
        })

        state = mcp_state_store.get_state()
        assert state["steps"][0]["status"] == "error"
        assert state["steps"][0]["data"].get("error") == "Connection failed"

    def test_subscriber_notification(self, mcp_state_store_with_capture, mcp_state_events):
        """Test that subscribers are notified of state changes."""
        mcp_state_store_with_capture.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        assert len(mcp_state_events) == 1
        assert mcp_state_events[0]["status"] == "running"

    def test_multiple_steps_sequence(self, mcp_state_store):
        """Test a sequence of multiple steps."""
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
            "data": {"query": "Test query"},
        })

        # Simulate a typical RAG pipeline
        steps = [
            ("tool_start", "Retrieve"),
            ("tool_complete", "Retrieve"),
            ("tool_start", "Rerank"),
            ("tool_complete", "Rerank"),
            ("model_start", "Draft"),
            ("model_complete", "Draft"),
        ]

        for event_type, node in steps:
            mcp_state_store.update({
                "event": event_type,
                "timestamp": datetime.now().isoformat(),
                "node": node,
                "data": {"duration_ms": 100.0} if "complete" in event_type else {},
            })

        state = mcp_state_store.get_state()

        assert state["metrics"]["total_steps"] == 3
        assert state["metrics"]["tool_calls"] == 2
        assert state["metrics"]["model_calls"] == 1
        assert len(state["steps"]) == 3

    def test_pipeline_node_status_from_steps(self, mcp_state_store):
        """Test that pipeline node statuses are derived from steps."""
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        mcp_state_store.update({
            "event": "tool_start",
            "timestamp": datetime.now().isoformat(),
            "node": "Retrieve",
        })

        mcp_state_store.update({
            "event": "tool_complete",
            "timestamp": datetime.now().isoformat(),
            "node": "Retrieve",
        })

        state = mcp_state_store.get_state()

        # Find the retrieve node in pipeline_nodes
        retrieve_node = next(
            (n for n in state["pipeline_nodes"] if n["id"] == "retrieve"),
            None,
        )
        assert retrieve_node is not None
        assert retrieve_node["status"] == "complete"


# ============================================================
# Global State Store Tests
# ============================================================

class TestGlobalStateStore:
    """Test suite for global state store singleton."""

    def test_get_global_state_store_singleton(self):
        """Test that get_global_state_store returns the same instance."""
        reset_global_state_store()

        store1 = get_global_state_store()
        store2 = get_global_state_store()

        assert store1 is store2

    def test_reset_global_state_store(self):
        """Test that reset_global_state_store resets the state."""
        store = get_global_state_store()
        store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        state_before = store.get_state()
        assert state_before["status"] == "running"

        reset_global_state_store()

        state_after = store.get_state()
        assert state_after["status"] == "idle"


# ============================================================
# MCP Tools Tests
# ============================================================

class TestMCPTools:
    """Test suite for MCP tool functions."""

    @pytest.mark.asyncio
    async def test_get_agent_status_tool(self, mcp_state_store):
        """Test get_agent_status tool returns current state."""
        # Modify state
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
            "data": {"query": "Test query"},
        })

        result = await get_agent_status(state_store=mcp_state_store)

        assert result["status"] == "running"
        assert result["current_query"] == "Test query"

    @pytest.mark.asyncio
    async def test_reset_agent_state_tool(self, mcp_state_store):
        """Test reset_agent_state tool resets the state."""
        # Modify state
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        result = await reset_agent_state(state_store=mcp_state_store)

        assert result["message"] == "Agent state reset to idle"
        assert result["state"]["status"] == "idle"


# ============================================================
# Dashboard Middleware Integration Tests
# ============================================================

class TestDashboardMiddlewareIntegration:
    """Test suite for DashboardMiddleware integration with state store."""

    def test_middleware_publishes_to_state_store(
        self,
        mock_dashboard_middleware,
        mcp_state_store,
    ):
        """Test that middleware events update the state store."""
        # Simulate before_agent call
        mock_dashboard_middleware.before_agent(
            state={"messages": [{"role": "user", "content": "Test query"}]},
            runtime=None,
        )

        state = mcp_state_store.get_state()

        assert state["status"] == "running"

    def test_middleware_model_events(
        self,
        mock_dashboard_middleware,
        mcp_state_store,
    ):
        """Test that middleware model events update the state store."""
        # Start agent
        mock_dashboard_middleware.before_agent(
            state={"messages": [{"role": "user", "content": "Test"}]},
            runtime=None,
        )

        # Start model call
        mock_dashboard_middleware.before_model(
            state={"messages": []},
            runtime=None,
        )

        state = mcp_state_store.get_state()
        assert state["metrics"]["model_calls"] == 1
        assert len(state["steps"]) == 1
        assert state["steps"][0]["status"] == "running"

        # Complete model call
        mock_dashboard_middleware.after_model(
            state={"messages": []},
            runtime=None,
        )

        state = mcp_state_store.get_state()
        assert state["steps"][0]["status"] == "complete"

    def test_middleware_after_agent_complete(
        self,
        mock_dashboard_middleware,
        mcp_state_store,
    ):
        """Test that middleware completes agent state."""
        mock_dashboard_middleware.before_agent(
            state={"messages": []},
            runtime=None,
        )

        mock_dashboard_middleware.after_agent(
            state={"messages": [{"role": "assistant", "content": "Final response"}]},
            runtime=None,
        )

        state = mcp_state_store.get_state()

        assert state["status"] == "complete"
        assert state["metrics"]["end_time"] is not None
        assert state["metrics"]["total_duration_ms"] is not None

    def test_middleware_after_agent_error(
        self,
        mock_dashboard_middleware,
        mcp_state_store,
    ):
        """Test that middleware handles agent errors."""
        mock_dashboard_middleware.before_agent(
            state={"messages": []},
            runtime=None,
        )

        mock_dashboard_middleware.after_agent(
            state={"messages": [], "error": "Something went wrong"},
            runtime=None,
        )

        state = mcp_state_store.get_state()

        assert state["status"] == "error"


# ============================================================
# UI Resource Tests
# ============================================================

class TestUIResource:
    """Test suite for UI resource functionality."""

    def test_template_loading(self):
        """Test that dashboard template can be loaded."""
        from src.mcp_server.server import load_template

        html = load_template("dashboard.html")

        assert html is not None
        assert len(html) > 0
        assert "Agent Status Dashboard" in html
        assert "__INITIAL_STATE__" in html

    def test_state_injection(self):
        """Test that state is properly injected into template."""
        from src.mcp_server.server import inject_state_into_template

        html = "const state = __INITIAL_STATE__;"
        state = {"status": "running", "current_node": "Draft"}

        result = inject_state_into_template(html, state)

        assert "__INITIAL_STATE__" not in result
        assert '"status": "running"' in result
        assert '"current_node": "Draft"' in result

    @pytest.mark.asyncio
    async def test_agent_status_ui_resource(self, mcp_state_store):
        """Test the agent_status_ui resource returns valid HTML."""
        from src.mcp_server.server import agent_status_ui

        # Set some state
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
            "data": {"query": "Test query"},
        })

        with patch("src.mcp_server.server.get_global_state_store", return_value=mcp_state_store):
            html = await agent_status_ui()

        assert html is not None
        assert "Agent Status Dashboard" in html
        assert '"status": "running"' in html


# ============================================================
# MCP Server Registration Tests
# ============================================================

class TestMCPServerRegistration:
    """Test suite for MCP server tool and resource registration."""

    def test_mcp_server_instance_exists(self):
        """Test that mcp_server instance is created."""
        from src.mcp_server.server import mcp_server

        assert mcp_server is not None
        assert mcp_server.name == "agent-dashboard"

    def test_mcp_server_has_tools(self):
        """Test that expected tools are registered."""
        from src.mcp_server.server import mcp_server

        # The tools should be registered via decorators
        # We can verify the server has the expected configuration
        assert mcp_server.instructions is not None
        assert "get_agent_status" in mcp_server.instructions
        assert "run_rag_query" in mcp_server.instructions
        assert "reset_agent_state" in mcp_server.instructions


# ============================================================
# End-to-End Workflow Tests
# ============================================================

class TestE2EWorkflow:
    """End-to-end workflow tests for MCP server."""

    def test_complete_rag_workflow_state_tracking(self, mcp_state_store):
        """Test state tracking through a complete RAG workflow simulation."""
        # Simulate a complete RAG workflow
        events = [
            {"event": "agent_start", "data": {"query": "What is the document about?"}},
            {"event": "tool_start", "node": "Retrieve"},
            {"event": "tool_complete", "node": "Retrieve", "data": {"duration_ms": 500}},
            {"event": "tool_start", "node": "Rerank"},
            {"event": "tool_complete", "node": "Rerank", "data": {"duration_ms": 200}},
            {"event": "tool_start", "node": "Cite Map"},
            {"event": "tool_complete", "node": "Cite Map", "data": {"duration_ms": 100}},
            {"event": "model_start", "node": "Draft"},
            {"event": "model_complete", "node": "Draft", "data": {"duration_ms": 2000}},
            {"event": "model_start", "node": "Reflect"},
            {"event": "model_complete", "node": "Reflect", "data": {"duration_ms": 1500}},
            {"event": "model_start", "node": "Revise"},
            {"event": "model_complete", "node": "Revise", "data": {"duration_ms": 1800}},
            {"event": "tool_start", "node": "Verify"},
            {"event": "tool_complete", "node": "Verify", "data": {"duration_ms": 300}},
            {"event": "agent_complete"},
        ]

        for event in events:
            mcp_state_store.update({
                **event,
                "timestamp": datetime.now().isoformat(),
            })

        state = mcp_state_store.get_state()

        # Verify final state
        assert state["status"] == "complete"
        assert state["current_query"] == "What is the document about?"
        assert state["metrics"]["total_steps"] == 7
        assert state["metrics"]["tool_calls"] == 4
        assert state["metrics"]["model_calls"] == 3

        # Verify all steps are complete
        for step in state["steps"]:
            assert step["status"] == "complete"

    def test_error_recovery_workflow(self, mcp_state_store):
        """Test state tracking when an error occurs and is handled."""
        events = [
            {"event": "agent_start", "data": {"query": "Test query"}},
            {"event": "tool_start", "node": "Retrieve"},
            {"event": "tool_error", "node": "Retrieve", "error": "API timeout"},
            {"event": "agent_error", "error": "Failed to retrieve documents"},
        ]

        for event in events:
            mcp_state_store.update({
                **event,
                "timestamp": datetime.now().isoformat(),
            })

        state = mcp_state_store.get_state()

        assert state["status"] == "error"
        assert state["last_error"] == "Failed to retrieve documents"
        assert state["steps"][0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_tools_return_current_state(self, mcp_state_store):
        """Test that tools return the current state correctly."""
        # Setup some state
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
            "data": {"query": "Test"},
        })

        mcp_state_store.update({
            "event": "tool_start",
            "timestamp": datetime.now().isoformat(),
            "node": "Retrieve",
        })

        # Get status
        status = await get_agent_status(state_store=mcp_state_store)

        assert status["status"] == "running"
        assert status["current_node"] == "Retrieve"
        assert status["metrics"]["tool_calls"] == 1

        # Reset
        result = await reset_agent_state(state_store=mcp_state_store)

        assert result["state"]["status"] == "idle"
        assert result["state"]["current_node"] is None


# ============================================================
# Thread Safety Tests
# ============================================================

class TestThreadSafety:
    """Test suite for thread safety of state store."""

    def test_concurrent_updates(self, mcp_state_store):
        """Test that concurrent updates don't cause data corruption."""
        import threading

        errors = []

        def update_state(event_type: str, node: str):
            try:
                for i in range(100):
                    mcp_state_store.update({
                        "event": event_type,
                        "timestamp": datetime.now().isoformat(),
                        "node": f"{node}_{i}",
                    })
            except Exception as e:
                errors.append(e)

        # Start the agent first
        mcp_state_store.update({
            "event": "agent_start",
            "timestamp": datetime.now().isoformat(),
        })

        threads = [
            threading.Thread(target=update_state, args=("tool_start", "tool")),
            threading.Thread(target=update_state, args=("model_start", "model")),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

        # State should be consistent
        state = mcp_state_store.get_state()
        assert state["status"] == "running"
        # Should have 200 steps (100 tool_start + 100 model_start)
        assert state["metrics"]["total_steps"] == 200
