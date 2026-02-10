# -*- coding: utf-8 -*-
"""Tests for Chat API."""

import json
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.modules.conversation.presentation.api.chat import get_chat_use_case_factory
from src.shared.kernel.contracts.ports.channel import ChannelDTO
from src.modules.conversation.application.use_cases.process_query import QueryResult


@pytest.fixture(autouse=True)
def _override_chat_use_case():
    """Prevent real container from resolving (which requires API keys).

    Provides a safe default override so tests that don't explicitly set
    their own override never trigger external service initialization.
    Individual tests may still override via app.dependency_overrides.
    """
    app.dependency_overrides[get_chat_use_case_factory] = lambda: _make_chat_use_case
    yield
    app.dependency_overrides.pop(get_chat_use_case_factory, None)


def _make_chat_use_case(
    channel_port=None,
    process_query_factory=None,
    db=None,
    session_memory_repo=None,
    checkpoint_store=None,
):
    """Create ChatUseCase with mock/real dependencies.

    When db is provided, real DB repositories are used (for integration tests).
    When db is None, all repositories are mocked.
    """
    from src.modules.conversation.application.use_cases.chat import ChatUseCase

    if db is not None:
        from src.modules.workspace.public import (
            create_channel_repository_port,
            create_search_history_repository_port,
        )
        from src.modules.conversation.public import (
            create_chat_history_repository_port,
            create_chat_session_repository_port,
        )
        channel_repo = create_channel_repository_port(db)
        chat_history_repo = create_chat_history_repository_port(db)
        session_repo = create_chat_session_repository_port(db)
        search_history_repo = create_search_history_repository_port(db)
    else:
        channel_repo = MagicMock()
        chat_history_repo = MagicMock()
        session_repo = MagicMock()
        search_history_repo = MagicMock()

    mock_cache = MagicMock()
    mock_cache.get_chat_response.return_value = None

    mock_summaries = MagicMock()
    mock_summaries.build_context_string.return_value = ""

    return ChatUseCase(
        channel_port=channel_port or MagicMock(),
        channel_repo=channel_repo,
        chat_history_repo=chat_history_repo,
        session_repo=session_repo,
        search_history_repo=search_history_repo,
        cache=mock_cache,
        summaries_use_case=mock_summaries,
        process_query_factory=process_query_factory or (lambda: MagicMock()),
        session_memory_repo=session_memory_repo,
        checkpoint_store=checkpoint_store,
    )


class TestSendMessage:
    """Tests for POST /api/v1/chat."""

    def test_send_message_success(self, client_with_db: TestClient, test_db):
        """Test successful chat message."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="This is the answer based on the documents.",
            sources=[{"source": "document.pdf", "content": "Relevant content here"}],
            iterations=1,
            session_id=None,
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "What is the main topic?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is the main topic?"
        assert data["response"] == "This is the answer based on the documents."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "document.pdf"

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_send_message_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test sending message to non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/chat",
            json={"query": "What is this?"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_send_message_empty_query(self, client_with_db: TestClient, test_db):
        """Test sending empty query fails."""
        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_send_message_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="",
            sources=[],
            iterations=1,
            error="API Error occurred",
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "What is this?"},
        )

        assert response.status_code == 500

        app.dependency_overrides.pop(get_chat_use_case_factory, None)


class TestGetChatHistory:
    """Tests for GET /api/v1/chat/history."""

    def test_get_history_empty(self, client_with_db: TestClient, test_db):
        """Test getting empty history."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["messages"] == []
        assert data["total"] == 0

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_get_history_with_messages(self, client_with_db: TestClient, test_db):
        """Test getting history after sending messages."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="Answer here",
            sources=[],
            iterations=1,
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Send a message first
        client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Hello?"},
        )

        # Get history
        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # user + assistant
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello?"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "Answer here"

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_get_history_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test getting history for non-existent channel returns empty (local-first)."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/not-exists/chat/history",
        )

        # Local-first: returns empty history instead of 404
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["messages"] == []

        app.dependency_overrides.pop(get_chat_use_case_factory, None)


class TestClearChatHistory:
    """Tests for DELETE /api/v1/chat/history."""

    def test_clear_history_success(self, client_with_db: TestClient, test_db):
        """Test clearing chat history."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="Answer",
            sources=[],
            iterations=1,
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Send a message first
        client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Hello?"},
        )

        # Clear history
        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )

        assert response.status_code == 204

        # Verify history is cleared
        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )
        assert response.json()["total"] == 0

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_clear_history_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test clearing history for non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/not-exists/chat/history",
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_clear_history_also_clears_session_memory(self, client_with_db: TestClient, test_db):
        """Test that clearing history also clears session memory (rolling summaries)."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_session_memory_repo = MagicMock()
        mock_session_memory_repo.clear_by_channel.return_value = 2

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            db=test_db,
            session_memory_repo=mock_session_memory_repo,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Ensure channel metadata exists
        client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Hello?"},
        )

        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )

        assert response.status_code == 204
        mock_session_memory_repo.clear_by_channel.assert_called_once()

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_clear_history_deletes_checkpoints(self, client_with_db: TestClient, test_db):
        """Test that clearing history also deletes LangGraph checkpoints for all sessions."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_checkpoint_store = MagicMock()

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="Answer",
            sources=[],
            iterations=1,
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
            checkpoint_store=mock_checkpoint_store,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Send messages to create sessions
        client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Hello?"},
        )
        client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Second?"},
        )

        # Clear history — should trigger checkpoint deletion
        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )

        assert response.status_code == 204
        # Checkpoint delete_thread should have been called for each session
        assert mock_checkpoint_store.delete_thread.call_count > 0

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_clear_history_checkpoint_failure_non_blocking(self, client_with_db: TestClient, test_db):
        """Test that checkpoint deletion failure doesn't block history clearing."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_checkpoint_store = MagicMock()
        mock_checkpoint_store.delete_thread.side_effect = RuntimeError("DB locked")

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="Answer",
            sources=[],
            iterations=1,
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
            checkpoint_store=mock_checkpoint_store,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Send a message to create session
        client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Hello?"},
        )

        # Clear history should succeed even when checkpoint deletion fails
        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )

        assert response.status_code == 204

        # Verify history is still cleared
        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )
        assert response.json()["total"] == 0

        app.dependency_overrides.pop(get_chat_use_case_factory, None)


class TestValidationPrecedence:
    """Regression: payload validation must precede use-case factory invocation."""

    def test_empty_query_skips_use_case_factory(self, client_with_db: TestClient, test_db):
        """When query is empty (422), the use-case factory must NOT be called."""
        mock_factory = MagicMock()

        app.dependency_overrides[get_chat_use_case_factory] = lambda: mock_factory

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": ""},
        )

        assert response.status_code == 422
        mock_factory.assert_not_called()

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_stream_empty_query_skips_use_case_factory(
        self, client_with_db: TestClient, test_db
    ):
        """When stream query is empty (422), the use-case factory must NOT be called."""
        mock_factory = MagicMock()

        app.dependency_overrides[get_chat_use_case_factory] = lambda: mock_factory

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": ""},
        )

        assert response.status_code == 422
        mock_factory.assert_not_called()

        app.dependency_overrides.pop(get_chat_use_case_factory, None)


class TestStreamMessage:
    """Tests for POST /api/v1/chat/stream (SSE streaming).

    Uses Clean Architecture with ChatUseCase.prepare_stream().
    SSE format:
    - {"chunk": "text"} for content
    - {"sources": [...]} for sources
    - [DONE] for completion
    - {"error": "message"} for errors
    """

    def test_stream_message_success(self, client_with_db: TestClient, test_db):
        """Test successful streaming chat message."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        # Mock ProcessQueryUseCase.execute_stream
        def mock_execute_stream(*args, **kwargs):
            def generator():
                yield {"event": "agent_started", "session_id": "test-session"}
                yield {"event": "content", "content": "Hello "}
                yield {"event": "content", "content": "World!"}
                yield {"event": "agent_completed", "response": "Hello World!"}
                return QueryResult(
                    response="Hello World!",
                    sources=[{"source": "doc.pdf", "content": "test"}],
                    session_id="test-session",
                    iterations=1,
                )
            return generator()

        mock_pq = MagicMock()
        mock_pq.execute_stream = mock_execute_stream

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": "What is this?"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE events
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    events.append("[DONE]")
                else:
                    events.append(json.loads(data))

        # Should have: chunk, chunk, sources, [DONE]
        assert len(events) >= 3
        # Find chunk events
        chunks = [e for e in events if isinstance(e, dict) and "chunk" in e]
        assert len(chunks) == 2
        assert chunks[0]["chunk"] == "Hello "
        assert chunks[1]["chunk"] == "World!"
        # Should end with [DONE]
        assert "[DONE]" in events

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_stream_message_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test streaming to non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/chat/stream",
            json={"query": "What is this?"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_stream_message_error_event(self, client_with_db: TestClient, test_db):
        """Test streaming with error event."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        # Mock ProcessQueryUseCase.execute_stream to yield error
        def mock_execute_stream(*args, **kwargs):
            def generator():
                yield {"event": "error", "error": "API Error"}
                return QueryResult(
                    response="Error: API Error",
                    sources=[],
                    error="API Error",
                )
            return generator()

        mock_pq = MagicMock()
        mock_pq.execute_stream = mock_execute_stream

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": "What is this?"},
        )

        assert response.status_code == 200  # SSE still returns 200

        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                data = line[6:]
                if data != "[DONE]":
                    events.append(json.loads(data))

        assert len(events) >= 1
        error_event = next((e for e in events if "error" in e), None)
        assert error_event is not None
        assert error_event["error"] == "API Error"

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_stream_saves_to_history(self, client_with_db: TestClient, test_db):
        """Test that streaming saves messages to history."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        # Mock ProcessQueryUseCase.execute_stream
        def mock_execute_stream(*args, **kwargs):
            def generator():
                yield {"event": "content", "content": "Streamed response"}
                yield {"event": "agent_completed", "response": "Streamed response"}
                return QueryResult(
                    response="Streamed response",
                    sources=[],
                    session_id="test-session",
                    iterations=1,
                )
            return generator()

        mock_pq = MagicMock()
        mock_pq.execute_stream = mock_execute_stream

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Stream a message
        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": "Test query"},
        )

        # Consume the response to ensure streaming completes
        _ = response.text

        # Check history
        history_response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/chat/history",
        )

        data = history_response.json()
        assert data["total"] == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Test query"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "Streamed response"

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_stream_empty_query_fails(self, client_with_db: TestClient, test_db):
        """Test streaming with empty query fails validation."""
        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": ""},
        )

        assert response.status_code == 422  # Validation error


class TestChatSession:
    """Tests for chat session management."""

    def test_create_session_success(self, client_with_db: TestClient, test_db):
        """Test creating a new chat session."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions",
            json={"context_window": 10},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["session_id"].startswith("sess_")
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["context_window"] == 10

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_create_session_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test creating session for non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/chat/sessions",
            json={"context_window": 10},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_get_session_success(self, client_with_db: TestClient, test_db):
        """Test getting session information."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Create session first
        create_response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions",
            json={"context_window": 5},
        )
        session_id = create_response.json()["session_id"]

        # Get session
        response = client_with_db.get(
            f"/api/v1/channels/fileSearchStores/test-store/chat/sessions/{session_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["context_window"] == 5

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_get_session_not_found(self, client_with_db: TestClient, test_db):
        """Test getting non-existent session."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions/sess_nonexistent"
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_delete_session_success(self, client_with_db: TestClient, test_db):
        """Test deleting a session."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Create session first
        create_response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions",
            json={"context_window": 10},
        )
        session_id = create_response.json()["session_id"]

        # Delete session
        response = client_with_db.delete(
            f"/api/v1/channels/fileSearchStores/test-store/chat/sessions/{session_id}"
        )

        assert response.status_code == 204

        # Verify session is deleted
        get_response = client_with_db.get(
            f"/api/v1/channels/fileSearchStores/test-store/chat/sessions/{session_id}"
        )
        assert get_response.status_code == 404

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_delete_session_not_found(self, client_with_db: TestClient, test_db):
        """Test deleting non-existent session."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_chat_use_case(channel_port=mock_channel_port, db=test_db)
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions/sess_nonexistent"
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_chat_use_case_factory, None)


class TestMultiTurnConversation:
    """Tests for multi-turn conversation with session context."""

    def test_chat_with_session_maintains_context(self, client_with_db: TestClient, test_db):
        """Test that chat with session_id passes thread_id for checkpointer-based context."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        # Track thread_id passed to use case
        received_thread_ids = []

        def mock_execute(query, channel_id, conversation_history=None, **kwargs):
            received_thread_ids.append(kwargs.get("thread_id"))
            return QueryResult(
                response=f"Response to: {query}",
                sources=[],
                iterations=1,
                session_id=kwargs.get("session_id"),
            )

        mock_pq = MagicMock()
        mock_pq.execute = mock_execute

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Create session
        session_response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions",
            json={"context_window": 10},
        )
        session_id = session_response.json()["session_id"]

        # First message
        response1 = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "What is Python?", "session_id": session_id},
        )
        assert response1.status_code == 200
        assert response1.json()["session_id"] == session_id

        # Second message
        response2 = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Tell me more about it", "session_id": session_id},
        )
        assert response2.status_code == 200

        # Verify thread_id was passed (same session_id for both calls)
        assert received_thread_ids[0] == session_id
        assert received_thread_ids[1] == session_id

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_chat_without_session_auto_bootstraps(self, client_with_db: TestClient, test_db):
        """Test that chat without explicit session_id auto-creates a session.

        Auto-session bootstrap ensures every request is stateful from the
        first turn. The conversation_history passed to the agent should be
        a callable (lazy loader) rather than an empty list.
        """
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        received_histories = []
        received_thread_ids = []

        def mock_execute(query, channel_id, conversation_history=None, **kwargs):
            received_histories.append(conversation_history)
            received_thread_ids.append(kwargs.get("thread_id"))
            return QueryResult(
                response=f"Response to: {query}",
                sources=[],
                iterations=1,
            )

        mock_pq = MagicMock()
        mock_pq.execute = mock_execute

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # First message without session — should auto-create session
        resp1 = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "What is Python?"},
        )

        # Response should contain auto-generated session_id
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1.get("session_id") is not None

        # conversation_history should be a lazy loader (callable), not []
        assert callable(received_histories[0])
        # thread_id should be set (same as session_id)
        assert received_thread_ids[0] is not None

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_get_session_history(self, client_with_db: TestClient, test_db):
        """Test getting chat history for a specific session."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/session-history-store",
            display_name="Session History Channel",
        )

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="Test response",
            sources=[],
            iterations=1,
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Create session
        session_response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/session-history-store/chat/sessions",
            json={"context_window": 10},
        )
        session_id = session_response.json()["session_id"]

        # Send message with session
        chat_response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/session-history-store/chat",
            json={"query": "Question 1", "session_id": session_id},
        )
        assert chat_response.status_code == 200

        # Get session history
        response = client_with_db.get(
            f"/api/v1/channels/fileSearchStores/session-history-store/chat/sessions/{session_id}/history"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # 1 user + 1 assistant message
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Question 1"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "Test response"

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_stream_with_session(self, client_with_db: TestClient, test_db):
        """Test streaming chat with session passes thread_id for checkpointer-based context."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        received_thread_ids = []

        # Mock ProcessQueryUseCase.execute_stream to capture thread_id
        def mock_execute_stream(query, channel_id, conversation_history=None, **kwargs):
            received_thread_ids.append(kwargs.get("thread_id"))
            def generator():
                yield {"event": "content", "content": f"Streamed: {query}"}
                yield {"event": "agent_completed"}
                return QueryResult(
                    response=f"Streamed: {query}",
                    sources=[],
                    session_id="test-session",
                    iterations=1,
                )
            return generator()

        mock_pq = MagicMock()
        mock_pq.execute_stream = mock_execute_stream

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Create session
        session_response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions",
            json={"context_window": 10},
        )
        session_id = session_response.json()["session_id"]

        # First stream request
        response1 = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": "First question", "session_id": session_id},
        )
        _ = response1.text  # Consume response

        # Second stream request
        response2 = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": "Follow up", "session_id": session_id},
        )
        _ = response2.text  # Consume response

        # Both calls should have same thread_id (= session_id)
        assert received_thread_ids[0] == session_id
        assert received_thread_ids[1] == session_id

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_stream_returns_session_id(self, client_with_db: TestClient, test_db):
        """Test that streaming response includes session_id event."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        # Mock ProcessQueryUseCase.execute_stream
        def mock_execute_stream(*args, **kwargs):
            def generator():
                yield {"event": "content", "content": "Hello"}
                yield {"event": "agent_completed"}
                return QueryResult(
                    response="Hello",
                    sources=[],
                    session_id="test-session",
                    iterations=1,
                )
            return generator()

        mock_pq = MagicMock()
        mock_pq.execute_stream = mock_execute_stream

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )
        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        # Create session
        session_response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/sessions",
            json={"context_window": 10},
        )
        session_id = session_response.json()["session_id"]

        # Stream with session
        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": "Hello", "session_id": session_id},
        )

        # Parse SSE events
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                data = line[6:]
                if data != "[DONE]":
                    events.append(json.loads(data))

        # First event should be session info (session_id field)
        session_event = next((e for e in events if "session_id" in e), None)
        assert session_event is not None
        assert session_event["session_id"] == session_id

        app.dependency_overrides.pop(get_chat_use_case_factory, None)


class TestSessionRenewalOldSessionId:
    """Tests for old_session_id exposure on session renewal (CHA-167)."""

    def test_rest_response_includes_old_session_id_on_renewal(
        self, client_with_db: TestClient, test_db
    ):
        """REST response includes old_session_id when session was renewed."""
        from datetime import datetime, UTC
        from src.shared.kernel.contracts.ports.persistence import ChatSessionDTO

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_pq = MagicMock()
        mock_pq.execute.return_value = QueryResult(
            response="Answer",
            sources=[],
            iterations=1,
        )

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )

        # Mock session_repo to simulate renewal: returns new session_id, created=True
        new_session_dto = ChatSessionDTO(
            id=99,
            session_id="sess_new_123",
            channel_id=1,
            channel_gemini_store_id="fileSearchStores/test-store",
            context_window=10,
            created_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
        )
        use_case._session_repo = MagicMock()
        use_case._session_repo.get_or_create.return_value = (new_session_dto, True)

        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "Hello", "session_id": "sess_old_expired"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_renewed"] is True
        assert data["old_session_id"] == "sess_old_expired"
        assert data["session_id"] == "sess_new_123"

        app.dependency_overrides.pop(get_chat_use_case_factory, None)

    def test_sse_session_event_includes_old_session_id_on_renewal(
        self, client_with_db: TestClient, test_db
    ):
        """SSE session event includes old_session_id when session was renewed."""
        from datetime import datetime, UTC
        from src.shared.kernel.contracts.ports.persistence import ChatSessionDTO

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        def mock_execute_stream(*args, **kwargs):
            def generator():
                yield {"event": "content", "content": "Hello"}
                yield {"event": "agent_completed"}
                return QueryResult(
                    response="Hello",
                    sources=[],
                    iterations=1,
                )
            return generator()

        mock_pq = MagicMock()
        mock_pq.execute_stream = mock_execute_stream

        use_case = _make_chat_use_case(
            channel_port=mock_channel_port,
            process_query_factory=lambda: mock_pq,
            db=test_db,
        )

        # Mock session_repo to simulate renewal
        new_session_dto = ChatSessionDTO(
            id=99,
            session_id="sess_new_456",
            channel_id=1,
            channel_gemini_store_id="fileSearchStores/test-store",
            context_window=10,
            created_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
        )
        use_case._session_repo = MagicMock()
        use_case._session_repo.get_or_create.return_value = (new_session_dto, True)

        app.dependency_overrides[get_chat_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat/stream",
            json={"query": "Hello", "session_id": "sess_old_expired"},
        )

        assert response.status_code == 200
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                data = line[6:]
                if data != "[DONE]":
                    events.append(json.loads(data))

        # Find session event
        session_event = next((e for e in events if "session_id" in e), None)
        assert session_event is not None
        assert session_event["session_id"] == "sess_new_456"
        assert session_event["session_renewed"] is True
        assert session_event["old_session_id"] == "sess_old_expired"

        app.dependency_overrides.pop(get_chat_use_case_factory, None)


def _mock_document_search():
    """Create a mock DocumentSearchPort for tests that directly construct runners."""
    mock_ds = MagicMock()
    mock_ds.search.return_value = []
    mock_ds.search_with_answer.return_value = {"response": "", "sources": []}
    return mock_ds


class TestCheckpointMissFallback:
    """Tests for checkpoint miss DB history fallback (CHA-167)."""

    def test_checkpoint_miss_invokes_history_loader(self):
        """When checkpointer has no state, the lazy history loader is called."""
        from langgraph.checkpoint.memory import MemorySaver
        from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
        from src.shared.kernel.contracts.ports.agent_runner import AgentConfig

        checkpointer = MemorySaver()
        runner = LangGraphAgentRunner(checkpointer=checkpointer, document_search=_mock_document_search())

        # Track whether the lazy loader was called
        loader_called = []

        def lazy_loader():
            loader_called.append(True)
            return [
                {"role": "user", "content": "previous question"},
                {"role": "assistant", "content": "previous answer"},
            ]

        # Mock _create_agent to avoid real LLM calls
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [MagicMock(content="response", type="ai", tool_calls=[])]
        }
        runner._create_agent = MagicMock(return_value=mock_agent)

        config = AgentConfig(max_iterations=5)
        context = {
            "channel_id": "test-channel",
            "conversation_history": lazy_loader,
            "thread_id": "sess_no_checkpoint",
        }

        runner.run(query="new question", config=config, context=context)

        # Loader should have been called because no checkpoint exists
        assert len(loader_called) == 1

        # Verify the messages include history + new query
        call_args = mock_agent.invoke.call_args
        messages = call_args[0][0]["messages"]
        assert len(messages) == 3  # 2 history + 1 new
        assert messages[0] == ("user", "previous question")
        assert messages[1] == ("assistant", "previous answer")
        assert messages[2] == ("user", "new question")

    def test_checkpoint_hit_skips_history_loader(self):
        """When checkpoint exists, the lazy history loader is NOT called."""
        from langgraph.checkpoint.memory import MemorySaver
        from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
        from src.shared.kernel.contracts.ports.agent_runner import AgentConfig

        checkpointer = MemorySaver()
        runner = LangGraphAgentRunner(checkpointer=checkpointer, document_search=_mock_document_search())

        # Pre-populate checkpoint state so get_tuple returns non-None
        thread_id = "sess_has_checkpoint"
        checkpoint_config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": ""}}
        checkpointer.put(
            config=checkpoint_config,
            checkpoint={
                "v": 1,
                "id": "ckpt-1",
                "ts": "2026-01-01T00:00:00+00:00",
                "channel_values": {},
                "channel_versions": {},
                "versions_seen": {},
                "pending_sends": [],
            },
            metadata={"source": "input", "step": 0, "writes": {}, "parents": {}},
            new_versions={},
        )

        loader_called = []

        def lazy_loader():
            loader_called.append(True)
            return [{"role": "user", "content": "old"}]

        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [MagicMock(content="response", type="ai", tool_calls=[])]
        }
        runner._create_agent = MagicMock(return_value=mock_agent)

        config = AgentConfig(max_iterations=5)
        context = {
            "channel_id": "test-channel",
            "conversation_history": lazy_loader,
            "thread_id": thread_id,
        }

        runner.run(query="new question", config=config, context=context)

        # Loader should NOT have been called - checkpoint exists
        assert len(loader_called) == 0

        # Only the new query should be in messages
        call_args = mock_agent.invoke.call_args
        messages = call_args[0][0]["messages"]
        assert len(messages) == 1
        assert messages[0] == ("user", "new question")


class TestCheckpointMissFallbackStream:
    """Tests for checkpoint miss DB history fallback via run_stream() (CHA-170)."""

    def test_stream_checkpoint_miss_invokes_history_loader(self):
        """run_stream(): when checkpointer has no state, the lazy history loader is called."""
        from langgraph.checkpoint.memory import MemorySaver
        from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
        from src.shared.kernel.contracts.ports.agent_runner import AgentConfig

        checkpointer = MemorySaver()
        runner = LangGraphAgentRunner(checkpointer=checkpointer, document_search=_mock_document_search())

        loader_called = []

        def lazy_loader():
            loader_called.append(True)
            return [
                {"role": "user", "content": "previous question"},
                {"role": "assistant", "content": "previous answer"},
            ]

        # Mock _create_agent to return an agent whose .stream yields (msg, metadata) pairs
        ai_msg = MagicMock(content="response", type="ai", tool_calls=[])
        mock_agent = MagicMock()
        mock_agent.stream.return_value = [(ai_msg, {"langgraph_node": "agent"})]
        runner._create_agent = MagicMock(return_value=mock_agent)

        config = AgentConfig(max_iterations=5)
        context = {
            "channel_id": "test-channel",
            "conversation_history": lazy_loader,
            "thread_id": "sess_no_checkpoint_stream",
        }

        # Consume the generator to drive execution
        gen = runner.run_stream(query="new question", config=config, context=context)
        events = []
        try:
            while True:
                events.append(next(gen))
        except StopIteration:
            pass

        # Loader should have been called because no checkpoint exists
        assert len(loader_called) == 1

        # Verify the messages include history + new query
        call_args = mock_agent.stream.call_args
        messages = call_args[0][0]["messages"]
        assert len(messages) == 3  # 2 history + 1 new
        assert messages[0] == ("user", "previous question")
        assert messages[1] == ("assistant", "previous answer")
        assert messages[2] == ("user", "new question")

    def test_stream_checkpoint_hit_skips_history_loader(self):
        """run_stream(): when checkpoint exists, the lazy history loader is NOT called."""
        from langgraph.checkpoint.memory import MemorySaver
        from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
        from src.shared.kernel.contracts.ports.agent_runner import AgentConfig

        checkpointer = MemorySaver()
        runner = LangGraphAgentRunner(checkpointer=checkpointer, document_search=_mock_document_search())

        # Pre-populate checkpoint state so get_tuple returns non-None
        thread_id = "sess_has_checkpoint_stream"
        checkpoint_config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": ""}}
        checkpointer.put(
            config=checkpoint_config,
            checkpoint={
                "v": 1,
                "id": "ckpt-stream-1",
                "ts": "2026-01-01T00:00:00+00:00",
                "channel_values": {},
                "channel_versions": {},
                "versions_seen": {},
                "pending_sends": [],
            },
            metadata={"source": "input", "step": 0, "writes": {}, "parents": {}},
            new_versions={},
        )

        loader_called = []

        def lazy_loader():
            loader_called.append(True)
            return [{"role": "user", "content": "old"}]

        # Mock _create_agent to return an agent whose .stream yields (msg, metadata) pairs
        ai_msg = MagicMock(content="response", type="ai", tool_calls=[])
        mock_agent = MagicMock()
        mock_agent.stream.return_value = [(ai_msg, {"langgraph_node": "agent"})]
        runner._create_agent = MagicMock(return_value=mock_agent)

        config = AgentConfig(max_iterations=5)
        context = {
            "channel_id": "test-channel",
            "conversation_history": lazy_loader,
            "thread_id": thread_id,
        }

        # Consume the generator to drive execution
        gen = runner.run_stream(query="new question", config=config, context=context)
        events = []
        try:
            while True:
                events.append(next(gen))
        except StopIteration:
            pass

        # Loader should NOT have been called - checkpoint exists
        assert len(loader_called) == 0

        # Only the new query should be in messages
        call_args = mock_agent.stream.call_args
        messages = call_args[0][0]["messages"]
        assert len(messages) == 1
        assert messages[0] == ("user", "new question")


class TestSqliteSaverIntegration:
    """Integration tests for SqliteSaver real path (CHA-172)."""

    def test_sqlite_saver_put_and_get_tuple(self, tmp_path):
        """SqliteSaver can store and retrieve checkpoints via real SQLite file."""
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = str(tmp_path / "test_checkpoints.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()

        thread_id = "integration_thread_1"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": ""}}

        # Initially no checkpoint
        assert saver.get_tuple({"configurable": {"thread_id": thread_id}}) is None

        # Put a checkpoint
        saver.put(
            config=config,
            checkpoint={
                "v": 1,
                "id": "ckpt-int-1",
                "ts": "2026-01-01T00:00:00+00:00",
                "channel_values": {},
                "channel_versions": {},
                "versions_seen": {},
                "pending_sends": [],
            },
            metadata={"source": "input", "step": 0, "writes": {}, "parents": {}},
            new_versions={},
        )

        # Now get_tuple should return non-None
        result = saver.get_tuple({"configurable": {"thread_id": thread_id}})
        assert result is not None

        conn.close()

    def test_sqlite_saver_survives_reconnect(self, tmp_path):
        """Checkpoint persists after closing and reopening the SQLite connection."""
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = str(tmp_path / "persist_checkpoints.db")

        # First connection: write checkpoint
        conn1 = sqlite3.connect(db_path, check_same_thread=False)
        saver1 = SqliteSaver(conn1)
        saver1.setup()

        thread_id = "persist_thread"
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": ""}}
        saver1.put(
            config=config,
            checkpoint={
                "v": 1,
                "id": "ckpt-persist-1",
                "ts": "2026-01-01T00:00:00+00:00",
                "channel_values": {},
                "channel_versions": {},
                "versions_seen": {},
                "pending_sends": [],
            },
            metadata={"source": "input", "step": 0, "writes": {}, "parents": {}},
            new_versions={},
        )
        conn1.close()

        # Second connection: verify checkpoint survived
        conn2 = sqlite3.connect(db_path, check_same_thread=False)
        saver2 = SqliteSaver(conn2)
        saver2.setup()

        result = saver2.get_tuple({"configurable": {"thread_id": thread_id}})
        assert result is not None
        conn2.close()

    def test_sqlite_saver_with_runner_checkpoint_miss(self, tmp_path):
        """LangGraphAgentRunner correctly detects miss/hit with real SqliteSaver."""
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver
        from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
        from src.shared.kernel.contracts.ports.agent_runner import AgentConfig

        db_path = str(tmp_path / "runner_checkpoints.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()

        runner = LangGraphAgentRunner(checkpointer=saver, document_search=_mock_document_search())

        loader_called = []

        def lazy_loader():
            loader_called.append(True)
            return [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]

        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "messages": [MagicMock(content="response", type="ai", tool_calls=[])]
        }
        runner._create_agent = MagicMock(return_value=mock_agent)

        config = AgentConfig(max_iterations=5)
        context = {
            "channel_id": "test-channel",
            "conversation_history": lazy_loader,
            "thread_id": "sqlite_thread_miss",
        }

        # First call: no checkpoint → miss → loader called
        runner.run(query="question", config=config, context=context)
        assert len(loader_called) == 1
        assert runner._checkpoint_miss_count == 1
        assert runner._checkpoint_hit_count == 0

        conn.close()

    def test_get_checkpointer_returns_sqlite_saver(self, tmp_path, monkeypatch):
        """get_checkpointer() returns SqliteSaver when properly configured."""
        import src.modules.conversation.infrastructure.di as conv_di

        # Reset singleton
        conv_di._checkpointer = None

        # Patch settings to use tmp path
        monkeypatch.setenv("CHECKPOINT_DB_PATH", str(tmp_path / "cp.db"))
        monkeypatch.setenv("STRICT_CHECKPOINTER", "false")

        # Clear settings cache so new env vars are picked up
        from src.core.config import get_settings
        get_settings.cache_clear()

        try:
            cp = conv_di.get_checkpointer()
            assert type(cp).__name__ == "SqliteSaver"
        finally:
            # Cleanup
            conv_di._checkpointer = None
            get_settings.cache_clear()

    def test_strict_checkpointer_raises_on_failure(self, tmp_path, monkeypatch):
        """When strict_checkpointer=True and SqliteSaver fails, RuntimeError is raised."""
        import src.modules.conversation.infrastructure.di as conv_di

        # Reset singleton
        conv_di._checkpointer = None

        # Set strict mode and invalid path to force failure
        monkeypatch.setenv("STRICT_CHECKPOINTER", "true")

        from src.core.config import get_settings
        get_settings.cache_clear()

        # Patch SqliteSaver import to simulate failure
        original_get_checkpointer = conv_di.get_checkpointer

        def patched_get_checkpointer():
            conv_di._checkpointer = None
            # Temporarily make SqliteSaver import fail
            import unittest.mock
            with unittest.mock.patch.dict("sys.modules", {"langgraph.checkpoint.sqlite": None}):
                return original_get_checkpointer()

        try:
            with pytest.raises(RuntimeError, match="strict_checkpointer=True"):
                patched_get_checkpointer()
        finally:
            conv_di._checkpointer = None
            get_settings.cache_clear()
