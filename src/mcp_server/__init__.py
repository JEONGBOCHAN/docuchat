# -*- coding: utf-8 -*-
"""
MCP Server module for agent dashboard visualization.

Provides an MCP (Model Context Protocol) Apps server with:
- Real-time agent state visualization via UI resources
- Tools for querying agent status and running RAG queries
- Integration with DashboardMiddleware from CHA-75
"""

from src.mcp_server.state import (
    AgentStateStore,
    get_global_state_store,
    reset_global_state_store,
)

__all__ = [
    "AgentStateStore",
    "get_global_state_store",
    "reset_global_state_store",
]
