# -*- coding: utf-8 -*-
"""
MCP Server test fixtures.

This conftest.py provides fixtures specific to MCP server tests
without importing the main FastAPI app to avoid unnecessary dependencies.
"""
import pytest

from src.mcp_server.state import (
    AgentStateStore,
    reset_global_state_store,
)


@pytest.fixture(autouse=True)
def reset_state_store():
    """Reset global state store before and after each test."""
    reset_global_state_store()
    yield
    reset_global_state_store()


@pytest.fixture
def state_store():
    """Create a fresh AgentStateStore for testing."""
    return AgentStateStore()
