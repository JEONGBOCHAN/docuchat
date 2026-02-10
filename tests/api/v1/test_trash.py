# -*- coding: utf-8 -*-
"""Tests for Trash API."""

from datetime import datetime, UTC
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.modules.workspace.infrastructure.persistence.models import ChannelMetadata, NoteDB
from src.modules.workspace.presentation.api.trash import _get_use_case
from src.modules.workspace.presentation.api.channels import get_channel_crud_use_case_factory
from src.modules.workspace.presentation.api.notes import get_note_crud_use_case_factory
from src.shared.kernel.presentation.dependencies.admin_auth import require_admin_key
from src.modules.workspace.application.use_cases.channel_crud import ChannelCrudUseCase
from src.shared.kernel.contracts.ports.channel import ChannelDTO
from src.modules.workspace.application.use_cases.trash_management import TrashManagementUseCase


@pytest.fixture(autouse=True)
def bypass_admin_key():
    """Bypass admin key check in tests."""
    app.dependency_overrides[require_admin_key] = lambda: "test-key"
    yield
    app.dependency_overrides.pop(require_admin_key, None)


def _build_use_case_with_mock_channel_port(db, mock_channel_port):
    """Build a real TrashManagementUseCase with a mocked channel_port."""
    from src.modules.workspace.public import create_trash_repository_port
    return TrashManagementUseCase(
        trash_repo=create_trash_repository_port(db),
        channel_port=mock_channel_port,
    )


class TestListTrash:
    """Tests for GET /api/v1/trash."""

    def test_list_trash_empty(self, client_with_db: TestClient, test_db):
        response = client_with_db.get("/api/v1/trash")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_trash_with_deleted_channel(self, client_with_db: TestClient, test_db):
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
        assert data["items"][0]["type"] == "channel"
        assert data["items"][0]["name"] == "Deleted Channel"

    def test_list_trash_with_deleted_note(self, client_with_db: TestClient, test_db):
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-channel",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

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
        assert data["items"][0]["type"] == "note"
        assert data["items"][0]["name"] == "Deleted Note"


class TestRestoreItem:
    """Tests for POST /api/v1/trash/{type}/{id}/restore."""

    def test_restore_channel_success(self, client_with_db: TestClient, test_db):
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

        test_db.refresh(channel)
        assert channel.deleted_at is None

    def test_restore_note_success(self, client_with_db: TestClient, test_db):
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-channel",
            name="Test Channel",
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
        test_db.refresh(note)

        response = client_with_db.post(f"/api/v1/trash/note/{note.id}/restore")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "note"
        assert data["id"] == note.id

        test_db.refresh(note)
        assert note.deleted_at is None

    def test_restore_channel_not_found(self, client_with_db: TestClient, test_db):
        response = client_with_db.post("/api/v1/trash/channel/99999/restore")
        assert response.status_code == 404

    def test_restore_note_not_found(self, client_with_db: TestClient, test_db):
        response = client_with_db.post("/api/v1/trash/note/99999/restore")
        assert response.status_code == 404


class TestDeleteItemPermanently:
    """Tests for DELETE /api/v1/trash/{type}/{id}."""

    def test_permanent_delete_channel(self, client_with_db: TestClient, test_db):
        mock_channel_port = MagicMock()
        mock_channel_port.delete_channel.return_value = True

        app.dependency_overrides[_get_use_case] = lambda: _build_use_case_with_mock_channel_port(
            test_db, mock_channel_port
        )

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

        deleted_channel = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()
        assert deleted_channel is None

        app.dependency_overrides.pop(_get_use_case, None)

    def test_permanent_delete_note(self, client_with_db: TestClient, test_db):
        mock_channel_port = MagicMock()
        app.dependency_overrides[_get_use_case] = lambda: _build_use_case_with_mock_channel_port(
            test_db, mock_channel_port
        )

        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-channel",
            name="Test Channel",
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
        test_db.refresh(note)
        note_id = note.id

        response = client_with_db.delete(f"/api/v1/trash/note/{note_id}")
        assert response.status_code == 204

        deleted_note = test_db.query(NoteDB).filter(NoteDB.id == note_id).first()
        assert deleted_note is None

        app.dependency_overrides.pop(_get_use_case, None)

    def test_permanent_delete_channel_gemini_failure(self, client_with_db: TestClient, test_db):
        mock_channel_port = MagicMock()
        mock_channel_port.delete_channel.return_value = False

        app.dependency_overrides[_get_use_case] = lambda: _build_use_case_with_mock_channel_port(
            test_db, mock_channel_port
        )

        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/fail-channel",
            name="Fail Channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()
        test_db.refresh(channel)
        channel_id = channel.id

        response = client_with_db.delete(f"/api/v1/trash/channel/{channel_id}")
        assert response.status_code == 502
        assert "external storage" in response.json()["detail"].lower()

        still_exists = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()
        assert still_exists is not None
        assert still_exists.deleted_at is not None

        app.dependency_overrides.pop(_get_use_case, None)

    def test_permanent_delete_channel_not_found(self, client_with_db: TestClient, test_db):
        mock_channel_port = MagicMock()
        app.dependency_overrides[_get_use_case] = lambda: _build_use_case_with_mock_channel_port(
            test_db, mock_channel_port
        )

        response = client_with_db.delete("/api/v1/trash/channel/99999")
        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)


class TestEmptyTrash:
    """Tests for DELETE /api/v1/trash."""

    def test_empty_trash_requires_confirmation(self, client_with_db: TestClient, test_db):
        mock_channel_port = MagicMock()
        app.dependency_overrides[_get_use_case] = lambda: _build_use_case_with_mock_channel_port(
            test_db, mock_channel_port
        )

        response = client_with_db.delete("/api/v1/trash")
        assert response.status_code == 400

        app.dependency_overrides.pop(_get_use_case, None)

    def test_empty_trash_success(self, client_with_db: TestClient, test_db):
        mock_channel_port = MagicMock()
        mock_channel_port.delete_channel.return_value = True

        app.dependency_overrides[_get_use_case] = lambda: _build_use_case_with_mock_channel_port(
            test_db, mock_channel_port
        )

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
        assert data["failed_channels"] == 0

        app.dependency_overrides.pop(_get_use_case, None)

    def test_empty_trash_partial_gemini_failure(self, client_with_db: TestClient, test_db):
        mock_channel_port = MagicMock()
        mock_channel_port.delete_channel.side_effect = [True, False]

        app.dependency_overrides[_get_use_case] = lambda: _build_use_case_with_mock_channel_port(
            test_db, mock_channel_port
        )

        ch1 = ChannelMetadata(
            gemini_store_id="fileSearchStores/ch-ok",
            name="OK Channel",
            deleted_at=datetime.now(UTC),
        )
        ch2 = ChannelMetadata(
            gemini_store_id="fileSearchStores/ch-fail",
            name="Fail Channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add_all([ch1, ch2])
        test_db.commit()
        test_db.refresh(ch1)
        test_db.refresh(ch2)
        ch1_id, ch2_id = ch1.id, ch2.id

        note = NoteDB(
            channel_id=ch2.id,
            title="Deleted Note",
            content="Content",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(note)
        test_db.commit()

        response = client_with_db.delete("/api/v1/trash", params={"confirm": True})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_channels"] == 1
        assert data["failed_channels"] == 1
        assert data["deleted_notes"] == 1

        assert test_db.query(ChannelMetadata).filter(ChannelMetadata.id == ch1_id).first() is None
        ch2_still = test_db.query(ChannelMetadata).filter(ChannelMetadata.id == ch2_id).first()
        assert ch2_still is not None
        assert ch2_still.deleted_at is not None

        app.dependency_overrides.pop(_get_use_case, None)


class TestTrashStats:
    """Tests for GET /api/v1/trash/stats."""

    def test_trash_stats_empty(self, client_with_db: TestClient, test_db):
        response = client_with_db.get("/api/v1/trash/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["trashed_channels"] == 0
        assert data["trashed_notes"] == 0
        assert data["total"] == 0

    def test_trash_stats_with_items(self, client_with_db: TestClient, test_db):
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/deleted-channel",
            name="Deleted Channel",
            deleted_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()

        active_channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/active-channel",
            name="Active Channel",
        )
        test_db.add(active_channel)
        test_db.commit()

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
        mock_channel_port = MagicMock()
        mock_channel_port.list_channels.return_value = [
            ChannelDTO(name="fileSearchStores/active", display_name="Active"),
            ChannelDTO(name="fileSearchStores/deleted", display_name="Deleted"),
        ]

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        from src.modules.workspace.public import (
            create_channel_repository_port,
            create_favorite_repository_port,
        )
        mock_cache = MagicMock()
        mock_cache.get_store_list.return_value = None
        mock_cache.get_channel_info.return_value = None
        use_case = ChannelCrudUseCase(
            channel_port=mock_channel_port,
            document_port=mock_document_port,
            channel_repo=create_channel_repository_port(test_db),
            fav_repo=create_favorite_repository_port(test_db),
            cache=mock_cache,
        )
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

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
        channel_ids = [c["id"] for c in data["channels"]]
        assert "fileSearchStores/deleted" not in channel_ids

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_deleted_note_not_in_list(self, client_with_db: TestClient, test_db):
        from src.modules.workspace.application.use_cases.note_crud import NoteCrudUseCase
        from src.modules.workspace.public import (
            create_channel_repository_port,
            create_note_repository_port,
            create_trash_repository_port,
        )

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test",
            display_name="Test",
        )

        note_use_case = NoteCrudUseCase(
            channel_port=mock_channel_port,
            channel_repo=create_channel_repository_port(test_db),
            note_repo=create_note_repository_port(test_db),
            trash_repo=create_trash_repository_port(test_db),
        )
        app.dependency_overrides[get_note_crud_use_case_factory] = lambda: lambda: note_use_case

        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test",
            name="Test",
        )
        test_db.add(channel)
        test_db.commit()

        active_note = NoteDB(
            channel_id=channel.id,
            title="Active Note",
            content="Content",
        )
        test_db.add(active_note)

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

        app.dependency_overrides.pop(get_note_crud_use_case_factory, None)
