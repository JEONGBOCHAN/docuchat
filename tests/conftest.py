# -*- coding: utf-8 -*-
"""
Root test fixtures.

Note: Heavy imports like app are lazy-loaded inside fixtures
to allow lightweight tests (like MCP server tests) to run
without loading the full application.
"""
import pytest
from datetime import datetime, UTC


def _get_app():
    """Lazy load the FastAPI app to avoid import errors in lightweight tests."""
    from src.main import app
    return app


def _get_base_and_db():
    """Lazy load database components."""
    from src.core.database import Base, get_db
    return Base, get_db


def _get_limiter():
    """Lazy load rate limiter."""
    from src.core.rate_limiter import limiter
    return limiter


def _get_channel_metadata():
    """Lazy load ChannelMetadata model."""
    from src.infrastructure.persistence.db_models import ChannelMetadata
    return ChannelMetadata


def _get_reset_cache_service():
    """Lazy load cache service reset function."""
    from src.infrastructure.cache.cache_service import reset_cache_service
    return reset_cache_service


def _register_orm_models_for_tests() -> None:
    """Ensure all ORM models are registered in Base.metadata before create_all.

    Without this, standalone test file execution (e.g. pytest tests/api/v1/test_chat.py)
    may fail with 'no such table' errors because model modules haven't been imported yet.
    """
    import importlib
    importlib.import_module("src.modules.workspace.infrastructure.persistence.models")
    importlib.import_module("src.infrastructure.persistence.db_models")


@pytest.fixture(autouse=True)
def reset_cache(request):
    """Reset cache service before each test to ensure test isolation.

    This fixture uses lazy loading to avoid breaking lightweight tests
    (like MCP server tests) that don't need the full application loaded.
    """
    # Skip entirely for MCP server tests - they have their own isolation
    # Use nodeid which is more reliable across pytest versions
    try:
        nodeid = request.node.nodeid
        if "mcp_server" in nodeid or "test_mcp" in nodeid:
            yield
            return
    except Exception:
        # If we can't determine the test path, skip cache reset to be safe
        yield
        return

    reset_fn = None

    # Try to get the reset function at setup time
    try:
        reset_fn = _get_reset_cache_service()
    except Exception:
        # If cache service is not available for any reason, skip reset
        yield
        return

    # Reset before test (if available)
    if reset_fn is not None:
        try:
            reset_fn()
        except Exception:
            pass

    yield

    # Reset after test (if available)
    if reset_fn is not None:
        try:
            reset_fn()
        except Exception:
            pass


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    app = _get_app()

    # Disable rate limiting for tests, restore original state afterwards
    limiter = _get_limiter()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    try:
        with TestClient(app) as client:
            yield client
    finally:
        limiter.enabled = prev_enabled


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    Base, _ = _get_base_and_db()
    _register_orm_models_for_tests()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client_with_db(test_db):
    """Create a test client with database override."""
    from fastapi.testclient import TestClient

    app = _get_app()
    _, get_db = _get_base_and_db()

    # Disable rate limiting for tests, restore original state afterwards
    limiter = _get_limiter()
    prev_enabled = limiter.enabled
    limiter.enabled = False

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        limiter.enabled = prev_enabled


@pytest.fixture
def sample_channel(test_db):
    """Create a sample channel for testing."""
    ChannelMetadata = _get_channel_metadata()

    channel = ChannelMetadata(
        gemini_store_id="test-store-id-12345",
        name="Test Channel",
        file_count=5,
        total_size_bytes=1024 * 1024,  # 1 MB
        created_at=datetime.now(UTC),
        last_accessed_at=datetime.now(UTC),
    )
    test_db.add(channel)
    test_db.commit()
    test_db.refresh(channel)
    return channel
