# -*- coding: utf-8 -*-
"""
RAG Agent workflow - backward compatible wrapper.

This module provides backward compatibility with the original LangGraph
implementation while delegating to the new LangChain create_agent-based
implementation in src/agents/rag_agent.py.

The LangChain-based implementation supports middleware, enabling:
- Request/response logging
- Token usage tracking
- Custom processing hooks
- MCP Apps integration
"""

from typing import TypedDict, Any

# Import from new implementation
from src.agents.rag_agent import (
    create_rag_agent as _create_langchain_agent,
    run_rag_agent as _run_langchain_agent,
    RAGAgentConfig,
    RAG_AGENT_SYSTEM_PROMPT,
)


# ============================================================
# State Definition (kept for backward compatibility)
# ============================================================

class AgentState(TypedDict):
    """State for the RAG agent workflow.

    This TypedDict is kept for backward compatibility with existing code.
    The new LangChain-based implementation uses its own state management.

    Attributes:
        channel_id: The channel (FileSearchStore) ID to search in
        query: User's question
        conversation_history: Previous messages for context
        iteration: Current iteration count
        max_iterations: Maximum allowed iterations
        tool_results: Accumulated results from tool executions
        sources: Sources found during search
        final_answer: The final answer to return
        error: Error message if any step fails
    """
    channel_id: str
    query: str
    conversation_history: list[dict]
    iteration: int
    max_iterations: int
    tool_results: list[dict]
    sources: list[dict]
    final_answer: str | None
    error: str | None


# ============================================================
# Backward Compatible Functions
# ============================================================

def create_rag_agent(config: RAGAgentConfig | None = None, channel_id: str | None = None) -> Any:
    """Create the RAG agent.

    This function provides backward compatibility by accepting either:
    - A RAGAgentConfig object (new style)
    - A channel_id string (old style, creates default config)

    Args:
        config: RAGAgentConfig with agent settings (new style)
        channel_id: Channel ID for backward compatibility (old style)

    Returns:
        Compiled agent graph
    """
    if config is None and channel_id is None:
        raise ValueError("Either config or channel_id must be provided")

    if config is None:
        config = RAGAgentConfig(channel_id=channel_id)

    return _create_langchain_agent(config)


def run_rag_agent(
    channel_id: str,
    query: str,
    conversation_history: list[dict] | None = None,
    max_iterations: int = 3,
    middleware: list[Any] | None = None,
) -> dict[str, Any]:
    """Run the RAG agent to answer a query.

    This function provides full backward compatibility with the original
    signature while also supporting the new middleware parameter.

    Args:
        channel_id: The channel ID to search in
        query: User's question
        conversation_history: Previous messages for context
        max_iterations: Maximum iterations (default 3)
        middleware: Optional list of middleware instances (new feature)

    Returns:
        Dict with 'response', 'sources', 'iterations', and optional 'error'
    """
    return _run_langchain_agent(
        channel_id=channel_id,
        query=query,
        conversation_history=conversation_history,
        max_iterations=max_iterations,
        middleware=middleware,
    )


# Re-export for backward compatibility
__all__ = [
    "AgentState",
    "RAG_AGENT_SYSTEM_PROMPT",
    "create_rag_agent",
    "run_rag_agent",
    "RAGAgentConfig",
]
