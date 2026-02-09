# -*- coding: utf-8 -*-
"""Tests for Search History API."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.api.v1.search import get_search_history_use_case
from src.api.v1.chat import get_chat_use_case
from src.application.ports.channel import ChannelDTO
from src.infrastructure.persistence.channel_repository import ChannelRepository
from src.infrastructure.persistence.search_repository import SearchHistoryRepository


def _make_use_case(test_db, channel_port=None):
    """Create a SearchHistoryUseCase with real DB repos and mocked external port."""
    from src.application.use_cases.search_history import SearchHistoryUseCase
    from src.infrastructure.di.container import (
        create_channel_repository_port,
        create_search_history_repository_port,
    )
    return SearchHistoryUseCase(
        channel_port=channel_port or MagicMock(),
        channel_repo=create_channel_repository_port(test_db),
        search_history_repo=create_search_history_repository_port(test_db),
    )


class TestGetSearchHistory:
    """Tests for GET /api/v1/search/history."""

    def test_get_history_empty(self, client_with_db: TestClient, test_db):
        """Test getting empty search history."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        response = client_with_db.get(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["history"] == []
        assert data["total"] == 0

        app.dependency_overrides.pop(get_search_history_use_case, None)

    def test_get_history_with_entries(self, client_with_db: TestClient, test_db):
        """Test getting search history with entries."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        # Create channel and add search history directly
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )

        search_repo = SearchHistoryRepository(test_db)
        search_repo.add_or_update(channel, "first query")
        search_repo.add_or_update(channel, "second query")

        response = client_with_db.get(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["history"]) == 2

        app.dependency_overrides.pop(get_search_history_use_case, None)

    def test_get_history_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test getting history for non-existent channel returns empty (local-first)."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = None

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        response = client_with_db.get(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/not-exists"},
        )

        # Local-first: returns empty history instead of 404
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["history"] == []

        app.dependency_overrides.pop(get_search_history_use_case, None)


class TestGetSearchSuggestions:
    """Tests for GET /api/v1/search/suggestions."""

    def test_get_suggestions_empty(self, client_with_db: TestClient, test_db):
        """Test getting suggestions when empty."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        response = client_with_db.get(
            "/api/v1/search/suggestions",
            params={"channel_id": "fileSearchStores/test-store", "q": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []
        assert data["query"] == "test"

        app.dependency_overrides.pop(get_search_history_use_case, None)

    def test_get_suggestions_with_prefix(self, client_with_db: TestClient, test_db):
        """Test getting suggestions with matching prefix."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        # Create channel and add search history
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )

        search_repo = SearchHistoryRepository(test_db)
        search_repo.add_or_update(channel, "what is machine learning")
        search_repo.add_or_update(channel, "what is deep learning")
        search_repo.add_or_update(channel, "how does it work")

        response = client_with_db.get(
            "/api/v1/search/suggestions",
            params={"channel_id": "fileSearchStores/test-store", "q": "what"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 2
        assert all("what" in s["query"].lower() for s in data["suggestions"])

        app.dependency_overrides.pop(get_search_history_use_case, None)

    def test_get_suggestions_popular_when_no_prefix(self, client_with_db: TestClient, test_db):
        """Test getting popular suggestions when no prefix."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        # Create channel and add search history with different counts
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )

        search_repo = SearchHistoryRepository(test_db)
        # Search "popular query" multiple times
        search_repo.add_or_update(channel, "popular query")
        search_repo.add_or_update(channel, "popular query")
        search_repo.add_or_update(channel, "popular query")
        search_repo.add_or_update(channel, "less popular")

        response = client_with_db.get(
            "/api/v1/search/suggestions",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 2
        # First suggestion should be most popular
        assert data["suggestions"][0]["query"] == "popular query"
        assert data["suggestions"][0]["search_count"] == 3

        app.dependency_overrides.pop(get_search_history_use_case, None)


class TestGetPopularSearches:
    """Tests for GET /api/v1/search/popular."""

    def test_get_popular_empty(self, client_with_db: TestClient, test_db):
        """Test getting popular searches when empty."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        response = client_with_db.get(
            "/api/v1/search/popular",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []

        app.dependency_overrides.pop(get_search_history_use_case, None)

    def test_get_popular_sorted_by_count(self, client_with_db: TestClient, test_db):
        """Test that popular searches are sorted by count."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        # Create channel and add search history
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )

        search_repo = SearchHistoryRepository(test_db)
        search_repo.add_or_update(channel, "query A")
        search_repo.add_or_update(channel, "query B")
        search_repo.add_or_update(channel, "query B")
        search_repo.add_or_update(channel, "query C")
        search_repo.add_or_update(channel, "query C")
        search_repo.add_or_update(channel, "query C")

        response = client_with_db.get(
            "/api/v1/search/popular",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 3
        assert data["suggestions"][0]["query"] == "query C"
        assert data["suggestions"][0]["search_count"] == 3
        assert data["suggestions"][1]["query"] == "query B"
        assert data["suggestions"][1]["search_count"] == 2
        assert data["suggestions"][2]["query"] == "query A"
        assert data["suggestions"][2]["search_count"] == 1

        app.dependency_overrides.pop(get_search_history_use_case, None)


class TestDeleteSearchHistory:
    """Tests for DELETE /api/v1/search/history/{history_id}."""

    def test_delete_history_entry(self, client_with_db: TestClient, test_db):
        """Test deleting a search history entry."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        # Create channel and add search history
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )

        search_repo = SearchHistoryRepository(test_db)
        history = search_repo.add_or_update(channel, "to delete")

        # Delete the entry
        response = client_with_db.delete(
            f"/api/v1/search/history/{history.id}",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 204

        # Verify it's deleted
        list_response = client_with_db.get(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )
        assert list_response.json()["total"] == 0

        app.dependency_overrides.pop(get_search_history_use_case, None)

    def test_delete_history_not_found(self, client_with_db: TestClient, test_db):
        """Test deleting non-existent history entry."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        response = client_with_db.delete(
            "/api/v1/search/history/99999",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_search_history_use_case, None)


class TestClearSearchHistory:
    """Tests for DELETE /api/v1/search/history."""

    def test_clear_all_history(self, client_with_db: TestClient, test_db):
        """Test clearing all search history."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: use_case

        # Create channel and add search history
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )

        search_repo = SearchHistoryRepository(test_db)
        search_repo.add_or_update(channel, "query 1")
        search_repo.add_or_update(channel, "query 2")
        search_repo.add_or_update(channel, "query 3")

        # Clear all history
        response = client_with_db.delete(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 204

        # Verify all cleared
        list_response = client_with_db.get(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )
        assert list_response.json()["total"] == 0

        app.dependency_overrides.pop(get_search_history_use_case, None)


class TestSearchHistoryIntegration:
    """Integration tests for search history with chat."""

    def test_chat_saves_to_search_history(self, client_with_db: TestClient, test_db):
        """Test that chat queries are saved to search history."""
        from src.application.use_cases.chat import ChatUseCase
        from src.infrastructure.di.container import (
            create_channel_repository_port,
            create_chat_history_repository_port,
            create_chat_session_repository_port,
            create_search_history_repository_port,
        )

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        # Search history use case (for reading back)
        search_use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: search_use_case

        # Chat use case (shares same DB so search history is visible)
        mock_pq = MagicMock()
        mock_pq.execute.return_value = MagicMock(
            response="Test response",
            sources=[],
            iterations=1,
            session_id=None,
            error=None,
        )
        mock_cache = MagicMock()
        mock_cache.get_chat_response.return_value = None
        mock_summaries = MagicMock()
        mock_summaries.build_context_string.return_value = ""

        chat_use_case = ChatUseCase(
            channel_port=mock_port,
            channel_repo=create_channel_repository_port(test_db),
            chat_history_repo=create_chat_history_repository_port(test_db),
            session_repo=create_chat_session_repository_port(test_db),
            search_history_repo=create_search_history_repository_port(test_db),
            cache=mock_cache,
            summaries_use_case=mock_summaries,
            process_query_factory=lambda: mock_pq,
        )
        app.dependency_overrides[get_chat_use_case] = lambda: chat_use_case

        # Send a chat message
        client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/chat",
            json={"query": "What is the meaning of life?"},
        )

        # Check search history
        response = client_with_db.get(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        data = response.json()
        assert data["total"] == 1
        assert data["history"][0]["query"] == "What is the meaning of life?"
        assert data["history"][0]["search_count"] == 1

        app.dependency_overrides.pop(get_search_history_use_case, None)
        app.dependency_overrides.pop(get_chat_use_case, None)

    def test_repeated_query_increments_count(self, client_with_db: TestClient, test_db):
        """Test that repeated queries increment search count."""
        from src.application.use_cases.chat import ChatUseCase
        from src.infrastructure.di.container import (
            create_channel_repository_port,
            create_chat_history_repository_port,
            create_chat_session_repository_port,
            create_search_history_repository_port,
        )

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        # Search history use case (for reading back)
        search_use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_search_history_use_case] = lambda: search_use_case

        # Chat use case (shares same DB so search history is visible)
        mock_pq = MagicMock()
        mock_pq.execute.return_value = MagicMock(
            response="Test response",
            sources=[],
            iterations=1,
            session_id=None,
            error=None,
        )
        mock_cache = MagicMock()
        mock_cache.get_chat_response.return_value = None
        mock_summaries = MagicMock()
        mock_summaries.build_context_string.return_value = ""

        chat_use_case = ChatUseCase(
            channel_port=mock_port,
            channel_repo=create_channel_repository_port(test_db),
            chat_history_repo=create_chat_history_repository_port(test_db),
            session_repo=create_chat_session_repository_port(test_db),
            search_history_repo=create_search_history_repository_port(test_db),
            cache=mock_cache,
            summaries_use_case=mock_summaries,
            process_query_factory=lambda: mock_pq,
        )
        app.dependency_overrides[get_chat_use_case] = lambda: chat_use_case

        # Send the same query multiple times
        for _ in range(3):
            client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/chat",
                json={"query": "repeated question"},
            )

        # Check search history
        response = client_with_db.get(
            "/api/v1/search/history",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        data = response.json()
        assert data["total"] == 1
        assert data["history"][0]["query"] == "repeated question"
        assert data["history"][0]["search_count"] == 3

        app.dependency_overrides.pop(get_search_history_use_case, None)
        app.dependency_overrides.pop(get_chat_use_case, None)
