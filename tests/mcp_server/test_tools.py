# -*- coding: utf-8 -*-
"""Tests for the MCP Server tools module."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.mcp_server.tools import (
    get_agent_status,
    run_rag_query,
    reset_agent_state,
)
from src.mcp_server.state import (
    AgentStateStore,
    AgentStatus,
    get_global_state_store,
    reset_global_state_store,
)


class TestGetAgentStatus:
    """Tests for get_agent_status function."""

    @pytest.mark.asyncio
    async def test_with_custom_store(self):
        """Test get_agent_status with custom state store."""
        store = AgentStateStore()
        store._state.status = AgentStatus.RUNNING
        store._state.current_node = "Draft"

        result = await get_agent_status(state_store=store)

        assert result["status"] == "running"
        assert result["current_node"] == "Draft"

    @pytest.mark.asyncio
    async def test_with_global_store(self):
        """Test get_agent_status with global state store."""
        reset_global_state_store()
        store = get_global_state_store()
        store._state.status = AgentStatus.COMPLETE

        result = await get_agent_status()

        assert result["status"] == "complete"

    @pytest.mark.asyncio
    async def test_returns_metrics(self):
        """Test that get_agent_status returns metrics."""
        store = AgentStateStore()
        store._state.metrics.total_steps = 5
        store._state.metrics.model_calls = 2
        store._state.metrics.tool_calls = 3

        result = await get_agent_status(state_store=store)

        assert result["metrics"]["total_steps"] == 5
        assert result["metrics"]["model_calls"] == 2
        assert result["metrics"]["tool_calls"] == 3

    @pytest.mark.asyncio
    async def test_returns_pipeline_nodes(self):
        """Test that get_agent_status returns pipeline nodes."""
        store = AgentStateStore()

        result = await get_agent_status(state_store=store)

        assert "pipeline_nodes" in result
        assert len(result["pipeline_nodes"]) > 0

        # Check that nodes have expected structure
        node = result["pipeline_nodes"][0]
        assert "id" in node
        assert "name" in node
        assert "type" in node
        assert "status" in node


class TestResetAgentState:
    """Tests for reset_agent_state function."""

    @pytest.mark.asyncio
    async def test_with_custom_store(self):
        """Test reset_agent_state with custom state store."""
        store = AgentStateStore()
        store._state.status = AgentStatus.ERROR
        store._state.current_node = "Reflect"
        store._state.metrics.total_steps = 10

        result = await reset_agent_state(state_store=store)

        assert "message" in result
        assert "state" in result
        assert result["state"]["status"] == "idle"
        assert result["state"]["current_node"] is None
        assert result["state"]["metrics"]["total_steps"] == 0

    @pytest.mark.asyncio
    async def test_with_global_store(self):
        """Test reset_agent_state with global state store."""
        store = get_global_state_store()
        store._state.status = AgentStatus.RUNNING

        result = await reset_agent_state()

        assert result["state"]["status"] == "idle"

    @pytest.mark.asyncio
    async def test_returns_confirmation_message(self):
        """Test that reset_agent_state returns confirmation message."""
        store = AgentStateStore()

        result = await reset_agent_state(state_store=store)

        assert "reset" in result["message"].lower()


class TestRunRagQuery:
    """Tests for run_rag_query function."""

    @pytest.mark.asyncio
    async def test_successful_query(self):
        """Test successful RAG query execution."""
        store = AgentStateStore()

        mock_result = {
            "response": "This is the answer",
            "sources": [{"source": "doc1.pdf", "content": "relevant text"}],
            "iterations": 2,
            "error": None,
        }

        with patch("src.agents.rag_agent.run_rag_agent", return_value=mock_result):
            result = await run_rag_query(
                channel_id="test-channel",
                query="What is the answer?",
                state_store=store,
            )

        assert result["response"] == "This is the answer"
        assert len(result["sources"]) == 1
        assert result["iterations"] == 2
        assert result["error"] is None
        assert "state" in result

    @pytest.mark.asyncio
    async def test_query_resets_state(self):
        """Test that run_rag_query resets state before running."""
        store = AgentStateStore()
        store._state.status = AgentStatus.ERROR
        store._state.metrics.total_steps = 100

        mock_result = {"response": "Answer", "sources": [], "iterations": 1, "error": None}

        with patch("src.agents.rag_agent.run_rag_agent", return_value=mock_result):
            await run_rag_query(
                channel_id="channel",
                query="query",
                state_store=store,
            )

        # State should have been reset, then updated by middleware
        # The metrics from previous run should be cleared
        assert store.state.metrics.total_steps != 100 or store.state.status != AgentStatus.ERROR

    @pytest.mark.asyncio
    async def test_query_error_handling(self):
        """Test run_rag_query error handling."""
        store = AgentStateStore()

        with patch(
            "src.agents.rag_agent.run_rag_agent",
            side_effect=RuntimeError("Connection failed"),
        ):
            result = await run_rag_query(
                channel_id="channel",
                query="query",
                state_store=store,
            )

        assert "Error" in result["response"]
        assert result["error"] == "Connection failed"
        assert result["sources"] == []
        assert result["iterations"] == 0
        # State should reflect error
        assert result["state"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_query_passes_middleware_to_agent(self):
        """Test that run_rag_query passes middleware to the agent."""
        store = AgentStateStore()

        captured_middleware = []

        def mock_run_rag_agent(channel_id, query, middleware=None):
            captured_middleware.append(middleware)
            return {
                "response": "OK",
                "sources": [],
                "iterations": 1,
                "error": None,
            }

        with patch("src.agents.rag_agent.run_rag_agent", side_effect=mock_run_rag_agent):
            await run_rag_query(
                channel_id="channel",
                query="query",
                state_store=store,
            )

        # Should have passed a list with DashboardMiddleware
        assert len(captured_middleware) == 1
        assert captured_middleware[0] is not None
        assert len(captured_middleware[0]) == 1
        assert "DashboardMiddleware" in type(captured_middleware[0][0]).__name__

    @pytest.mark.asyncio
    async def test_query_with_global_store(self):
        """Test run_rag_query with global state store."""
        reset_global_state_store()

        mock_result = {"response": "Global result", "sources": [], "iterations": 1, "error": None}

        with patch("src.agents.rag_agent.run_rag_agent", return_value=mock_result):
            result = await run_rag_query(
                channel_id="channel",
                query="query",
            )

        assert result["response"] == "Global result"


class TestRunRagQueryStateIntegration:
    """Integration tests for run_rag_query state updates."""

    @pytest.mark.asyncio
    async def test_middleware_updates_state(self):
        """Test that middleware properly updates state during execution."""
        store = AgentStateStore()
        states_received = []

        def capture_states(state_dict):
            # Subscribe receives state dictionaries, not events
            states_received.append(state_dict.copy())

        store.subscribe(capture_states)

        # Create a mock that simulates middleware being called
        def mock_run_agent_with_middleware(channel_id, query, middleware=None):
            if middleware:
                # Simulate middleware calls by calling the store's update method
                # The store.update method handles events
                store.update({
                    "event": "agent_start",
                    "timestamp": "2024-01-01T00:00:00",
                    "data": {"query": query},
                })
                store.update({
                    "event": "model_start",
                    "node": "Draft",
                    "timestamp": "2024-01-01T00:00:01",
                    "data": {"type": "model"},
                })
                store.update({
                    "event": "model_complete",
                    "node": "Draft",
                    "data": {"duration_ms": 500},
                })
                store.update({
                    "event": "agent_complete",
                    "timestamp": "2024-01-01T00:00:02",
                })

            return {
                "response": "Test answer",
                "sources": [],
                "iterations": 1,
                "error": None,
            }

        with patch("src.agents.rag_agent.run_rag_agent", side_effect=mock_run_agent_with_middleware):
            result = await run_rag_query(
                channel_id="test",
                query="What is X?",
                state_store=store,
            )

        # Check states were received (subscribers get state dicts)
        assert len(states_received) > 0

        # Verify state progression
        statuses = [s["status"] for s in states_received]
        assert "running" in statuses  # Started running
        assert statuses[-1] == "complete"  # Ended complete

        # Final state should be complete
        assert result["state"]["status"] == "complete"


class TestToolsModuleImports:
    """Tests for module imports and dependencies."""

    def test_can_import_tools(self):
        """Test that tools can be imported."""
        from src.mcp_server import tools

        assert hasattr(tools, "get_agent_status")
        assert hasattr(tools, "run_rag_query")
        assert hasattr(tools, "reset_agent_state")

    def test_functions_are_async(self):
        """Test that tool functions are async."""
        import asyncio
        import inspect

        from src.mcp_server.tools import get_agent_status, run_rag_query, reset_agent_state

        assert inspect.iscoroutinefunction(get_agent_status)
        assert inspect.iscoroutinefunction(run_rag_query)
        assert inspect.iscoroutinefunction(reset_agent_state)
