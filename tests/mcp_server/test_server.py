# -*- coding: utf-8 -*-
"""Tests for the MCP Server module."""

import json
import os
import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.mcp_server.server import (
    mcp_server,
    load_template,
    inject_state_into_template,
)
from src.mcp_server.state import (
    AgentStateStore,
    AgentStatus,
    get_global_state_store,
    reset_global_state_store,
)


class TestMcpServerInstance:
    """Tests for the MCP server instance."""

    def test_server_name(self):
        """Test that the MCP server has the correct name."""
        assert mcp_server.name == "docuchat"

    def test_server_has_instructions(self):
        """Test that the MCP server has instructions."""
        assert mcp_server.instructions is not None
        assert "agent" in mcp_server.instructions.lower()


class TestLoadTemplate:
    """Tests for load_template function."""

    def test_load_dashboard_template(self):
        """Test loading the dashboard.html template."""
        html = load_template("dashboard.html")

        assert html is not None
        assert len(html) > 0
        assert "<!DOCTYPE html>" in html
        assert "Agent Status Dashboard" in html

    def test_load_nonexistent_template(self):
        """Test that loading nonexistent template raises error."""
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent.html")


class TestInjectStateIntoTemplate:
    """Tests for inject_state_into_template function."""

    def test_inject_state(self):
        """Test injecting state into template."""
        template = "<script>let state = __INITIAL_STATE__;</script>"
        state = {"status": "running", "current_node": "Draft"}

        result = inject_state_into_template(template, state)

        assert "__INITIAL_STATE__" not in result
        assert '"status": "running"' in result
        assert '"current_node": "Draft"' in result

    def test_inject_empty_state(self):
        """Test injecting empty state."""
        template = "<script>let state = __INITIAL_STATE__;</script>"
        state = {}

        result = inject_state_into_template(template, state)

        assert "{}" in result

    def test_inject_complex_state(self):
        """Test injecting complex state with nested data."""
        template = "var state = __INITIAL_STATE__;"
        state = {
            "status": "complete",
            "steps": [
                {"node": "Draft", "status": "complete"},
                {"node": "Reflect", "status": "running"},
            ],
            "metrics": {"total_steps": 2, "model_calls": 2},
        }

        result = inject_state_into_template(template, state)

        # Verify JSON is valid by parsing it
        json_str = result.replace("var state = ", "").replace(";", "")
        parsed = json.loads(json_str)

        assert parsed["status"] == "complete"
        assert len(parsed["steps"]) == 2


class TestAgentStatusUi:
    """Tests for agent_status_ui resource function."""

    @pytest.mark.asyncio
    async def test_agent_status_ui_returns_html(self):
        """Test that agent_status_ui returns HTML content."""
        # Reset global state
        reset_global_state_store()

        # Import the function directly
        from src.mcp_server.server import agent_status_ui

        html = await agent_status_ui()

        assert html is not None
        assert "<!DOCTYPE html>" in html
        assert "Agent Status Dashboard" in html

    @pytest.mark.asyncio
    async def test_agent_status_ui_includes_initial_state(self):
        """Test that agent_status_ui includes initial state."""
        # Reset and modify global state
        reset_global_state_store()
        store = get_global_state_store()
        store._state.status = AgentStatus.RUNNING
        store._state.current_node = "Draft"

        from src.mcp_server.server import agent_status_ui

        html = await agent_status_ui()

        # The initial state should be injected
        assert "__INITIAL_STATE__" not in html
        assert "running" in html


class TestGetAgentStatusTool:
    """Tests for get_agent_status_tool MCP tool."""

    @pytest.mark.asyncio
    async def test_get_agent_status_returns_state(self):
        """Test that get_agent_status_tool returns current state."""
        # Reset global state
        reset_global_state_store()
        store = get_global_state_store()
        store._state.status = AgentStatus.RUNNING
        store._state.current_node = "Draft"
        store._state.metrics.total_steps = 5

        from src.mcp_server.server import get_agent_status_tool

        result = await get_agent_status_tool()

        assert isinstance(result, dict)
        assert result["status"] == "running"
        assert result["current_node"] == "Draft"
        assert result["metrics"]["total_steps"] == 5

    @pytest.mark.asyncio
    async def test_get_agent_status_idle_state(self):
        """Test get_agent_status_tool with idle state."""
        reset_global_state_store()

        from src.mcp_server.server import get_agent_status_tool

        result = await get_agent_status_tool()

        assert result["status"] == "idle"
        assert result["current_node"] is None


class TestResetAgentStateTool:
    """Tests for reset_agent_state_tool MCP tool."""

    @pytest.mark.asyncio
    async def test_reset_agent_state(self):
        """Test that reset_agent_state_tool resets state."""
        # Set up a running state
        store = get_global_state_store()
        store._state.status = AgentStatus.RUNNING
        store._state.current_node = "Reflect"
        store._state.metrics.total_steps = 10

        from src.mcp_server.server import reset_agent_state_tool

        result = await reset_agent_state_tool()

        assert "message" in result
        assert "state" in result
        assert result["state"]["status"] == "idle"
        assert result["state"]["current_node"] is None
        assert result["state"]["metrics"]["total_steps"] == 0


class TestRunRagQueryTool:
    """Tests for run_rag_query_tool MCP tool (using Clean Architecture)."""

    @pytest.mark.asyncio
    async def test_run_rag_query_with_mock(self):
        """Test run_rag_query_tool with mocked ProcessQueryUseCase."""
        reset_global_state_store()
        from dataclasses import dataclass

        @dataclass
        class MockResult:
            response: str = "Test response"
            sources: list = None
            iterations: int = 2
            error: str = None
            tools_used: list = None

            def __post_init__(self):
                if self.sources is None:
                    self.sources = [{"source": "doc1.pdf"}]
                if self.tools_used is None:
                    self.tools_used = []

        mock_use_case = Mock()
        mock_use_case.execute.return_value = MockResult()

        with patch("src.infrastructure.di.create_process_query_use_case", return_value=mock_use_case):
            from src.mcp_server.server import run_rag_query_tool

            result = await run_rag_query_tool(
                channel_id="test-channel",
                query="What is X?",
            )

            assert result["response"] == "Test response"
            assert len(result["sources"]) == 1
            assert result["iterations"] == 2
            assert "state" in result

    @pytest.mark.asyncio
    async def test_run_rag_query_error_handling(self):
        """Test run_rag_query_tool error handling."""
        reset_global_state_store()

        # Mock the create_process_query_use_case function to raise an error
        with patch(
            "src.infrastructure.di.create_process_query_use_case",
            side_effect=RuntimeError("API Error"),
        ):
            from src.mcp_server.server import run_rag_query_tool

            result = await run_rag_query_tool(
                channel_id="test-channel",
                query="What is X?",
            )

            assert "Error" in result["response"]
            assert result["error"] == "API Error"


class TestMcpServerTools:
    """Tests for MCP server tool registrations."""

    @pytest.mark.asyncio
    async def test_tools_are_registered(self):
        """Test that expected tools are registered."""
        tools = await mcp_server.list_tools()

        tool_names = [t.name for t in tools]
        assert "get_agent_status" in tool_names
        assert "run_rag_query" in tool_names
        assert "reset_agent_state" in tool_names

    @pytest.mark.asyncio
    async def test_get_agent_status_tool_metadata(self):
        """Test get_agent_status tool has correct metadata."""
        tools = await mcp_server.list_tools()
        tool = next((t for t in tools if t.name == "get_agent_status"), None)

        assert tool is not None
        assert "agent" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_run_rag_query_tool_has_parameters(self):
        """Test run_rag_query tool has required parameters."""
        tools = await mcp_server.list_tools()
        tool = next((t for t in tools if t.name == "run_rag_query"), None)

        assert tool is not None
        # Tool should have input schema with channel_id and query
        assert tool.inputSchema is not None


class TestMcpServerResources:
    """Tests for MCP server resource registrations."""

    @pytest.mark.asyncio
    async def test_resources_are_registered(self):
        """Test that expected resources are registered."""
        resources = await mcp_server.list_resources()

        resource_uris = [str(r.uri) for r in resources]
        assert "ui://dashboard/agent-status" in resource_uris

    @pytest.mark.asyncio
    async def test_dashboard_resource_metadata(self):
        """Test dashboard resource has correct metadata."""
        resources = await mcp_server.list_resources()
        dashboard = next(
            (r for r in resources if "agent-status" in str(r.uri)),
            None,
        )

        assert dashboard is not None
        assert dashboard.mimeType == "text/html"


class TestDashboardHtmlTemplate:
    """Tests for the dashboard HTML template content."""

    def test_template_has_status_indicator(self):
        """Test that template has status indicator element."""
        html = load_template("dashboard.html")

        assert 'id="statusIndicator"' in html
        assert 'id="statusText"' in html

    def test_template_has_pipeline_nodes(self):
        """Test that template has pipeline node elements."""
        html = load_template("dashboard.html")

        assert 'data-node="retrieve"' in html
        assert 'data-node="draft"' in html
        assert 'data-node="reflect"' in html

    def test_template_has_metrics_panel(self):
        """Test that template has metrics panel elements."""
        html = load_template("dashboard.html")

        assert 'id="currentNode"' in html
        assert 'id="totalSteps"' in html
        assert 'id="modelCalls"' in html
        assert 'id="toolCalls"' in html
        assert 'id="duration"' in html

    def test_template_has_postmessage_handler(self):
        """Test that template has postMessage event handler."""
        html = load_template("dashboard.html")

        assert "window.addEventListener('message'" in html
        assert "mcp_state" in html

    def test_template_has_initial_state_placeholder(self):
        """Test that template has initial state placeholder."""
        html = load_template("dashboard.html")

        assert "__INITIAL_STATE__" in html

    def test_template_has_dark_theme(self):
        """Test that template uses dark theme colors."""
        html = load_template("dashboard.html")

        # Check for dark theme background colors
        assert "#1a1a2e" in html  # Dark background
        assert "#2d2d44" in html  # Card background

    def test_template_has_status_styles(self):
        """Test that template has status-specific styles."""
        html = load_template("dashboard.html")

        assert ".status-idle" in html
        assert ".status-running" in html
        assert ".status-complete" in html
        assert ".status-error" in html
