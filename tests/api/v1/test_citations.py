# -*- coding: utf-8 -*-
"""Tests for Citations API."""

import json
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service
from src.core.database import get_db


class TestQueryWithCitations:
    """Tests for POST /api/v1/citations."""

    def test_query_with_citations_success(self, client_with_db: TestClient, test_db):
        """Test successful query with inline citations."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_with_citations.return_value = {
            "response": "The answer is based on documents. [1] More info here. [2]",
            "response_plain": "The answer is based on documents. More info here.",
            "citations": [
                {
                    "index": 1,
                    "source": "document1.pdf",
                    "content": "Relevant content from doc 1",
                    "page": 5,
                    "start_index": 100,
                    "end_index": 200,
                },
                {
                    "index": 2,
                    "source": "document2.pdf",
                    "content": "Content from doc 2",
                    "page": 3,
                    "start_index": None,
                    "end_index": None,
                },
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is the main topic?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is the main topic?"
        assert "[1]" in data["response"]
        assert "[2]" in data["response"]
        assert "[1]" not in data["response_plain"]
        assert len(data["citations"]) == 2
        assert data["citations"][0]["index"] == 1
        assert data["citations"][0]["source"] == "document1.pdf"
        assert data["citations"][0]["location"]["page"] == 5

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_query_with_citations_channel_not_found(
        self, client_with_db: TestClient, test_db
    ):
        """Test query with non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations",
            params={"channel_id": "fileSearchStores/not-exists"},
            json={"query": "What is this?"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_query_with_citations_empty_query(self, client_with_db: TestClient, test_db):
        """Test query with empty query fails validation."""
        response = client_with_db.post(
            "/api/v1/citations",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": ""},
        )

        assert response.status_code == 422

    def test_query_with_citations_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_with_citations.return_value = {
            "response": "",
            "response_plain": "",
            "citations": [],
            "error": "API Error occurred",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is this?"},
        )

        assert response.status_code == 500

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_query_with_no_citations(self, client_with_db: TestClient, test_db):
        """Test query that returns no citations."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_with_citations.return_value = {
            "response": "General answer without specific sources.",
            "response_plain": "General answer without specific sources.",
            "citations": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is this?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["citations"] == []

        app.dependency_overrides.pop(get_gemini_service, None)


class TestQueryWithCitationsStream:
    """Tests for POST /api/v1/citations/stream."""

    def test_stream_with_citations_success(self, client_with_db: TestClient, test_db):
        """Test successful streaming query with citations."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": "Hello "}
            yield {"type": "content", "text": "World!"}
            yield {
                "type": "citations",
                "response_with_citations": "Hello World! [1]",
                "citations": [
                    {
                        "index": 1,
                        "source": "doc.pdf",
                        "content": "test content",
                        "page": 1,
                    }
                ],
            }
            yield {"type": "done"}

        mock_gemini.search_with_citations_stream = mock_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations/stream",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is this?", "include_citations": True},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE events
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) == 4
        assert events[0] == {"type": "content", "text": "Hello "}
        assert events[1] == {"type": "content", "text": "World!"}
        assert events[2]["type"] == "citations"
        assert "[1]" in events[2]["response_with_citations"]
        assert len(events[2]["citations"]) == 1
        assert events[3] == {"type": "done"}

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test streaming with non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations/stream",
            params={"channel_id": "fileSearchStores/not-exists"},
            json={"query": "What is this?", "include_citations": True},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_error_event(self, client_with_db: TestClient, test_db):
        """Test streaming with error event."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        def mock_stream(*args, **kwargs):
            yield {"type": "error", "error": "API Error"}

        mock_gemini.search_with_citations_stream = mock_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations/stream",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "What is this?", "include_citations": True},
        )

        assert response.status_code == 200

        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) == 1
        assert events[0]["type"] == "error"

        app.dependency_overrides.pop(get_gemini_service, None)


class TestGetCitationDetail:
    """Tests for GET /api/v1/citations/{citation_index}."""

    def test_get_citation_detail_success(self, client_with_db: TestClient, test_db):
        """Test getting citation details."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.get(
            "/api/v1/citations/1",
            params={
                "channel_id": "fileSearchStores/test-store",
                "source": "document.pdf",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["index"] == 1
        assert data["source"] == "document.pdf"
        assert "location" in data

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_get_citation_detail_channel_not_found(
        self, client_with_db: TestClient, test_db
    ):
        """Test getting citation for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.get(
            "/api/v1/citations/1",
            params={
                "channel_id": "fileSearchStores/not-exists",
                "source": "document.pdf",
            },
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)


class TestInlineCitationInsertion:
    """Tests for inline citation insertion logic."""

    def test_citations_inserted_in_response(self, client_with_db: TestClient, test_db):
        """Test that citation markers are properly inserted."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.search_with_citations.return_value = {
            "response": "First sentence. [1] Second sentence. [2]",
            "response_plain": "First sentence. Second sentence.",
            "citations": [
                {"index": 1, "source": "doc1.pdf", "content": "First sentence content"},
                {"index": 2, "source": "doc2.pdf", "content": "Second sentence content"},
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/citations",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"query": "Tell me about the topics"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify citations are in the response but not in plain version
        assert "[1]" in data["response"]
        assert "[2]" in data["response"]
        assert "[1]" not in data["response_plain"]
        assert "[2]" not in data["response_plain"]

        app.dependency_overrides.pop(get_gemini_service, None)
