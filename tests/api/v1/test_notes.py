# -*- coding: utf-8 -*-
"""Tests for Notes API."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.api.v1.notes import get_note_crud_use_case
from src.application.ports.channel import ChannelDTO


def _make_use_case(test_db, channel_port=None):
    """Create a NoteCrudUseCase with real DB repos and mocked external port."""
    from src.application.use_cases.note_crud import NoteCrudUseCase
    from src.infrastructure.di.container import (
        create_channel_repository_port,
        create_note_repository_port,
        create_trash_repository_port,
    )
    return NoteCrudUseCase(
        channel_port=channel_port or MagicMock(),
        channel_repo=create_channel_repository_port(test_db),
        note_repo=create_note_repository_port(test_db),
        trash_repo=create_trash_repository_port(test_db),
    )


class TestCreateNote:
    """Tests for POST /api/v1/notes."""

    def test_create_note_success(self, client_with_db: TestClient, test_db):
        """Test successful note creation."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={
                "title": "My First Note",
                "content": "This is the content of my note.",
                "sources": [],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My First Note"
        assert data["content"] == "This is the content of my note."
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_create_note_with_sources(self, client_with_db: TestClient, test_db):
        """Test creating note with AI sources."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={
                "title": "AI Generated Note",
                "content": "Summary from AI",
                "sources": [
                    {"source": "document.pdf", "content": "Relevant content"},
                ],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source"] == "document.pdf"

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_create_note_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test creating note in non-existent channel."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = None

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/not-exists"},
            json={
                "title": "Test Note",
                "content": "Test content",
            },
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_create_note_empty_title(self, client_with_db: TestClient, test_db):
        """Test creating note with empty title fails."""
        response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={
                "title": "",
                "content": "Test content",
            },
        )

        assert response.status_code == 422  # Validation error


class TestListNotes:
    """Tests for GET /api/v1/notes."""

    def test_list_notes_empty(self, client_with_db: TestClient, test_db):
        """Test listing notes when empty."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        response = client_with_db.get(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == []
        assert data["total"] == 0

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_list_notes_with_data(self, client_with_db: TestClient, test_db):
        """Test listing notes after creating some."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create notes
        for i in range(3):
            client_with_db.post(
                "/api/v1/notes",
                params={"channel_id": "fileSearchStores/test-store"},
                json={"title": f"Note {i}", "content": f"Content {i}"},
            )

        # List notes
        response = client_with_db.get(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["notes"]) == 3

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_list_notes_pagination(self, client_with_db: TestClient, test_db):
        """Test listing notes with pagination."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create 5 notes
        for i in range(5):
            client_with_db.post(
                "/api/v1/notes",
                params={"channel_id": "fileSearchStores/test-store"},
                json={"title": f"Note {i}", "content": f"Content {i}"},
            )

        # Get first page
        response = client_with_db.get(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store", "limit": 2, "offset": 0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["notes"]) == 2

        # Get second page
        response = client_with_db.get(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store", "limit": 2, "offset": 2},
        )

        data = response.json()
        assert len(data["notes"]) == 2

        app.dependency_overrides.pop(get_note_crud_use_case, None)


class TestGetNote:
    """Tests for GET /api/v1/notes/{note_id}."""

    def test_get_note_success(self, client_with_db: TestClient, test_db):
        """Test getting a specific note."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create a note
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "My Note", "content": "My content"},
        )
        note_id = create_response.json()["id"]

        # Get the note
        response = client_with_db.get(
            f"/api/v1/notes/{note_id}",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == note_id
        assert data["title"] == "My Note"
        assert data["content"] == "My content"

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_get_note_not_found(self, client_with_db: TestClient, test_db):
        """Test getting non-existent note."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        response = client_with_db.get(
            "/api/v1/notes/99999",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_note_crud_use_case, None)


class TestUpdateNote:
    """Tests for PUT /api/v1/notes/{note_id}."""

    def test_update_note_title(self, client_with_db: TestClient, test_db):
        """Test updating note title."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create a note
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "Original Title", "content": "Content"},
        )
        note_id = create_response.json()["id"]

        # Update title
        response = client_with_db.put(
            f"/api/v1/notes/{note_id}",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["content"] == "Content"  # Content unchanged

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_update_note_content(self, client_with_db: TestClient, test_db):
        """Test updating note content."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create a note
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "Title", "content": "Original Content"},
        )
        note_id = create_response.json()["id"]

        # Update content
        response = client_with_db.put(
            f"/api/v1/notes/{note_id}",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"content": "Updated Content"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Title"  # Title unchanged
        assert data["content"] == "Updated Content"

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_update_note_both_fields(self, client_with_db: TestClient, test_db):
        """Test updating both title and content."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create a note
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "Old Title", "content": "Old Content"},
        )
        note_id = create_response.json()["id"]

        # Update both
        response = client_with_db.put(
            f"/api/v1/notes/{note_id}",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "New Title", "content": "New Content"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Title"
        assert data["content"] == "New Content"

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_update_note_no_fields_fails(self, client_with_db: TestClient, test_db):
        """Test update with no fields fails."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create a note
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "Title", "content": "Content"},
        )
        note_id = create_response.json()["id"]

        # Update with no fields
        response = client_with_db.put(
            f"/api/v1/notes/{note_id}",
            params={"channel_id": "fileSearchStores/test-store"},
            json={},
        )

        assert response.status_code == 400

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_update_note_not_found(self, client_with_db: TestClient, test_db):
        """Test updating non-existent note."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        response = client_with_db.put(
            "/api/v1/notes/99999",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "New Title"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_note_crud_use_case, None)


class TestDeleteNote:
    """Tests for DELETE /api/v1/notes/{note_id}."""

    def test_delete_note_success(self, client_with_db: TestClient, test_db):
        """Test deleting a note."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        # Create a note
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={"title": "To Delete", "content": "Will be deleted"},
        )
        note_id = create_response.json()["id"]

        # Delete the note
        response = client_with_db.delete(
            f"/api/v1/notes/{note_id}",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 204

        # Verify it's deleted
        get_response = client_with_db.get(
            f"/api/v1/notes/{note_id}",
            params={"channel_id": "fileSearchStores/test-store"},
        )
        assert get_response.status_code == 404

        app.dependency_overrides.pop(get_note_crud_use_case, None)

    def test_delete_note_not_found(self, client_with_db: TestClient, test_db):
        """Test deleting non-existent note."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_port)
        app.dependency_overrides[get_note_crud_use_case] = lambda: use_case

        response = client_with_db.delete(
            "/api/v1/notes/99999",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_note_crud_use_case, None)
