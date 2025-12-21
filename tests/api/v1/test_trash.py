# -*- coding: utf-8 -*-
"""Tests for Trash API."""

from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models.db_models import ChannelMetadata, NoteDB
from src.services.gemini import get_gemini_service


class TestListTrash:
    """Tests for GET /api/v1/trash."""

    def test_list_trash_empty(self, client_with_db: TestClient, test_db):
        """Test listing trash when empty."""
        response = client_with_db.get("/api/v1/trash")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_trash_with_deleted_channel(self, client_with_db: TestClient, test_db):
        """Test listing trash with soft-deleted channel."""
        # Create a soft-deleted channel
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/deleted-channel",
            name="Deleted Channel",
            description="A deleted channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()

        response = client_with_db.get("/api/v1/trash")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["type"] == "channel"
        assert data["items"][0]["name"] == "Deleted Channel"

    def test_list_trash_with_deleted_note(self, client_with_db: TestClient, test_db):
        """Test listing trash with soft-deleted note."""
        # Create a channel first
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-channel",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        # Create a soft-deleted note
        note = NoteDB(
            channel_id=channel.id,
            title="Deleted Note",
            content="Content of deleted note",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(note)
        test_db.commit()

        response = client_with_db.get("/api/v1/trash")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["type"] == "note"
        assert data["items"][0]["name"] == "Deleted Note"


class TestRestoreItem:
    """Tests for POST /api/v1/trash/{type}/{id}/restore."""

    def test_restore_channel_success(self, client_with_db: TestClient, test_db):
        """Test restoring a soft-deleted channel."""
        # Create a soft-deleted channel
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/deleted-channel",
            name="Deleted Channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()
        test_db.refresh(channel)

        response = client_with_db.post(f"/api/v1/trash/channel/{channel.id}/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "channel"
        assert data["id"] == channel.id
        assert "restored" in data["message"].lower()

        # Verify channel is restored
        test_db.refresh(channel)
        assert channel.deleted_at is None

    def test_restore_note_success(self, client_with_db: TestClient, test_db):
        """Test restoring a soft-deleted note."""
        # Create a channel
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-channel",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        # Create a soft-deleted note
        note = NoteDB(
            channel_id=channel.id,
            title="Deleted Note",
            content="Content",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(note)
        test_db.commit()
        test_db.refresh(note)

        response = client_with_db.post(f"/api/v1/trash/note/{note.id}/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "note"
        assert data["id"] == note.id

        # Verify note is restored
        test_db.refresh(note)
        assert note.deleted_at is None

    def test_restore_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test restoring non-existent trashed channel."""
        response = client_with_db.post("/api/v1/trash/channel/99999/restore")
        assert response.status_code == 404

    def test_restore_note_not_found(self, client_with_db: TestClient, test_db):
        """Test restoring non-existent trashed note."""
        response = client_with_db.post("/api/v1/trash/note/99999/restore")
        assert response.status_code == 404


class TestDeleteItemPermanently:
    """Tests for DELETE /api/v1/trash/{type}/{id}."""

    def test_permanent_delete_channel(self, client_with_db: TestClient, test_db):
        """Test permanently deleting a trashed channel."""
        mock_gemini = MagicMock()
        mock_gemini.delete_store.return_value = True

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create a soft-deleted channel
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/deleted-channel",
            name="Deleted Channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()
        test_db.refresh(channel)
        channel_id = channel.id

        response = client_with_db.delete(f"/api/v1/trash/channel/{channel_id}")

        assert response.status_code == 204

        # Verify channel is permanently deleted
        deleted_channel = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()
        assert deleted_channel is None

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_permanent_delete_note(self, client_with_db: TestClient, test_db):
        """Test permanently deleting a trashed note."""
        mock_gemini = MagicMock()
        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create a channel
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-channel",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        # Create a soft-deleted note
        note = NoteDB(
            channel_id=channel.id,
            title="Deleted Note",
            content="Content",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(note)
        test_db.commit()
        test_db.refresh(note)
        note_id = note.id

        response = client_with_db.delete(f"/api/v1/trash/note/{note_id}")

        assert response.status_code == 204

        # Verify note is permanently deleted
        deleted_note = test_db.query(NoteDB).filter(NoteDB.id == note_id).first()
        assert deleted_note is None

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_permanent_delete_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test permanently deleting non-existent trashed channel."""
        mock_gemini = MagicMock()
        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.delete("/api/v1/trash/channel/99999")
        assert response.status_code == 404

        app.dependency_overrides.pop(get_gemini_service, None)


class TestEmptyTrash:
    """Tests for DELETE /api/v1/trash."""

    def test_empty_trash_requires_confirmation(self, client_with_db: TestClient, test_db):
        """Test that empty trash requires confirmation."""
        mock_gemini = MagicMock()
        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.delete("/api/v1/trash")
        assert response.status_code == 400

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_empty_trash_success(self, client_with_db: TestClient, test_db):
        """Test emptying trash successfully."""
        mock_gemini = MagicMock()
        mock_gemini.delete_store.return_value = True

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create soft-deleted channel and note
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/deleted-channel",
            name="Deleted Channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()

        note = NoteDB(
            channel_id=channel.id,
            title="Deleted Note",
            content="Content",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(note)
        test_db.commit()

        response = client_with_db.delete("/api/v1/trash", params={"confirm": True})

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_channels"] >= 1
        assert "message" in data

        app.dependency_overrides.pop(get_gemini_service, None)


class TestTrashStats:
    """Tests for GET /api/v1/trash/stats."""

    def test_trash_stats_empty(self, client_with_db: TestClient, test_db):
        """Test trash stats when empty."""
        response = client_with_db.get("/api/v1/trash/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["trashed_channels"] == 0
        assert data["trashed_notes"] == 0
        assert data["total"] == 0

    def test_trash_stats_with_items(self, client_with_db: TestClient, test_db):
        """Test trash stats with items."""
        # Create soft-deleted channel
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/deleted-channel",
            name="Deleted Channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()

        # Create channel for notes
        active_channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/active-channel",
            name="Active Channel",
        )
        test_db.add(active_channel)
        test_db.commit()

        # Create soft-deleted notes
        for i in range(3):
            note = NoteDB(
                channel_id=active_channel.id,
                title=f"Deleted Note {i}",
                content="Content",
                deleted_at=datetime.now(UTC),
            )
            test_db.add(note)
        test_db.commit()

        response = client_with_db.get("/api/v1/trash/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["trashed_channels"] == 1
        assert data["trashed_notes"] == 3
        assert data["total"] == 4


class TestSoftDeleteIntegration:
    """Integration tests for soft delete behavior."""

    def test_deleted_channel_not_in_list(self, client_with_db: TestClient, test_db):
        """Test that soft-deleted channels are not shown in channel list."""
        mock_gemini = MagicMock()
        mock_gemini.list_stores.return_value = [
            {"name": "fileSearchStores/active", "display_name": "Active"},
            {"name": "fileSearchStores/deleted", "display_name": "Deleted"},
        ]

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create a soft-deleted channel in DB
        deleted_channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/deleted",
            name="Deleted",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(deleted_channel)
        test_db.commit()

        response = client_with_db.get("/api/v1/channels")

        assert response.status_code == 200
        data = response.json()
        # Only active channel should be in the list
        channel_ids = [c["id"] for c in data["channels"]]
        assert "fileSearchStores/deleted" not in channel_ids

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_deleted_note_not_in_list(self, client_with_db: TestClient, test_db):
        """Test that soft-deleted notes are not shown in note list."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test",
            "display_name": "Test",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        # Create channel
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test",
            name="Test",
        )
        test_db.add(channel)
        test_db.commit()

        # Create active note
        active_note = NoteDB(
            channel_id=channel.id,
            title="Active Note",
            content="Content",
        )
        test_db.add(active_note)

        # Create deleted note
        deleted_note = NoteDB(
            channel_id=channel.id,
            title="Deleted Note",
            content="Content",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(deleted_note)
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["notes"][0]["title"] == "Active Note"

        app.dependency_overrides.pop(get_gemini_service, None)
