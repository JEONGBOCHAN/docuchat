# -*- coding: utf-8 -*-
"""Pytest configuration for integration tests."""

import os
import pytest
from datetime import datetime, UTC

from src.services.gemini import GeminiService
from src.core.config import get_settings


def pytest_configure(config):
    """Configure pytest for integration tests."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require real Gemini API key)"
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
