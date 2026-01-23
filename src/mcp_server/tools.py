# -*- coding: utf-8 -*-
"""
MCP Tools for agent dashboard.

Provides MCP tool definitions that can be registered with the MCP server.
These tools allow Claude to interact with the agent state and run RAG queries.
"""

from typing import Any

from src.mcp_server.state import AgentStateStore, AgentStatus, get_global_state_store


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


async def run_rag_query(
    channel_id: str,
    query: str,
    state_store: AgentStateStore | None = None,
) -> dict[str, Any]:
    """Run a RAG query with state publishing for dashboard visualization.

    This tool runs the RAG agent and publishes execution state updates
    that can be visualized in the MCP Apps dashboard.

    Args:
        channel_id: The channel (FileSearchStore) ID to search in.
        query: The user's question to answer.
        state_store: Optional state store to use. Uses global store if not provided.

    Returns:
        Dictionary with response, sources, and execution metadata.
    """
    store = state_store or get_global_state_store()

    # Reset state for new query
    store.reset()

    # Import here to avoid circular imports
    from src.agents.middlewares.dashboard import DashboardMiddleware
    from src.agents.rag_agent import run_rag_agent

    # Create middleware that publishes to our state store
    middleware = DashboardMiddleware(state_updater=store.update)

    try:
        # Run the RAG agent with our middleware
        result = run_rag_agent(
            channel_id=channel_id,
            query=query,
            middleware=[middleware],
        )

        return {
            "response": result.get("response", "No response generated"),
            "sources": result.get("sources", []),
            "iterations": result.get("iterations", 0),
            "error": result.get("error"),
            "state": store.get_state(),
        }

    except Exception as e:
        # Ensure error state is recorded
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


async def reset_agent_state(state_store: AgentStateStore | None = None) -> dict[str, Any]:
    """Reset the agent state to idle.

    Useful when starting a new conversation or after an error.

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
