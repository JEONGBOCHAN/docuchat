# -*- coding: utf-8 -*-
import pytest
from datetime import datetime, UTC
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.core.database import Base, get_db
from src.core.rate_limiter import limiter
from src.models.db_models import ChannelMetadata
from src.infrastructure.cache.cache_service import reset_cache_service


# Disable rate limiting for all tests
limiter.enabled = False


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache service before each test to ensure test isolation."""
    reset_cache_service()
    yield
    reset_cache_service()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
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
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_channel(test_db):
    """Create a sample channel for testing."""
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
