# -*- coding: utf-8 -*-
"""Tests for Favorites API."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.modules.workspace.presentation.api.favorites import get_favorite_crud_use_case_factory
from src.application.ports.channel import ChannelDTO
from src.infrastructure.persistence.db_models import NoteDB


def _make_use_case(test_db, channel_port=None):
    """Create a FavoriteCrudUseCase with real DB repos and mocked external port."""
    from src.application.use_cases.favorite_crud import FavoriteCrudUseCase
    from src.infrastructure.di.container import (
        create_favorite_repository_port,
        create_note_repository_port,
    )
    return FavoriteCrudUseCase(
        channel_port=channel_port or MagicMock(),
        fav_repo=create_favorite_repository_port(test_db),
        note_repo=create_note_repository_port(test_db),
    )


class TestAddFavorite:
    """Tests for POST /api/v1/favorites."""

    def test_add_channel_to_favorites(self, client_with_db: TestClient, test_db):
        """Test adding a channel to favorites."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "channel"
        assert data["target_id"] == "fileSearchStores/store-123"
        assert data["display_order"] == 1
        assert "id" in data
        assert "created_at" in data

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_add_note_to_favorites(self, client_with_db: TestClient, test_db):
        """Test adding a note to favorites."""
        # Create a note first
        note = NoteDB(
            channel_id="fileSearchStores/store-123",
            title="Test Note",
            content="Test content",
        )
        test_db.add(note)
        test_db.commit()
        test_db.refresh(note)

        mock_channel_port = MagicMock()
        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "note",
                "target_id": str(note.id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "note"
        assert data["target_id"] == str(note.id)

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_add_document_to_favorites(self, client_with_db: TestClient, test_db):
        """Test adding a document to favorites."""
        mock_channel_port = MagicMock()
        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "document",
                "target_id": "files/doc-123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "document"
        assert data["target_id"] == "files/doc-123"

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_add_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test adding non-existent channel returns 404."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/not-exists",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_add_note_not_found(self, client_with_db: TestClient, test_db):
        """Test adding non-existent note returns 404."""
        mock_channel_port = MagicMock()
        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "note",
                "target_id": "99999",
            },
        )

        assert response.status_code == 404
        assert "Note not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_add_invalid_document_id(self, client_with_db: TestClient, test_db):
        """Test adding document with empty ID returns 400."""
        mock_channel_port = MagicMock()
        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "document",
                "target_id": "",
            },
        )

        assert response.status_code == 400
        assert "Document ID" in response.json()["detail"]

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_add_duplicate_favorite_returns_existing(self, client_with_db: TestClient, test_db):
        """Test adding duplicate favorite returns existing one."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add first time
        response1 = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )
        assert response1.status_code == 201
        first_id = response1.json()["id"]

        # Add second time
        response2 = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )
        assert response2.status_code == 201
        assert response2.json()["id"] == first_id  # Same ID

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)


class TestRemoveFavorite:
    """Tests for DELETE /api/v1/favorites."""

    def test_remove_favorite(self, client_with_db: TestClient, test_db):
        """Test removing a favorite."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add favorite first
        client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )

        # Remove it
        response = client_with_db.delete(
            "/api/v1/favorites",
            params={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )

        assert response.status_code == 204

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_remove_nonexistent_favorite(self, client_with_db: TestClient, test_db):
        """Test removing non-existent favorite returns 404."""
        response = client_with_db.delete(
            "/api/v1/favorites",
            params={
                "target_type": "channel",
                "target_id": "fileSearchStores/not-exists",
            },
        )

        assert response.status_code == 404


class TestListFavorites:
    """Tests for GET /api/v1/favorites."""

    def test_list_favorites_empty(self, client_with_db: TestClient, test_db):
        """Test listing favorites when empty."""
        response = client_with_db.get("/api/v1/favorites")

        assert response.status_code == 200
        data = response.json()
        assert data["favorites"] == []
        assert data["total"] == 0

    def test_list_favorites(self, client_with_db: TestClient, test_db):
        """Test listing favorites."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add a favorite
        client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )

        response = client_with_db.get("/api/v1/favorites")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["favorites"]) == 1
        assert data["favorites"][0]["target_type"] == "channel"

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_list_favorites_filter_by_type(self, client_with_db: TestClient, test_db):
        """Test listing favorites filtered by type."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add channel favorite
        client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )

        # Add document favorite
        client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "document",
                "target_id": "files/doc-123",
            },
        )

        # Filter by channel
        response = client_with_db.get("/api/v1/favorites?target_type=channel")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["favorites"][0]["target_type"] == "channel"

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)


class TestCheckFavorite:
    """Tests for GET /api/v1/favorites/check."""

    def test_check_favorited(self, client_with_db: TestClient, test_db):
        """Test checking if item is favorited - true."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add favorite
        client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )

        # Check
        response = client_with_db.get(
            "/api/v1/favorites/check",
            params={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-123",
            },
        )

        assert response.status_code == 200
        assert response.json()["is_favorited"] is True

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_check_not_favorited(self, client_with_db: TestClient, test_db):
        """Test checking if item is favorited - false."""
        response = client_with_db.get(
            "/api/v1/favorites/check",
            params={
                "target_type": "channel",
                "target_id": "fileSearchStores/not-favorited",
            },
        )

        assert response.status_code == 200
        assert response.json()["is_favorited"] is False


class TestReorderFavorites:
    """Tests for PUT /api/v1/favorites/reorder."""

    def test_reorder_favorites(self, client_with_db: TestClient, test_db):
        """Test reordering favorites."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add two favorites
        r1 = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-1",
            },
        )
        r2 = client_with_db.post(
            "/api/v1/favorites",
            json={
                "target_type": "channel",
                "target_id": "fileSearchStores/store-2",
            },
        )

        id1 = r1.json()["id"]
        id2 = r2.json()["id"]

        # Reorder (swap)
        response = client_with_db.put(
            "/api/v1/favorites/reorder",
            json={"favorite_ids": [id2, id1]},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Favorites reordered successfully"

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)


class TestConvenienceEndpoints:
    """Tests for convenience endpoints."""

    def test_favorite_channel(self, client_with_db: TestClient, test_db):
        """Test POST /favorites/channels/{id}."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post("/api/v1/favorites/channels/fileSearchStores/store-123")

        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "channel"
        assert data["target_id"] == "fileSearchStores/store-123"

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_unfavorite_channel(self, client_with_db: TestClient, test_db):
        """Test DELETE /favorites/channels/{id}."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add first
        client_with_db.post("/api/v1/favorites/channels/fileSearchStores/store-123")

        # Remove
        response = client_with_db.delete("/api/v1/favorites/channels/fileSearchStores/store-123")

        assert response.status_code == 204

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_favorite_note(self, client_with_db: TestClient, test_db):
        """Test POST /favorites/notes/{id}."""
        # Create note
        note = NoteDB(
            channel_id="fileSearchStores/store-123",
            title="Test Note",
            content="Test content",
        )
        test_db.add(note)
        test_db.commit()
        test_db.refresh(note)

        mock_channel_port = MagicMock()
        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(f"/api/v1/favorites/notes/{note.id}")

        assert response.status_code == 201
        data = response.json()
        assert data["target_type"] == "note"
        assert data["target_id"] == str(note.id)

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)

    def test_unfavorite_note(self, client_with_db: TestClient, test_db):
        """Test DELETE /favorites/notes/{id}."""
        # Create note
        note = NoteDB(
            channel_id="fileSearchStores/store-123",
            title="Test Note",
            content="Test content",
        )
        test_db.add(note)
        test_db.commit()
        test_db.refresh(note)

        mock_channel_port = MagicMock()
        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: use_case

        # Add first
        client_with_db.post(f"/api/v1/favorites/notes/{note.id}")

        # Remove
        response = client_with_db.delete(f"/api/v1/favorites/notes/{note.id}")

        assert response.status_code == 204

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)


class TestChannelListWithFavorites:
    """Tests for channel list with favorite info."""

    def test_list_channels_with_favorites(self, client_with_db: TestClient, test_db):
        """Test that channel list includes is_favorited field."""
        from src.modules.workspace.presentation.api.channels import get_channel_crud_use_case_factory
        from src.application.use_cases.channel_crud import ChannelCrudUseCase
        from src.infrastructure.di.container import (
            create_channel_repository_port,
            create_favorite_repository_port,
        )

        mock_channel_port = MagicMock()
        mock_channel_port.list_channels.return_value = [
            ChannelDTO(name="fileSearchStores/store-1", display_name="Channel 1"),
            ChannelDTO(name="fileSearchStores/store-2", display_name="Channel 2"),
        ]
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-1",
            display_name="Channel 1",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        mock_cache = MagicMock()
        mock_cache.get_store_list.return_value = None
        mock_cache.get_channel_info.return_value = None
        channel_use_case = ChannelCrudUseCase(
            channel_port=mock_channel_port,
            document_port=mock_document_port,
            channel_repo=create_channel_repository_port(test_db),
            fav_repo=create_favorite_repository_port(test_db),
            cache=mock_cache,
        )

        fav_use_case = _make_use_case(test_db, channel_port=mock_channel_port)

        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: fav_use_case
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: channel_use_case

        # Favorite only channel 1
        client_with_db.post("/api/v1/favorites/channels/fileSearchStores/store-1")

        # List channels
        response = client_with_db.get("/api/v1/channels")

        assert response.status_code == 200
        data = response.json()

        # Favorited channel should be first (due to sorting)
        assert data["channels"][0]["id"] == "fileSearchStores/store-1"
        assert data["channels"][0]["is_favorited"] is True
        assert data["channels"][1]["is_favorited"] is False

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)
        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_get_channel_with_favorite_status(self, client_with_db: TestClient, test_db):
        """Test that get channel includes is_favorited field."""
        from src.modules.workspace.presentation.api.channels import get_channel_crud_use_case_factory
        from src.application.use_cases.channel_crud import ChannelCrudUseCase
        from src.infrastructure.di.container import (
            create_channel_repository_port,
            create_favorite_repository_port,
        )

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        mock_cache = MagicMock()
        mock_cache.get_store_list.return_value = None
        mock_cache.get_channel_info.return_value = None
        channel_use_case = ChannelCrudUseCase(
            channel_port=mock_channel_port,
            document_port=mock_document_port,
            channel_repo=create_channel_repository_port(test_db),
            fav_repo=create_favorite_repository_port(test_db),
            cache=mock_cache,
        )

        fav_use_case = _make_use_case(test_db, channel_port=mock_channel_port)

        app.dependency_overrides[get_favorite_crud_use_case_factory] = lambda: lambda: fav_use_case
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: channel_use_case

        # Not favorited
        response1 = client_with_db.get("/api/v1/channels/fileSearchStores/store-123")
        assert response1.status_code == 200
        assert response1.json()["is_favorited"] is False

        # Favorite it
        client_with_db.post("/api/v1/favorites/channels/fileSearchStores/store-123")

        # Now favorited
        response2 = client_with_db.get("/api/v1/channels/fileSearchStores/store-123")
        assert response2.status_code == 200
        assert response2.json()["is_favorited"] is True

        app.dependency_overrides.pop(get_favorite_crud_use_case_factory, None)
        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)
