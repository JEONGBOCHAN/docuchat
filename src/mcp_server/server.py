# -*- coding: utf-8 -*-
"""
MCP Server for agent dashboard visualization.

Provides an MCP (Model Context Protocol) Apps server with real-time
agent state visualization through UI resources and tools.
"""

import json
import os
from typing import Any

from mcp.server import FastMCP

from src.mcp_server.state import get_global_state_store, reset_global_state_store


# ============================================================
# MCP Server Instance
# ============================================================

mcp_server = FastMCP(
    name="agent-dashboard",
    instructions="""
    This MCP server provides real-time visualization of agent execution.

    Available tools:
    - get_agent_status: View current agent execution state
    - run_rag_query: Run a RAG query with state visualization
    - reset_agent_state: Reset agent to idle state

    The dashboard UI resource (ui://dashboard/agent-status) shows:
    - Agent status (idle/running/complete/error)
    - Pipeline visualization with node states
    - Execution metrics and timing
    """,
)


# ============================================================
# Helper Functions
# ============================================================

def load_template(name: str) -> str:
    """Load an HTML template from the templates directory.

    Args:
        name: Template filename (e.g., "dashboard.html")

    Returns:
        Template content as string.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    template_path = os.path.join(template_dir, name)
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def inject_state_into_template(html: str, state: dict[str, Any]) -> str:
    """Inject current state into HTML template.

    Replaces the __INITIAL_STATE__ placeholder with JSON-encoded state.

    Args:
        html: HTML template content.
        state: State dictionary to inject.

    Returns:
        HTML with state injected.
    """
    state_json = json.dumps(state)
    return html.replace("__INITIAL_STATE__", state_json)


# ============================================================
# UI Resources
# ============================================================

@mcp_server.resource(
    uri="ui://dashboard/agent-status",
    name="agent-status-dashboard",
    title="Agent Status Dashboard",
    description="Real-time visualization of agent execution state",
    mime_type="text/html",
)
async def agent_status_ui() -> str:
    """Serve the agent status dashboard UI.

    Returns HTML with the current state injected for initial render.
    The UI updates in real-time via postMessage events.
    """
    store = get_global_state_store()
    state = store.get_state()
    html = load_template("dashboard.html")
    return inject_state_into_template(html, state)


# ============================================================
# Tools
# ============================================================

@mcp_server.tool(
    name="get_agent_status",
    title="Get Agent Status",
    description="Get the current agent execution status including pipeline state, metrics, and execution history.",
    meta={"ui/resourceUri": "ui://dashboard/agent-status"},
)
async def get_agent_status_tool() -> dict[str, Any]:
    """Get the current agent execution status.

    Returns a dictionary containing:
    - status: Overall agent status (idle/running/complete/error)
    - current_node: Currently executing node
    - steps: List of execution steps with timing
    - metrics: Execution metrics (duration, call counts)
    - pipeline_nodes: Pipeline visualization data
    """
    store = get_global_state_store()
    return store.get_state()


@mcp_server.tool(
    name="run_rag_query",
    title="Run RAG Query",
    description="Run a RAG (Retrieval-Augmented Generation) query and visualize execution in the dashboard.",
    meta={"ui/resourceUri": "ui://dashboard/agent-status"},
)
async def run_rag_query_tool(channel_id: str, query: str) -> dict[str, Any]:
    """Run a RAG query with dashboard visualization.

    Args:
        channel_id: The channel (FileSearchStore) ID to search in.
        query: The user's question to answer.

    Returns:
        Dictionary with response, sources, and execution state.
    """
    # Import here to avoid circular imports and ensure fresh imports
    from src.mcp_server.tools import run_rag_query

    return await run_rag_query(channel_id=channel_id, query=query)


@mcp_server.tool(
    name="reset_agent_state",
    title="Reset Agent State",
    description="Reset the agent execution state to idle. Use before starting a new conversation.",
)
async def reset_agent_state_tool() -> dict[str, Any]:
    """Reset agent state to idle.

    Returns confirmation message and the new state.
    """
    reset_global_state_store()
    store = get_global_state_store()
    return {
        "message": "Agent state reset to idle",
        "state": store.get_state(),
    }


# ============================================================
# Entry Point
# ============================================================

def run_server() -> None:
    """Run the MCP server using stdio transport.

    This is the entry point when running the server directly.
    """
    import asyncio
    asyncio.run(mcp_server.run_stdio_async())


if __name__ == "__main__":
    run_server()
