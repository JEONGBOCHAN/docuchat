# -*- coding: utf-8 -*-
"""
Agents module for Docuchat.

Provides LangChain-based agents with middleware support.
"""

from src.agents.middlewares import DashboardMiddleware

__all__ = [
    "DashboardMiddleware",
]
