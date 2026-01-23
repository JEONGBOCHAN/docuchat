# -*- coding: utf-8 -*-
"""
Workflows module for Docuchat.

Provides LangChain-based agentic workflows with middleware support.
"""

from src.workflows.rag import (
    create_rag_agent,
    run_rag_agent,
    AgentState,
    RAG_AGENT_SYSTEM_PROMPT,
    RAGAgentConfig,
)

__all__ = [
    "create_rag_agent",
    "run_rag_agent",
    "AgentState",
    "RAG_AGENT_SYSTEM_PROMPT",
    "RAGAgentConfig",
]
