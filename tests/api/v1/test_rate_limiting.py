# -*- coding: utf-8 -*-
"""Rate limiting tests."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.main import app
from src.core.rate_limiter import RateLimits
from src.modules.conversation.presentation.api.chat import get_chat_use_case_factory
from src.shared.kernel.contracts.ports.channel import ChannelDTO


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_channel_port():
    """Mock ChatUseCase via get_chat_use_case for chat endpoint."""
    from src.modules.conversation.application.use_cases.chat import ChatUseCase

    mock_port = MagicMock()
    mock_port.get_channel.return_value = ChannelDTO(
        name="test-store",
        display_name="Test",
    )

    mock_cache = MagicMock()
    mock_cache.get_chat_response.return_value = None
    mock_summaries = MagicMock()
    mock_summaries.build_context_string.return_value = ""

    mock_pq = MagicMock()
    mock_pq.execute.return_value = MagicMock(
        response="Test response",
        sources=[],
        iterations=1,
        session_id="test-session",
        error=None,
    )

    mock_session_repo = MagicMock()
    mock_session_dto = MagicMock()
    mock_session_dto.session_id = "test-session"
    mock_session_repo.get_or_create.return_value = (mock_session_dto, True)

    use_case = ChatUseCase(
        channel_port=mock_port,
        channel_repo=MagicMock(),
        chat_history_repo=MagicMock(),
        session_repo=mock_session_repo,
        search_history_repo=MagicMock(),
        cache=mock_cache,
        summaries_use_case=mock_summaries,
        process_query_factory=lambda: mock_pq,
    )
    app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case
    yield mock_port
    app.dependency_overrides.pop(get_chat_use_case_factory, None)


@pytest.fixture
def mock_db(test_db):
    """Mock database session."""
    yield test_db


class TestRateLimitingConfig:
    """Test rate limiting configuration."""

    def test_chat_rate_limit_value(self):
        """Verify chat rate limit is configured correctly."""
        assert RateLimits.CHAT == "10/minute"

    def test_file_upload_rate_limit_value(self):
        """Verify file upload rate limit is configured correctly."""
        assert RateLimits.FILE_UPLOAD == "20/hour"

    def test_default_rate_limit_value(self):
        """Verify default rate limit is configured correctly."""
        assert RateLimits.DEFAULT == "100/minute"


class TestRateLimiting429Response:
    """Test 429 Too Many Requests response — deterministic verification."""

    def test_rate_limit_exceeded_returns_429(self, client):
        """Exceed a strict 1/minute limit and assert 429 with Retry-After."""
        from fastapi import APIRouter, Request
        from fastapi.responses import JSONResponse
        from src.core.rate_limiter import limiter

        # Force limiter ON regardless of conftest fixture state
        prev_enabled = limiter.enabled
        limiter.enabled = True

        # Create a temporary test route with a very low limit
        test_router = APIRouter()

        @test_router.get("/_test_rate_limit")
        @limiter.limit("1/minute")
        def _rate_limit_test_endpoint(request: Request):
            return JSONResponse({"ok": True})

        app.include_router(test_router)

        try:
            # Use a fresh client so route registration takes effect
            test_client = TestClient(app)

            # First request should succeed
            r1 = test_client.get("/_test_rate_limit")
            assert r1.status_code == 200

            # Second request must be rate-limited
            r2 = test_client.get("/_test_rate_limit")
            assert r2.status_code == 429, f"Expected 429 but got {r2.status_code}"
            assert "Retry-After" in r2.headers
        finally:
            # Remove the test route and restore limiter state
            app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != "/_test_rate_limit"]
            limiter.enabled = prev_enabled


class TestRateLimitHeaders:
    """Test rate limit response headers."""

    @pytest.mark.asyncio
    async def test_429_response_has_retry_after_header(self, client):
        """Test that 429 response includes Retry-After header."""
        # The rate limit exception handler should add Retry-After header
        # This tests the handler is properly configured
        from slowapi.errors import RateLimitExceeded
        from src.main import rate_limit_exceeded_handler
        from fastapi import Request

        # Create a mock request
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()

        # Create mock exception
        mock_exc = MagicMock(spec=RateLimitExceeded)
        mock_exc.detail = "10 per 1 minute"
        mock_exc.retry_after = 60

        # Call the handler
        response = await rate_limit_exceeded_handler(mock_request, mock_exc)

        # Verify response
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "60"


class TestEndpointRateLimits:
    """Test that endpoints have rate limits applied."""

    def test_chat_endpoint_has_rate_limit_decorator(self):
        """Verify chat endpoint has rate limit decorator."""
        from src.modules.conversation.presentation.api.chat import send_message
        # Check that the function has been wrapped by limiter
        assert hasattr(send_message, "__wrapped__") or hasattr(send_message, "__self__")

    def test_chat_stream_endpoint_has_rate_limit_decorator(self):
        """Verify chat stream endpoint has rate limit decorator."""
        from src.modules.conversation.presentation.api.chat import send_message_stream
        assert hasattr(send_message_stream, "__wrapped__") or hasattr(send_message_stream, "__self__")

    def test_document_upload_endpoint_has_rate_limit_decorator(self):
        """Verify document upload endpoint has rate limit decorator."""
        from src.modules.workspace.presentation.api.documents import upload_document
        assert hasattr(upload_document, "__wrapped__") or hasattr(upload_document, "__self__")

    def test_document_url_upload_endpoint_has_rate_limit_decorator(self):
        """Verify document URL upload endpoint has rate limit decorator."""
        from src.modules.workspace.presentation.api.documents import upload_from_url
        assert hasattr(upload_from_url, "__wrapped__") or hasattr(upload_from_url, "__self__")


class TestRateLimiterSetup:
    """Test rate limiter setup in main app."""

    def test_app_has_limiter_state(self):
        """Verify app has limiter in state."""
        assert hasattr(app.state, "limiter")

    def test_rate_limit_exception_handler_registered(self):
        """Verify RateLimitExceeded exception handler is registered."""
        from slowapi.errors import RateLimitExceeded
        # Check that the exception handler is registered
        handlers = app.exception_handlers
        assert RateLimitExceeded in handlers
