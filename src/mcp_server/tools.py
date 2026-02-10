# -*- coding: utf-8 -*-
"""
MCP Tools Implementation.

Clean Architecture based implementation of MCP tools.
All tools use ProcessQueryUseCase and other application layer components.

Session-level conversation history has been removed; MCP queries are
stateless.  Conversation context (if needed) should be managed through
the conversation module's public API.
"""

import time
from datetime import datetime, UTC
from typing import Any
import uuid

from src.mcp_server.state import AgentStateStore, get_global_state_store


# ============================================================
# Session Storage (In-Memory with TTL and capacity limits)
# ============================================================

_sessions: dict[str, dict[str, Any]] = {}

_CLEANUP_INTERVAL_SECONDS = 60  # Throttle cleanup to at most once per minute
_last_cleanup_time: float = 0.0


def _get_mcp_settings() -> tuple[int, int]:
    """Return (ttl_seconds, max_sessions) from centralised Settings."""
    from src.core.config import get_settings
    s = get_settings()
    return s.mcp_session_ttl_seconds, s.mcp_max_sessions


def _cleanup_stale_sessions(force: bool = False) -> None:
    """Remove sessions that have exceeded the TTL.

    Args:
        force: If True, skip the throttle check and run immediately.
    """
    global _last_cleanup_time
    now = time.monotonic()
    if not force and (now - _last_cleanup_time) < _CLEANUP_INTERVAL_SECONDS:
        return
    _last_cleanup_time = now
    ttl, _ = _get_mcp_settings()
    expired = [
        sid for sid, data in _sessions.items()
        if now - data.get("_last_seen", 0) > ttl
    ]
    for sid in expired:
        _sessions.pop(sid, None)


def _generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


# ============================================================
# Agent Status Tools
# ============================================================

async def get_agent_status(
    channel_id: str | None = None,
    state_store: AgentStateStore | None = None,
) -> dict[str, Any]:
    """Get the current agent execution status for a specific channel.

    Returns the complete state including:
    - Overall status (idle/running/complete/error)
    - Current node being executed
    - Execution history (steps)
    - Metrics (duration, call counts)
    - Pipeline node statuses

    Args:
        channel_id: The channel ID to get status for. Returns idle if not specified.
        state_store: Optional state store to use. Uses global store if not provided.

    Returns:
        Dictionary containing the current agent state for the channel.
    """
    store = state_store or get_global_state_store()
    return store.get_state(channel_id)


async def reset_agent_state(
    channel_id: str | None = None,
    state_store: AgentStateStore | None = None,
) -> dict[str, Any]:
    """Reset the agent state to idle for a specific channel.

    Args:
        channel_id: The channel ID to reset. Resets all channels if not specified.
        state_store: Optional state store to use. Uses global store if not provided.

    Returns:
        Dictionary confirming the reset with the new state.
    """
    store = state_store or get_global_state_store()
    store.reset(channel_id)
    return {
        "message": f"Agent state reset to idle{f' for channel {channel_id}' if channel_id else ''}",
        "state": store.get_state(channel_id),
    }


# ============================================================
# Channel Tools
# ============================================================

async def validate_channel(channel_id: str) -> dict[str, Any]:
    """Validate if a channel exists.

    Args:
        channel_id: The channel ID to validate.

    Returns:
        Dictionary with validation result.
    """
    from src.infrastructure.di import create_channel_port

    try:
        channel_port = create_channel_port()
        channel = channel_port.get_channel(channel_id)

        if channel:
            return {
                "valid": True,
                "channel_id": channel_id,
                "display_name": channel.display_name,
            }
        else:
            return {
                "valid": False,
                "channel_id": channel_id,
                "error": "Channel not found",
            }
    except Exception as e:
        return {
            "valid": False,
            "channel_id": channel_id,
            "error": str(e),
        }


async def list_channels() -> dict[str, Any]:
    """List all available channels.

    Returns:
        Dictionary with list of channels.
    """
    from src.infrastructure.di import create_channel_port

    try:
        channel_port = create_channel_port()
        channel_list = channel_port.list_channels()

        channels = []
        for channel in channel_list:
            channels.append({
                "channel_id": channel.name.split("/")[-1] if channel.name else "",
                "display_name": channel.display_name,
            })

        return {
            "channels": channels,
            "total": len(channels),
        }
    except Exception as e:
        return {
            "channels": [],
            "total": 0,
            "error": str(e),
        }


# ============================================================
# Session Tools
# ============================================================

async def create_session(channel_id: str) -> dict[str, Any]:
    """Create a new chat session.

    Args:
        channel_id: The channel ID for this session.

    Returns:
        Dictionary with session information.
    """
    # Validate channel first
    validation = await validate_channel(channel_id)
    if not validation.get("valid"):
        return {
            "success": False,
            "error": f"Invalid channel: {channel_id}",
        }

    # Cleanup expired sessions and enforce capacity limit
    _cleanup_stale_sessions(force=True)
    _, max_sessions = _get_mcp_settings()
    if len(_sessions) >= max_sessions:
        return {
            "success": False,
            "error": "Maximum number of MCP tool sessions reached. Try again later.",
        }

    session_id = _generate_session_id()
    _sessions[session_id] = {
        "session_id": session_id,
        "channel_id": channel_id,
        "created_at": datetime.now(UTC).isoformat(),
        "_last_seen": time.monotonic(),
    }

    return {
        "success": True,
        "session_id": session_id,
        "channel_id": channel_id,
    }


async def get_session(session_id: str) -> dict[str, Any]:
    """Get session information.

    Args:
        session_id: The session ID to retrieve.

    Returns:
        Dictionary with session information.
    """
    _cleanup_stale_sessions()
    if session_id not in _sessions:
        return {
            "success": False,
            "error": f"Session not found: {session_id}",
        }

    session = _sessions[session_id]
    session["_last_seen"] = time.monotonic()
    return {
        "success": True,
        **session,
    }


async def delete_session(session_id: str) -> dict[str, Any]:
    """Delete a chat session.

    Args:
        session_id: The session ID to delete.

    Returns:
        Dictionary confirming deletion.
    """
    if session_id not in _sessions:
        return {
            "success": False,
            "error": f"Session not found: {session_id}",
        }

    del _sessions[session_id]

    return {
        "success": True,
        "message": f"Session {session_id} deleted",
    }


async def list_sessions() -> dict[str, Any]:
    """List all active sessions.

    Returns:
        Dictionary with list of sessions.
    """
    _cleanup_stale_sessions()
    sessions = []
    for session_id, session in _sessions.items():
        sessions.append({**session})

    return {
        "sessions": sessions,
        "total": len(sessions),
    }


# ============================================================
# RAG Query Tool
# ============================================================

async def run_rag_query(
    channel_id: str,
    query: str,
    session_id: str | None = None,
    state_store: AgentStateStore | None = None,
) -> dict[str, Any]:
    """Run a RAG query with state publishing for dashboard visualization.

    Uses Clean Architecture ProcessQueryUseCase.

    Args:
        channel_id: The channel (FileSearchStore) ID to search in.
        query: The user's question to answer.
        session_id: Optional session ID (used for _last_seen tracking only).
        state_store: Optional state store to use.

    Returns:
        Dictionary with response, sources, and execution metadata.
    """
    store = state_store or get_global_state_store()
    store.reset(channel_id)

    # Touch session _last_seen if session exists
    if session_id and session_id in _sessions:
        _sessions[session_id]["_last_seen"] = time.monotonic()

    try:
        # Use Clean Architecture: ProcessQueryUseCase
        from src.modules.conversation.public import create_process_query_use_case

        use_case = create_process_query_use_case(
            use_legacy_dashboard=True,
            include_web_search=True,
            include_academic_search=True,
        )

        result = use_case.execute(
            query=query,
            channel_id=channel_id,
        )

        return {
            "response": result.response,
            "sources": result.sources,
            "iterations": result.iterations,
            "error": result.error,
            "state": store.get_state(channel_id),
        }

    except Exception as e:
        store.update({
            "event": "agent_error",
            "channel_id": channel_id,
            "error": str(e),
        })
        return {
            "response": f"Error: {str(e)}",
            "sources": [],
            "iterations": 0,
            "error": str(e),
            "state": store.get_state(channel_id),
        }


# ============================================================
# Web Search Tool (Tavily)
# ============================================================

async def run_web_search(
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """Run a web search using Tavily.

    Args:
        query: The search query.
        max_results: Maximum number of results.

    Returns:
        Dictionary with search results.
    """
    try:
        from src.infrastructure.external.mcp import McpWebSearchAdapter

        adapter = McpWebSearchAdapter()
        results = adapter.search(query, max_results=max_results)

        return {
            "success": True,
            "query": query,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "score": r.score,
                }
                for r in results
            ],
            "total": len(results),
        }
    except Exception as e:
        return {
            "success": False,
            "query": query,
            "results": [],
            "error": str(e),
        }


async def run_rag_with_web_search(
    channel_id: str,
    query: str,
    session_id: str | None = None,
    state_store: AgentStateStore | None = None,
) -> dict[str, Any]:
    """Run a RAG query with web search enabled.

    Uses Clean Architecture ProcessQueryUseCase with Tavily web search.

    Args:
        channel_id: The channel ID to search in.
        query: The user's question.
        session_id: Optional session ID (used for _last_seen tracking only).
        state_store: Optional state store to use.

    Returns:
        Dictionary with response, sources, and execution metadata.
    """
    store = state_store or get_global_state_store()
    store.reset(channel_id)

    # Touch session _last_seen if session exists
    if session_id and session_id in _sessions:
        _sessions[session_id]["_last_seen"] = time.monotonic()

    try:
        from src.modules.conversation.public import create_process_query_use_case

        use_case = create_process_query_use_case(
            use_legacy_dashboard=True,
            include_web_search=True,
            include_academic_search=True,
        )

        result = use_case.execute(
            query=query,
            channel_id=channel_id,
        )

        return {
            "response": result.response,
            "sources": result.sources,
            "iterations": result.iterations,
            "tools_used": result.tools_used,
            "error": result.error,
            "state": store.get_state(channel_id),
        }

    except Exception as e:
        store.update({
            "event": "agent_error",
            "channel_id": channel_id,
            "error": str(e),
        })
        return {
            "response": f"Error: {str(e)}",
            "sources": [],
            "iterations": 0,
            "error": str(e),
            "state": store.get_state(channel_id),
        }
