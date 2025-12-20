# -*- coding: utf-8 -*-
"""Tests for Chat API."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service
from src.core.database import get_db


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
