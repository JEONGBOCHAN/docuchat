# -*- coding: utf-8 -*-
"""
MCP Tools Implementation.

Clean Architecture based implementation of MCP tools.
All tools use ProcessQueryUseCase and other application layer components.
"""

from typing import Any
import uuid

from src.mcp_server.state import AgentStateStore, get_global_state_store


# ============================================================
# Session Storage (In-Memory for now)
# ============================================================

_sessions: dict[str, dict[str, Any]] = {}
_chat_histories: dict[str, list[dict[str, Any]]] = {}


def _generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


# ============================================================
# Agent Status Tools
# ============================================================

async def get_agent_status(state_store: AgentStateStore | None = None) -> dict[str, Any]:
    """Get the current agent execution status.

    Returns the complete state including:
    - Overall status (idle/running/complete/error)
    - Current node being executed
    - Execution history (steps)
    - Metrics (duration, call counts)
    - Pipeline node statuses

    Args:
        state_store: Optional state store to use. Uses global store if not provided.

    Returns:
        Dictionary containing the current agent state.
    """
    store = state_store or get_global_state_store()
    return store.get_state()


async def reset_agent_state(state_store: AgentStateStore | None = None) -> dict[str, Any]:
    """Reset the agent state to idle.

    Args:
        state_store: Optional state store to use. Uses global store if not provided.

    Returns:
        Dictionary confirming the reset with the new state.
    """
    store = state_store or get_global_state_store()
    store.reset()
    return {
        "message": "Agent state reset to idle",
        "state": store.get_state(),
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

    session_id = _generate_session_id()
    _sessions[session_id] = {
        "session_id": session_id,
        "channel_id": channel_id,
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    _chat_histories[session_id] = []

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
    if session_id not in _sessions:
        return {
            "success": False,
            "error": f"Session not found: {session_id}",
        }

    session = _sessions[session_id]
    return {
        "success": True,
        **session,
        "message_count": len(_chat_histories.get(session_id, [])),
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
    if session_id in _chat_histories:
        del _chat_histories[session_id]

    return {
        "success": True,
        "message": f"Session {session_id} deleted",
    }


async def list_sessions() -> dict[str, Any]:
    """List all active sessions.

    Returns:
        Dictionary with list of sessions.
    """
    sessions = []
    for session_id, session in _sessions.items():
        sessions.append({
            **session,
            "message_count": len(_chat_histories.get(session_id, [])),
        })

    return {
        "sessions": sessions,
        "total": len(sessions),
    }


# ============================================================
# Chat History Tools
# ============================================================

async def get_chat_history(session_id: str, limit: int = 100) -> dict[str, Any]:
    """Get chat history for a session.

    Args:
        session_id: The session ID.
        limit: Maximum number of messages to return.

    Returns:
        Dictionary with chat history.
    """
    if session_id not in _sessions:
        return {
            "success": False,
            "error": f"Session not found: {session_id}",
        }

    history = _chat_histories.get(session_id, [])[-limit:]
    return {
        "success": True,
        "session_id": session_id,
        "messages": history,
        "total": len(history),
    }


async def clear_chat_history(session_id: str) -> dict[str, Any]:
    """Clear chat history for a session.

    Args:
        session_id: The session ID.

    Returns:
        Dictionary confirming deletion.
    """
    if session_id not in _sessions:
        return {
            "success": False,
            "error": f"Session not found: {session_id}",
        }

    _chat_histories[session_id] = []
    return {
        "success": True,
        "message": f"Chat history cleared for session {session_id}",
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
        session_id: Optional session ID for conversation context.
        state_store: Optional state store to use.

    Returns:
        Dictionary with response, sources, and execution metadata.
    """
    store = state_store or get_global_state_store()
    store.reset()

    # Get conversation history if session exists
    conversation_history = []
    if session_id and session_id in _chat_histories:
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in _chat_histories[session_id]
        ]

    try:
        # Use Clean Architecture: ProcessQueryUseCase
        from src.infrastructure.di import create_process_query_use_case

        use_case = create_process_query_use_case(
            use_legacy_dashboard=True,
            include_web_search=False,
        )

        result = use_case.execute(
            query=query,
            channel_id=channel_id,
            conversation_history=conversation_history,
        )

        response_data = {
            "response": result.response,
            "sources": result.sources,
            "iterations": result.iterations,
            "error": result.error,
            "state": store.get_state(),
        }

        # Save to chat history if session exists
        if session_id and session_id in _chat_histories:
            _chat_histories[session_id].append({
                "role": "user",
                "content": query,
            })
            _chat_histories[session_id].append({
                "role": "assistant",
                "content": result.response,
                "sources": result.sources,
            })

        return response_data

    except Exception as e:
        store.update({
            "event": "agent_error",
            "error": str(e),
        })
        return {
            "response": f"Error: {str(e)}",
            "sources": [],
            "iterations": 0,
            "error": str(e),
            "state": store.get_state(),
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
        from src.infrastructure.external.tavily import TavilyWebSearchAdapter

        adapter = TavilyWebSearchAdapter()
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
        session_id: Optional session ID for conversation context.
        state_store: Optional state store to use.

    Returns:
        Dictionary with response, sources, and execution metadata.
    """
    store = state_store or get_global_state_store()
    store.reset()

    conversation_history = []
    if session_id and session_id in _chat_histories:
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in _chat_histories[session_id]
        ]

    try:
        from src.infrastructure.di import create_process_query_use_case

        use_case = create_process_query_use_case(
            use_legacy_dashboard=True,
            include_web_search=True,  # Enable Tavily
        )

        result = use_case.execute(
            query=query,
            channel_id=channel_id,
            conversation_history=conversation_history,
        )

        response_data = {
            "response": result.response,
            "sources": result.sources,
            "iterations": result.iterations,
            "tools_used": result.tools_used,
            "error": result.error,
            "state": store.get_state(),
        }

        if session_id and session_id in _chat_histories:
            _chat_histories[session_id].append({
                "role": "user",
                "content": query,
            })
            _chat_histories[session_id].append({
                "role": "assistant",
                "content": result.response,
                "sources": result.sources,
            })

        return response_data

    except Exception as e:
        store.update({
            "event": "agent_error",
            "error": str(e),
        })
        return {
            "response": f"Error: {str(e)}",
            "sources": [],
            "iterations": 0,
            "error": str(e),
            "state": store.get_state(),
        }
