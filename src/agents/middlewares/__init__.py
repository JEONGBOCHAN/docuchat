# -*- coding: utf-8 -*-
"""
Middlewares module for Docuchat agents.

Provides middleware components for agent monitoring, logging, and integration
with external dashboards like MCP Apps.
"""

from src.agents.middlewares.dashboard import DashboardMiddleware

__all__ = [
    "DashboardMiddleware",
]
