# -*- coding: utf-8 -*-
"""
MCP Server for Document Q&A with Clean Architecture.

Provides all functionality through MCP tools:
- Channel management
- Session management
- Chat with RAG (document search)
- Web search (Tavily)
- Agent status dashboard
"""

import json
import os
from typing import Any

from mcp.server import FastMCP

from src.mcp_server.state import get_global_state_store, reset_global_state_store
from src.mcp_server import tools


# ============================================================
# MCP Server Instance
# ============================================================

mcp_server = FastMCP(
    name="docuchat",
    instructions="""
    Docuchat MCP Server - Document Q&A with AI

    Available tools:

    **Channel Management:**
    - list_channels: List all available document channels
    - validate_channel: Check if a channel exists

    **Session Management:**
    - create_session: Create a new chat session for a channel
    - get_session: Get session information
    - list_sessions: List all active sessions
    - delete_session: Delete a session

    **Chat:**
    - chat: Send a message and get AI response (uses RAG)
    - chat_with_web_search: Chat with web search enabled (Tavily)
    - get_chat_history: Get conversation history
    - clear_chat_history: Clear conversation history

    **Web Search:**
    - web_search: Search the web using Tavily

    **Agent Status:**
    - get_agent_status: View current agent execution state
    - reset_agent_state: Reset agent to idle state

    The dashboard UI resource (ui://dashboard/agent-status) shows real-time
    agent execution visualization.
    """,
)


# ============================================================
# Helper Functions
# ============================================================

def load_template(name: str) -> str:
    """Load an HTML template from the templates directory."""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    template_path = os.path.join(template_dir, name)
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def inject_state_into_template(html: str, state: dict[str, Any]) -> str:
    """Inject current state into HTML template."""
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
    """Serve the agent status dashboard UI."""
    store = get_global_state_store()
    state = store.get_state()
    html = load_template("dashboard.html")
    return inject_state_into_template(html, state)


# ============================================================
# Channel Tools
# ============================================================

@mcp_server.tool(
    name="list_channels",
    title="List Channels",
    description="List all available document channels.",
)
async def list_channels_tool() -> dict[str, Any]:
    """List all available channels."""
    return await tools.list_channels()


@mcp_server.tool(
    name="validate_channel",
    title="Validate Channel",
    description="Check if a channel exists and get its information.",
)
async def validate_channel_tool(channel_id: str) -> dict[str, Any]:
    """Validate if a channel exists.

    Args:
        channel_id: The channel ID to validate.
    """
    return await tools.validate_channel(channel_id)


# ============================================================
# Session Tools
# ============================================================

@mcp_server.tool(
    name="create_session",
    title="Create Session",
    description="Create a new chat session for multi-turn conversation.",
)
async def create_session_tool(channel_id: str) -> dict[str, Any]:
    """Create a new chat session.

    Args:
        channel_id: The channel ID for this session.
    """
    return await tools.create_session(channel_id)


@mcp_server.tool(
    name="get_session",
    title="Get Session",
    description="Get information about a chat session.",
)
async def get_session_tool(session_id: str) -> dict[str, Any]:
    """Get session information.

    Args:
        session_id: The session ID to retrieve.
    """
    return await tools.get_session(session_id)


@mcp_server.tool(
    name="list_sessions",
    title="List Sessions",
    description="List all active chat sessions.",
)
async def list_sessions_tool() -> dict[str, Any]:
    """List all active sessions."""
    return await tools.list_sessions()


@mcp_server.tool(
    name="delete_session",
    title="Delete Session",
    description="Delete a chat session and its history.",
)
async def delete_session_tool(session_id: str) -> dict[str, Any]:
    """Delete a chat session.

    Args:
        session_id: The session ID to delete.
    """
    return await tools.delete_session(session_id)


# ============================================================
# Chat Tools
# ============================================================

@mcp_server.tool(
    name="chat",
    title="Chat",
    description="Send a message and get an AI response based on documents in the channel.",
    meta={"ui/resourceUri": "ui://dashboard/agent-status"},
)
async def chat_tool(
    channel_id: str,
    query: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Chat with the AI using document context.

    Args:
        channel_id: The channel ID containing documents.
        query: Your question or message.
        session_id: Optional session ID for conversation context.
    """
    return await tools.run_rag_query(
        channel_id=channel_id,
        query=query,
        session_id=session_id,
    )


@mcp_server.tool(
    name="chat_with_web_search",
    title="Chat with Web Search",
    description="Send a message and get an AI response using both documents and web search.",
    meta={"ui/resourceUri": "ui://dashboard/agent-status"},
)
async def chat_with_web_search_tool(
    channel_id: str,
    query: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Chat with the AI using documents and web search.

    Args:
        channel_id: The channel ID containing documents.
        query: Your question or message.
        session_id: Optional session ID for conversation context.
    """
    return await tools.run_rag_with_web_search(
        channel_id=channel_id,
        query=query,
        session_id=session_id,
    )


@mcp_server.tool(
    name="get_chat_history",
    title="Get Chat History",
    description="Get the conversation history for a session.",
)
async def get_chat_history_tool(
    session_id: str,
    limit: int = 100,
) -> dict[str, Any]:
    """Get chat history for a session.

    Args:
        session_id: The session ID.
        limit: Maximum number of messages to return (default 100).
    """
    return await tools.get_chat_history(session_id, limit)


@mcp_server.tool(
    name="clear_chat_history",
    title="Clear Chat History",
    description="Clear the conversation history for a session.",
)
async def clear_chat_history_tool(session_id: str) -> dict[str, Any]:
    """Clear chat history for a session.

    Args:
        session_id: The session ID.
    """
    return await tools.clear_chat_history(session_id)


# ============================================================
# Web Search Tools
# ============================================================

@mcp_server.tool(
    name="web_search",
    title="Web Search",
    description="Search the web using Tavily API.",
)
async def web_search_tool(
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """Search the web.

    Args:
        query: The search query.
        max_results: Maximum number of results (default 5).
    """
    return await tools.run_web_search(query, max_results)


# ============================================================
# Agent Status Tools
# ============================================================

@mcp_server.tool(
    name="get_agent_status",
    title="Get Agent Status",
    description="Get the current agent execution status for a specific channel.",
    meta={"ui/resourceUri": "ui://dashboard/agent-status"},
)
async def get_agent_status_tool(channel_id: str | None = None) -> dict[str, Any]:
    """Get the current agent execution status.

    Args:
        channel_id: The channel ID to get status for. Required for per-channel status.
    """
    return await tools.get_agent_status(channel_id=channel_id)


@mcp_server.tool(
    name="reset_agent_state",
    title="Reset Agent State",
    description="Reset the agent execution state to idle for a specific channel.",
)
async def reset_agent_state_tool(channel_id: str | None = None) -> dict[str, Any]:
    """Reset agent state to idle.

    Args:
        channel_id: The channel ID to reset. Resets all channels if not specified.
    """
    return await tools.reset_agent_state(channel_id=channel_id)


# ============================================================
# Legacy aliases (backward compatibility)
# ============================================================

@mcp_server.tool(
    name="run_rag_query",
    title="Run RAG Query",
    description="[DEPRECATED: Use 'chat' instead] Run a RAG query.",
    meta={"ui/resourceUri": "ui://dashboard/agent-status"},
)
async def run_rag_query_tool(channel_id: str, query: str) -> dict[str, Any]:
    """Run a RAG query (legacy, use 'chat' instead).

    Args:
        channel_id: The channel ID to search in.
        query: The user's question.
    """
    return await tools.run_rag_query(channel_id=channel_id, query=query)


# ============================================================
# Entry Point
# ============================================================

def run_server() -> None:
    """Run the MCP server using stdio transport."""
    import asyncio
    asyncio.run(mcp_server.run_stdio_async())


if __name__ == "__main__":
    run_server()
