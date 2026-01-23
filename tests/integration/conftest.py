# -*- coding: utf-8 -*-
"""Pytest configuration for integration tests."""

import os
import pytest
from datetime import datetime, UTC
from dotenv import load_dotenv
from typing import Any, Generator

# Load .env file for integration tests
load_dotenv()

from src.services.gemini import GeminiService
from src.core.config import get_settings


def pytest_configure(config):
    """Configure pytest for integration tests."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require real Gemini API key)"
    )
    config.addinivalue_line(
        "markers", "mcp: marks tests as MCP integration tests"
    )


@pytest.fixture(scope="session")
def gemini_api_key():
    """Get the Gemini API key from environment.

    Skips tests if the key is not available.
    """
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        pytest.skip("GOOGLE_API_KEY environment variable not set")
    return key


@pytest.fixture(scope="session")
def gemini_service(gemini_api_key):
    """Create a GeminiService instance for integration tests.

    Uses the real API key from the environment.
    """
    return GeminiService()


@pytest.fixture
def test_channel_name():
    """Generate a unique test channel name."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"integration-test-{timestamp}"


@pytest.fixture
def cleanup_channels(gemini_service):
    """Fixture to clean up test channels after tests.

    Yields a list that tests can append channel IDs to.
    After the test, all channels in the list will be deleted.
    """
    channels_to_cleanup = []

    yield channels_to_cleanup

    # Cleanup after test
    for channel_id in channels_to_cleanup:
        try:
            gemini_service.delete_store(channel_id)
        except Exception as e:
            print(f"Failed to cleanup channel {channel_id}: {e}")


# ============================================================
# MCP Server Integration Test Fixtures
# ============================================================

@pytest.fixture
def mcp_state_store() -> Generator[Any, None, None]:
    """Create and reset a fresh AgentStateStore for MCP tests.

    Yields:
        AgentStateStore instance for testing.
    """
    from src.mcp_server.state import AgentStateStore, reset_global_state_store

    # Reset global state before test
    reset_global_state_store()

    # Create a fresh store for this test
    store = AgentStateStore()
    yield store

    # Cleanup after test
    reset_global_state_store()


@pytest.fixture
def mcp_state_events() -> Generator[list[dict[str, Any]], None, None]:
    """Fixture to capture MCP state events.

    Yields:
        List that captures all state update events.
    """
    events: list[dict[str, Any]] = []
    yield events


@pytest.fixture
def mcp_state_store_with_capture(
    mcp_state_store,
    mcp_state_events,
) -> Generator[Any, None, None]:
    """Create an AgentStateStore that captures events.

    Args:
        mcp_state_store: The base state store.
        mcp_state_events: List to capture events.

    Yields:
        AgentStateStore with event capture subscribed.
    """
    def capture_event(state: dict[str, Any]) -> None:
        mcp_state_events.append(state.copy())

    mcp_state_store.subscribe(capture_event)
    yield mcp_state_store
    mcp_state_store.unsubscribe(capture_event)


@pytest.fixture
def mock_dashboard_middleware(mcp_state_store):
    """Create a DashboardMiddleware with the test state store.

    Args:
        mcp_state_store: The state store to use.

    Returns:
        DashboardMiddleware instance.
    """
    from src.agents.middlewares.dashboard import DashboardMiddleware

    middleware = DashboardMiddleware(
        state_updater=mcp_state_store.update,
        name="test_dashboard_middleware",
    )
    return middleware


@pytest.fixture
def mcp_test_channel_id():
    """Return a test channel ID for MCP tests.

    This can be overridden in tests that need real channel IDs.
    """
    return "test-channel-mcp-12345"
