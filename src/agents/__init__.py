# -*- coding: utf-8 -*-
"""
Agents module for Docuchat.

Provides LangChain-based agents with middleware support.
"""

from src.agents.rag_agent import (
    create_rag_agent,
    run_rag_agent,
    RAGAgentConfig,
)

__all__ = [
    "create_rag_agent",
    "run_rag_agent",
    "RAGAgentConfig",
]
