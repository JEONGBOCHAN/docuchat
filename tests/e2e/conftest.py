# -*- coding: utf-8 -*-
"""Pytest configuration for E2E tests.

These tests make real API calls to Gemini and test the complete user flow.
Run with: pytest tests/e2e -m e2e -v

Requirements:
- GOOGLE_API_KEY in .env file or environment variable
- Tests will create and delete real resources
- Tests may incur API costs
"""

import os
import pytest
from dotenv import load_dotenv

# Load .env file
load_dotenv()
from datetime import datetime, UTC
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.core.database import Base, get_db
from src.core.rate_limiter import limiter
from src.services.gemini import GeminiService


def pytest_configure(config):
    """Configure pytest for E2E tests."""
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests (require real Gemini API)"
    )


@pytest.fixture(scope="session")
def check_api_key():
    """Check if Gemini API key is available."""
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        pytest.skip("GOOGLE_API_KEY environment variable not set")
    return key


@pytest.fixture(scope="function")
def e2e_db():
    """Create an in-memory SQLite database for E2E tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def e2e_client(e2e_db, check_api_key):
    """Create a test client for E2E tests with real database."""
    # Enable rate limiting for realistic testing
    original_enabled = limiter.enabled
    limiter.enabled = False  # Disable for faster tests

    def override_get_db():
        try:
            yield e2e_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    limiter.enabled = original_enabled


@pytest.fixture(scope="function")
def gemini_service(check_api_key):
    """Create a GeminiService for cleanup operations."""
    return GeminiService()


@pytest.fixture(scope="function")
def cleanup_channels(gemini_service):
    """Fixture to clean up test channels after E2E tests."""
    channels_to_cleanup = []

    yield channels_to_cleanup

    # Cleanup after test
    for channel_id in channels_to_cleanup:
        try:
            gemini_service.delete_store(channel_id)
            print(f"Cleaned up channel: {channel_id}")
        except Exception as e:
            print(f"Failed to cleanup channel {channel_id}: {e}")
