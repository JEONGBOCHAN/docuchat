# -*- coding: utf-8 -*-
"""Tests for the MCP Server tools module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from src.mcp_server.tools import (
    get_agent_status,
    run_rag_query,
    reset_agent_state,
    validate_channel,
    list_channels,
    create_session,
    get_session,
    delete_session,
    list_sessions,
    run_web_search,
    run_rag_with_web_search,
    _sessions,
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
        channel_id = "test-channel"
        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:00",
        })
        store.update({
            "event": "model_start",
            "channel_id": channel_id,
            "node": "Draft",
            "timestamp": "2024-01-01T00:00:01",
        })

        result = await get_agent_status(state_store=store, channel_id=channel_id)

        assert result["status"] == "running"
        assert result["current_node"] == "Draft"

    @pytest.mark.asyncio
    async def test_with_global_store(self):
        """Test get_agent_status with global state store."""
        reset_global_state_store()

        result = await get_agent_status()

        # Without any events, should return idle state
        assert result["status"] == "idle"

    @pytest.mark.asyncio
    async def test_returns_metrics(self):
        """Test that get_agent_status returns metrics."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # Add some events to populate metrics
        for i in range(5):
            store.update({
                "event": "tool_start",
                "channel_id": channel_id,
                "node": f"tool_{i}",
                "timestamp": f"2024-01-01T00:00:0{i}",
            })
            store.update({
                "event": "tool_complete",
                "channel_id": channel_id,
                "node": f"tool_{i}",
                "data": {"duration_ms": 100},
            })
        # Add model calls
        for i in range(2):
            store.update({
                "event": "model_start",
                "channel_id": channel_id,
                "node": f"model_{i}",
                "timestamp": f"2024-01-01T00:01:0{i}",
            })
            store.update({
                "event": "model_complete",
                "channel_id": channel_id,
                "node": f"model_{i}",
                "data": {"duration_ms": 200},
            })

        result = await get_agent_status(state_store=store, channel_id=channel_id)

        assert result["metrics"]["total_steps"] == 7  # 5 tool calls + 2 model calls
        assert result["metrics"]["model_calls"] == 2
        assert result["metrics"]["tool_calls"] == 5

    @pytest.mark.asyncio
    async def test_returns_steps(self):
        """Test that get_agent_status returns steps."""
        store = AgentStateStore()
        channel_id = "test-channel"

        store.update({
            "event": "tool_start",
            "channel_id": channel_id,
            "node": "search_documents",
            "timestamp": "2024-01-01T00:00:00",
        })
        store.update({
            "event": "tool_complete",
            "channel_id": channel_id,
            "node": "search_documents",
            "data": {"duration_ms": 100},
        })

        result = await get_agent_status(state_store=store, channel_id=channel_id)

        assert "steps" in result
        assert len(result["steps"]) == 1
        assert result["steps"][0]["node"] == "search_documents"
        assert result["steps"][0]["status"] == "complete"


class TestResetAgentState:
    """Tests for reset_agent_state function."""

    @pytest.mark.asyncio
    async def test_with_custom_store(self):
        """Test reset_agent_state with custom state store."""
        store = AgentStateStore()
        channel_id = "test-channel"

        # Add some events
        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:00",
        })
        for i in range(10):
            store.update({
                "event": "tool_start",
                "channel_id": channel_id,
                "node": f"tool_{i}",
                "timestamp": f"2024-01-01T00:00:0{i}",
            })

        result = await reset_agent_state(state_store=store, channel_id=channel_id)

        assert "message" in result
        assert "state" in result
        assert result["state"]["status"] == "idle"
        assert result["state"]["current_node"] is None
        assert result["state"]["metrics"]["total_steps"] == 0

    @pytest.mark.asyncio
    async def test_with_global_store(self):
        """Test reset_agent_state with global state store."""
        reset_global_state_store()
        store = get_global_state_store()
        channel_id = "_default"
        store.update({
            "event": "agent_start",
            "channel_id": channel_id,
            "timestamp": "2024-01-01T00:00:00",
        })

        result = await reset_agent_state()

        assert result["state"]["status"] == "idle"

    @pytest.mark.asyncio
    async def test_returns_confirmation_message(self):
        """Test that reset_agent_state returns confirmation message."""
        store = AgentStateStore()

        result = await reset_agent_state(state_store=store)

        assert "reset" in result["message"].lower()


class TestRunRagQuery:
    """Tests for run_rag_query function (Clean Architecture version)."""

    def setup_method(self):
        """Clear sessions before each test."""
        _sessions.clear()

    @pytest.mark.asyncio
    async def test_successful_query(self):
        """Test successful RAG query execution."""
        store = AgentStateStore()

        @dataclass
        class MockResult:
            response: str = "This is the answer"
            sources: list = None
            iterations: int = 2
            error: str = None
            tools_used: list = None

            def __post_init__(self):
                if self.sources is None:
                    self.sources = [{"source": "doc1.pdf", "content": "relevant text"}]
                if self.tools_used is None:
                    self.tools_used = []

        mock_use_case = Mock()
        mock_use_case.execute.return_value = MockResult()

        with patch("src.modules.conversation.public.create_process_query_use_case", return_value=mock_use_case):
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
    async def test_query_error_handling(self):
        """Test run_rag_query error handling."""
        store = AgentStateStore()

        with patch(
            "src.modules.conversation.public.create_process_query_use_case",
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

    @pytest.mark.asyncio
    async def test_query_with_global_store(self):
        """Test run_rag_query with global state store."""
        reset_global_state_store()

        @dataclass
        class MockResult:
            response: str = "Global result"
            sources: list = None
            iterations: int = 1
            error: str = None
            tools_used: list = None

            def __post_init__(self):
                if self.sources is None:
                    self.sources = []
                if self.tools_used is None:
                    self.tools_used = []

        mock_use_case = Mock()
        mock_use_case.execute.return_value = MockResult()

        with patch("src.modules.conversation.public.create_process_query_use_case", return_value=mock_use_case):
            result = await run_rag_query(
                channel_id="channel",
                query="query",
            )

        assert result["response"] == "Global result"


class TestChannelTools:
    """Tests for channel-related tools."""

    @pytest.mark.asyncio
    async def test_validate_channel_success(self):
        """Test validating an existing channel."""
        mock_channel = Mock()
        mock_channel.display_name = "Test Channel"

        mock_channel_port = Mock()
        mock_channel_port.get_channel.return_value = mock_channel

        with patch("src.infrastructure.di.create_channel_port", return_value=mock_channel_port):
            result = await validate_channel("test-channel")

        assert result["valid"] is True
        assert result["channel_id"] == "test-channel"
        assert result["display_name"] == "Test Channel"

    @pytest.mark.asyncio
    async def test_validate_channel_not_found(self):
        """Test validating a non-existent channel."""
        mock_channel_port = Mock()
        mock_channel_port.get_channel.return_value = None

        with patch("src.infrastructure.di.create_channel_port", return_value=mock_channel_port):
            result = await validate_channel("nonexistent")

        assert result["valid"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_list_channels_success(self):
        """Test listing channels."""
        mock_channel1 = Mock()
        mock_channel1.name = "stores/store1"
        mock_channel1.display_name = "Channel 1"

        mock_channel2 = Mock()
        mock_channel2.name = "stores/store2"
        mock_channel2.display_name = "Channel 2"

        mock_channel_port = Mock()
        mock_channel_port.list_channels.return_value = [mock_channel1, mock_channel2]

        with patch("src.infrastructure.di.create_channel_port", return_value=mock_channel_port):
            result = await list_channels()

        assert result["total"] == 2
        assert len(result["channels"]) == 2


class TestSessionTools:
    """Tests for session management tools."""

    def setup_method(self):
        """Clear sessions before each test."""
        _sessions.clear()

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test creating a new session."""
        mock_channel = Mock()
        mock_channel.display_name = "Test Channel"

        mock_channel_port = Mock()
        mock_channel_port.get_channel.return_value = mock_channel

        with patch("src.infrastructure.di.create_channel_port", return_value=mock_channel_port):
            result = await create_session("test-channel")

        assert result["success"] is True
        assert "session_id" in result
        assert result["channel_id"] == "test-channel"

    @pytest.mark.asyncio
    async def test_create_session_invalid_channel(self):
        """Test creating session with invalid channel."""
        mock_channel_port = Mock()
        mock_channel_port.get_channel.return_value = None

        with patch("src.infrastructure.di.create_channel_port", return_value=mock_channel_port):
            result = await create_session("invalid-channel")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_session_success(self):
        """Test getting an existing session."""
        # Create a session first
        _sessions["test-session"] = {
            "session_id": "test-session",
            "channel_id": "channel1",
        }

        result = await get_session("test-session")

        assert result["success"] is True
        assert result["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test getting a non-existent session."""
        result = await get_session("nonexistent")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_delete_session_success(self):
        """Test deleting a session."""
        _sessions["test-session"] = {"session_id": "test-session"}

        result = await delete_session("test-session")

        assert result["success"] is True
        assert "test-session" not in _sessions

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        """Test listing all sessions."""
        _sessions["session1"] = {"session_id": "session1", "channel_id": "ch1"}
        _sessions["session2"] = {"session_id": "session2", "channel_id": "ch2"}

        result = await list_sessions()

        assert result["total"] == 2
        assert len(result["sessions"]) == 2


class TestWebSearchTools:
    """Tests for web search tools."""

    @pytest.mark.asyncio
    async def test_web_search_success(self):
        """Test successful web search."""
        @dataclass
        class MockSearchResult:
            title: str
            url: str
            snippet: str
            score: float

        mock_results = [
            MockSearchResult(title="Result 1", url="https://example.com/1", snippet="Snippet 1", score=0.9),
            MockSearchResult(title="Result 2", url="https://example.com/2", snippet="Snippet 2", score=0.8),
        ]

        mock_adapter = Mock()
        mock_adapter.search.return_value = mock_results

        with patch("src.infrastructure.external.mcp.McpWebSearchAdapter", return_value=mock_adapter):
            result = await run_web_search("test query")

        assert result["success"] is True
        assert result["total"] == 2
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_web_search_error(self):
        """Test web search error handling."""
        with patch(
            "src.infrastructure.external.mcp.McpWebSearchAdapter",
            side_effect=Exception("API Error"),
        ):
            result = await run_web_search("test query")

        assert result["success"] is False
        assert "error" in result


class TestToolsModuleImports:
    """Tests for module imports and dependencies."""

    def test_can_import_tools(self):
        """Test that tools can be imported."""
        from src.mcp_server import tools

        assert hasattr(tools, "get_agent_status")
        assert hasattr(tools, "run_rag_query")
        assert hasattr(tools, "reset_agent_state")
        assert hasattr(tools, "validate_channel")
        assert hasattr(tools, "list_channels")
        assert hasattr(tools, "create_session")
        assert hasattr(tools, "get_session")
        assert hasattr(tools, "delete_session")
        assert hasattr(tools, "list_sessions")
        assert hasattr(tools, "run_web_search")
        assert hasattr(tools, "run_rag_with_web_search")

    def test_functions_are_async(self):
        """Test that tool functions are async."""
        import inspect

        from src.mcp_server.tools import (
            get_agent_status,
            run_rag_query,
            reset_agent_state,
            validate_channel,
            list_channels,
            create_session,
            get_session,
            delete_session,
            list_sessions,
            run_web_search,
            run_rag_with_web_search,
        )

        assert inspect.iscoroutinefunction(get_agent_status)
        assert inspect.iscoroutinefunction(run_rag_query)
        assert inspect.iscoroutinefunction(reset_agent_state)
        assert inspect.iscoroutinefunction(validate_channel)
        assert inspect.iscoroutinefunction(list_channels)
        assert inspect.iscoroutinefunction(create_session)
        assert inspect.iscoroutinefunction(get_session)
        assert inspect.iscoroutinefunction(delete_session)
        assert inspect.iscoroutinefunction(list_sessions)
        assert inspect.iscoroutinefunction(run_web_search)
        assert inspect.iscoroutinefunction(run_rag_with_web_search)
