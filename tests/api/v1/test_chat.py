# -*- coding: utf-8 -*-
"""Tests for Chat API."""

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service
from src.core.database import get_db
from src.application.use_cases.process_query import QueryResult


class TestSendMessage:
    """Tests for POST /api/v1/chat."""

    def test_send_message_success(self, client_with_db: TestClient, test_db):
        """Test successful chat message."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_and_answer.return_value = {
            "response": "This is the answer based on the documents.",
            "sources": [
                {"source": "document.pdf", "content": "Relevant content here"},
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is the main topic?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is the main topic?"
        assert data["response"] == "This is the answer based on the documents."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "document.pdf"

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_send_message_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test sending message to non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/not-exists"},
            json={"query": "What is this?"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_send_message_empty_query(self, client_with_db: TestClient, test_db):
        """Test sending empty query fails."""
        response = client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_send_message_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_and_answer.return_value = {
            "response": "",
            "error": "API Error occurred",
            "sources": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is this?"},
        )

        assert response.status_code == 500

        app.dependency_overrides.pop(get_gemini_service, None)


class TestGetChatHistory:
    """Tests for GET /api/v1/chat/history."""

    def test_get_history_empty(self, client_with_db: TestClient, test_db):
        """Test getting empty history."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.get(
            "/api/v1/chat/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["messages"] == []
        assert data["total"] == 0

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_get_history_with_messages(self, client_with_db: TestClient, test_db):
        """Test getting history after sending messages."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_and_answer.return_value = {
            "response": "Answer here",
            "sources": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Send a message first
        client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "Hello?"},
        )

        # Get history
        response = client_with_db.get(
            "/api/v1/chat/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # user + assistant
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello?"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "Answer here"

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_get_history_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test getting history for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.get(
            "/api/v1/chat/history",
            params={"channel_id": "fileSearchStores/not-exists"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)


class TestClearChatHistory:
    """Tests for DELETE /api/v1/chat/history."""

    def test_clear_history_success(self, client_with_db: TestClient, test_db):
        """Test clearing chat history."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_and_answer.return_value = {
            "response": "Answer",
            "sources": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Send a message first
        client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "Hello?"},
        )

        # Clear history
        response = client_with_db.delete(
            "/api/v1/chat/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 204

        # Verify history is cleared
        response = client_with_db.get(
            "/api/v1/chat/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )
        assert response.json()["total"] == 0

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_clear_history_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test clearing history for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.delete(
            "/api/v1/chat/history",
            params={"channel_id": "fileSearchStores/not-exists"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)


class TestStreamMessage:
    """Tests for POST /api/v1/chat/stream (SSE streaming).

    Uses Clean Architecture with ProcessQueryUseCase.execute_stream().
    SSE format:
    - {"chunk": "text"} for content
    - {"sources": [...]} for sources
    - [DONE] for completion
    - {"error": "message"} for errors
    """

    def test_stream_message_success(self, client_with_db: TestClient, test_db):
        """Test successful streaming chat message."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

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

        mock_use_case = MagicMock()
        mock_use_case.execute_stream = mock_execute_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.chat.create_process_query_use_case", return_value=mock_use_case):
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

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_message_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test streaming to non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/chat/stream",
            json={"query": "What is this?"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_message_error_event(self, client_with_db: TestClient, test_db):
        """Test streaming with error event."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

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

        mock_use_case = MagicMock()
        mock_use_case.execute_stream = mock_execute_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.chat.create_process_query_use_case", return_value=mock_use_case):
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

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_saves_to_history(self, client_with_db: TestClient, test_db):
        """Test that streaming saves messages to history."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

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

        mock_use_case = MagicMock()
        mock_use_case.execute_stream = mock_execute_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.chat.create_process_query_use_case", return_value=mock_use_case):
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

        app.dependency_overrides.pop(get_gemini_service, None)

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
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/chat/sessions",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"context_window": 10},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["session_id"].startswith("sess_")
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["context_window"] == 10

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_create_session_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test creating session for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/chat/sessions",
            params={"channel_id": "fileSearchStores/not-exists"},
            json={"context_window": 10},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_get_session_success(self, client_with_db: TestClient, test_db):
        """Test getting session information."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create session first
        create_response = client_with_db.post(
            "/api/v1/chat/sessions",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"context_window": 5},
        )
        session_id = create_response.json()["session_id"]

        # Get session
        response = client_with_db.get(f"/api/v1/chat/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["context_window"] == 5

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_get_session_not_found(self, client_with_db: TestClient, test_db):
        """Test getting non-existent session."""
        mock_gemini = MagicMock()
        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.get("/api/v1/chat/sessions/sess_nonexistent")

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_delete_session_success(self, client_with_db: TestClient, test_db):
        """Test deleting a session."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create session first
        create_response = client_with_db.post(
            "/api/v1/chat/sessions",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"context_window": 10},
        )
        session_id = create_response.json()["session_id"]

        # Delete session
        response = client_with_db.delete(f"/api/v1/chat/sessions/{session_id}")

        assert response.status_code == 204

        # Verify session is deleted
        get_response = client_with_db.get(f"/api/v1/chat/sessions/{session_id}")
        assert get_response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_delete_session_not_found(self, client_with_db: TestClient, test_db):
        """Test deleting non-existent session."""
        response = client_with_db.delete("/api/v1/chat/sessions/sess_nonexistent")

        assert response.status_code == 404


class TestMultiTurnConversation:
    """Tests for multi-turn conversation with session context."""

    def test_chat_with_session_maintains_context(self, client_with_db: TestClient, test_db):
        """Test that chat with session_id maintains conversation context."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        # Track conversation history passed to search_and_answer
        received_histories = []

        def mock_search_and_answer(store_name, query, conversation_history=None, model="gemini-2.5-flash"):
            received_histories.append(conversation_history)
            return {
                "response": f"Response to: {query}",
                "sources": [],
            }

        mock_gemini.search_and_answer = mock_search_and_answer

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create session
        session_response = client_with_db.post(
            "/api/v1/chat/sessions",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"context_window": 10},
        )
        session_id = session_response.json()["session_id"]

        # First message
        response1 = client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is Python?", "session_id": session_id},
        )
        assert response1.status_code == 200
        assert response1.json()["session_id"] == session_id

        # Second message - should include first message in context
        response2 = client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "Tell me more about it", "session_id": session_id},
        )
        assert response2.status_code == 200

        # Verify context was passed
        # First call has no history
        assert received_histories[0] == []

        # Second call should have context
        assert len(received_histories[1]) == 2
        assert received_histories[1][0]["role"] == "user"
        assert received_histories[1][0]["content"] == "What is Python?"
        assert received_histories[1][1]["role"] == "assistant"
        assert "Response to: What is Python?" in received_histories[1][1]["content"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_chat_without_session_no_context(self, client_with_db: TestClient, test_db):
        """Test that chat without session_id doesn't maintain context."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        received_histories = []

        def mock_search_and_answer(store_name, query, conversation_history=None, model="gemini-2.5-flash"):
            received_histories.append(conversation_history)
            return {
                "response": f"Response to: {query}",
                "sources": [],
            }

        mock_gemini.search_and_answer = mock_search_and_answer

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # First message without session
        client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is Python?"},
        )

        # Second message without session
        client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "Tell me more about it"},
        )

        # Both calls should have empty history
        assert received_histories[0] == []
        assert received_histories[1] == []

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_get_session_history(self, client_with_db: TestClient, test_db):
        """Test getting chat history for a specific session."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/session-history-store",
            "display_name": "Session History Channel",
        }
        mock_gemini.search_and_answer.return_value = {
            "response": "Test response",
            "sources": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create session
        session_response = client_with_db.post(
            "/api/v1/chat/sessions",
            params={"channel_id": "fileSearchStores/session-history-store"},
            json={"context_window": 10},
        )
        session_id = session_response.json()["session_id"]

        # Send message with session
        chat_response = client_with_db.post(
            "/api/v1/chat",
            params={"channel_id": "fileSearchStores/session-history-store"},
            json={"query": "Question 1", "session_id": session_id},
        )
        assert chat_response.status_code == 200

        # Get session history
        response = client_with_db.get(f"/api/v1/chat/sessions/{session_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # 1 user + 1 assistant message
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Question 1"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "Test response"

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_with_session(self, client_with_db: TestClient, test_db):
        """Test streaming chat with session maintains context."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        received_histories = []

        # Mock ProcessQueryUseCase.execute_stream to capture history
        def mock_execute_stream(query, channel_id, conversation_history=None, **kwargs):
            received_histories.append(conversation_history or [])
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

        mock_use_case = MagicMock()
        mock_use_case.execute_stream = mock_execute_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.chat.create_process_query_use_case", return_value=mock_use_case):
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

        # First call has no history
        assert received_histories[0] == []

        # Second call should have context
        assert len(received_histories[1]) == 2
        assert received_histories[1][0]["content"] == "First question"

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_returns_session_id(self, client_with_db: TestClient, test_db):
        """Test that streaming response includes session_id event."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

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

        mock_use_case = MagicMock()
        mock_use_case.execute_stream = mock_execute_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        with patch("src.api.v1.chat.create_process_query_use_case", return_value=mock_use_case):
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

        app.dependency_overrides.pop(get_gemini_service, None)
