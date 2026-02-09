# -*- coding: utf-8 -*-
"""Pytest configuration for integration tests."""

import os
import pytest
from datetime import datetime, UTC
from dotenv import load_dotenv
from typing import Any, Generator

# Load .env file for integration tests
load_dotenv()

from src.infrastructure.external.gemini.channel import GeminiChannelAdapter
from src.infrastructure.external.gemini.document import GeminiDocumentAdapter
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
    """Create Gemini adapters for integration tests.

    Returns a SimpleNamespace with channel_adapter and document_adapter
    for backward compatibility with existing tests.
    """
    from types import SimpleNamespace

    channel_adapter = GeminiChannelAdapter()
    document_adapter = GeminiDocumentAdapter()

    # Create a compatibility wrapper that maps old method names to new adapter methods
    service = SimpleNamespace(
        # Channel operations (mapped to GeminiChannelAdapter)
        create_store=lambda display_name: {
            "name": channel_adapter.create_channel(display_name).name,
            "display_name": display_name,
        },
        get_store=lambda store_name: (
            {"name": ch.name, "display_name": ch.display_name}
            if (ch := channel_adapter.get_channel(store_name)) else None
        ),
        list_stores=lambda: [
            {"name": ch.name, "display_name": ch.display_name}
            for ch in channel_adapter.list_channels()
        ],
        delete_store=lambda store_name, force=True: channel_adapter.delete_channel(store_name, force),
        # Document operations (mapped to GeminiDocumentAdapter)
        upload_file=lambda store_name, file_path, display_name=None: (
            lambda result: {"name": result.operation_name, "done": result.done}
        )(document_adapter.upload_document(store_name, file_path, display_name)),
        list_store_files=lambda store_name: [
            {"name": doc.name, "display_name": doc.display_name, "size_bytes": doc.size_bytes, "state": doc.state}
            for doc in document_adapter.list_documents(store_name)
        ],
    )
    return service


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
