# -*- coding: utf-8 -*-
"""Tests for Multi-channel Search API."""

import json
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service
from src.core.database import get_db


class TestMultiChannelSearch:
    """Tests for POST /api/v1/search."""

    def test_search_single_channel_success(self, client_with_db: TestClient, test_db):
        """Test successful search with single channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store-1",
            "display_name": "Test Channel 1",
        }
        mock_gemini.multi_store_search.return_value = {
            "response": "This is the answer based on multiple channels.",
            "sources": [
                {"source": "document1.pdf", "content": "Content from channel 1"},
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": ["fileSearchStores/test-store-1"],
                "query": "What is the main topic?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "What is the main topic?"
        assert data["response"] == "This is the answer based on multiple channels."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "document1.pdf"
        assert data["searched_channels"] == ["fileSearchStores/test-store-1"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_search_multiple_channels_success(self, client_with_db: TestClient, test_db):
        """Test successful search with multiple channels."""
        mock_gemini = MagicMock()

        def mock_get_store(channel_id):
            return {
                "name": channel_id,
                "display_name": f"Channel {channel_id[-1]}",
            }

        mock_gemini.get_store = mock_get_store
        mock_gemini.multi_store_search.return_value = {
            "response": "Combined answer from multiple sources.",
            "sources": [
                {"source": "doc1.pdf", "content": "From first channel"},
                {"source": "doc2.pdf", "content": "From second channel"},
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": [
                    "fileSearchStores/store-1",
                    "fileSearchStores/store-2",
                    "fileSearchStores/store-3",
                ],
                "query": "What do these documents say?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Combined answer from multiple sources."
        assert len(data["sources"]) == 2
        assert len(data["searched_channels"]) == 3

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_search_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test search with non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": ["fileSearchStores/not-exists"],
                "query": "What is this?",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_search_partial_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test search with some channels not found."""
        mock_gemini = MagicMock()

        def mock_get_store(channel_id):
            if "valid" in channel_id:
                return {"name": channel_id, "display_name": "Existing Channel"}
            return None

        mock_gemini.get_store = mock_get_store

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": [
                    "fileSearchStores/valid-1",
                    "fileSearchStores/missing-1",
                ],
                "query": "Test query",
            },
        )

        # Should fail because one channel doesn't exist
        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_search_empty_channel_list(self, client_with_db: TestClient, test_db):
        """Test search with empty channel list fails validation."""
        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": [],
                "query": "What is this?",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_search_too_many_channels(self, client_with_db: TestClient, test_db):
        """Test search with more than 5 channels fails validation."""
        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": [f"channel-{i}" for i in range(6)],
                "query": "What is this?",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_search_empty_query(self, client_with_db: TestClient, test_db):
        """Test search with empty query fails validation."""
        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": ["fileSearchStores/test-store"],
                "query": "",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_search_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.multi_store_search.return_value = {
            "response": "",
            "error": "API Error occurred",
            "sources": [],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": ["fileSearchStores/test-store"],
                "query": "What is this?",
            },
        )

        assert response.status_code == 500

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_search_sources_include_channel_info(self, client_with_db: TestClient, test_db):
        """Test that search sources include channel information."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "My Test Channel",
        }
        mock_gemini.multi_store_search.return_value = {
            "response": "Answer with sources",
            "sources": [
                {"source": "document.pdf", "content": "Relevant content"},
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search",
            json={
                "channel_ids": ["fileSearchStores/test-store"],
                "query": "What is the topic?",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 1
        source = data["sources"][0]
        assert "channel_id" in source
        assert "channel_name" in source
        assert source["channel_id"] == "fileSearchStores/test-store"

        app.dependency_overrides.pop(get_gemini_service, None)


class TestMultiChannelSearchStream:
    """Tests for POST /api/v1/search/stream (SSE streaming)."""

    def test_stream_search_success(self, client_with_db: TestClient, test_db):
        """Test successful streaming multi-channel search."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": "Hello "}
            yield {"type": "content", "text": "World!"}
            yield {"type": "sources", "sources": [{"source": "doc.pdf", "content": "test"}]}
            yield {"type": "done"}

        mock_gemini.multi_store_search_stream = mock_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search/stream",
            json={
                "channel_ids": ["fileSearchStores/test-store"],
                "query": "What is this?",
            },
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
        assert events[2]["type"] == "sources"
        # Verify sources are enriched with channel info
        assert "searched_channels" in events[2]
        assert events[3] == {"type": "done"}

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_search_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test streaming search with non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search/stream",
            json={
                "channel_ids": ["fileSearchStores/not-exists"],
                "query": "What is this?",
            },
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_search_error_event(self, client_with_db: TestClient, test_db):
        """Test streaming search with error event."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }

        def mock_stream(*args, **kwargs):
            yield {"type": "error", "error": "API Error"}

        mock_gemini.multi_store_search_stream = mock_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search/stream",
            json={
                "channel_ids": ["fileSearchStores/test-store"],
                "query": "What is this?",
            },
        )

        assert response.status_code == 200  # SSE still returns 200

        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["error"] == "API Error"

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_search_multiple_channels(self, client_with_db: TestClient, test_db):
        """Test streaming search with multiple channels."""
        mock_gemini = MagicMock()

        def mock_get_store(channel_id):
            return {
                "name": channel_id,
                "display_name": f"Channel {channel_id[-1]}",
            }

        mock_gemini.get_store = mock_get_store

        def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": "Combined answer"}
            yield {
                "type": "sources",
                "sources": [
                    {"source": "doc1.pdf", "content": "From channel 1"},
                    {"source": "doc2.pdf", "content": "From channel 2"},
                ],
            }
            yield {"type": "done"}

        mock_gemini.multi_store_search_stream = mock_stream

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/search/stream",
            json={
                "channel_ids": [
                    "fileSearchStores/store-1",
                    "fileSearchStores/store-2",
                ],
                "query": "Combined search",
            },
        )

        assert response.status_code == 200

        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        # Find the sources event
        sources_event = next((e for e in events if e.get("type") == "sources"), None)
        assert sources_event is not None
        assert len(sources_event["searched_channels"]) == 2

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_stream_search_empty_query(self, client_with_db: TestClient, test_db):
        """Test streaming search with empty query fails validation."""
        response = client_with_db.post(
            "/api/v1/search/stream",
            json={
                "channel_ids": ["fileSearchStores/test-store"],
                "query": "",
            },
        )

        assert response.status_code == 422  # Validation error
