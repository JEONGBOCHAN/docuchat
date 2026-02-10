# -*- coding: utf-8 -*-
"""Tests for Channel CRUD API."""

from unittest.mock import MagicMock
from datetime import datetime, UTC
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.modules.workspace.presentation.api.channels import get_channel_crud_use_case_factory
from src.modules.workspace.application.use_cases.channel_crud import ChannelCrudUseCase
from src.shared.kernel.contracts.ports.channel import ChannelDTO
from src.shared.kernel.contracts.ports.document import DocumentDTO
from src.core.database import get_db
from src.modules.workspace.infrastructure.persistence.models import ChannelMetadata


def _make_use_case(test_db, channel_port=None, document_port=None, cache=None):
    """Create a ChannelCrudUseCase with mocked external ports and real DB repos."""
    from src.modules.workspace.public import (
        create_channel_repository_port,
        create_favorite_repository_port,
    )
    if cache is None:
        cache = MagicMock()
        cache.get_store_list.return_value = None
        cache.get_channel_info.return_value = None
    return ChannelCrudUseCase(
        channel_port=channel_port or MagicMock(),
        document_port=document_port or MagicMock(),
        channel_repo=create_channel_repository_port(test_db),
        fav_repo=create_favorite_repository_port(test_db),
        cache=cache,
    )


class TestCreateChannel:
    """Tests for POST /api/v1/channels."""

    def test_create_channel_success(self, client_with_db: TestClient, test_db):
        """Test successful channel creation."""
        mock_channel_port = MagicMock()
        mock_channel_port.create_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store-123",
            display_name="Test Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels",
            json={"name": "Test Channel"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "fileSearchStores/test-store-123"
        assert data["name"] == "Test Channel"
        assert data["file_count"] == 0
        assert "created_at" in data

        # Cleanup
        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_create_channel_empty_name(self, client_with_db: TestClient, test_db):
        """Test channel creation with empty name fails."""
        use_case = _make_use_case(test_db)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels",
            json={"name": ""},
        )

        assert response.status_code == 422  # Validation error

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_create_channel_api_error(self, client_with_db: TestClient, test_db):
        """Test channel creation handles API errors."""
        mock_channel_port = MagicMock()
        mock_channel_port.create_channel.side_effect = Exception("API Error")

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.post(
            "/api/v1/channels",
            json={"name": "Test Channel"},
        )

        assert response.status_code == 500
        assert "Failed to create channel" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)


class TestListChannels:
    """Tests for GET /api/v1/channels."""

    def test_list_channels_success(self, client_with_db: TestClient, test_db):
        """Test listing channels."""
        mock_channel_port = MagicMock()
        mock_channel_port.list_channels.return_value = [
            ChannelDTO(name="fileSearchStores/store-1", display_name="Channel 1"),
            ChannelDTO(name="fileSearchStores/store-2", display_name="Channel 2"),
        ]

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        use_case = _make_use_case(
            test_db, channel_port=mock_channel_port, document_port=mock_document_port,
        )
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get("/api/v1/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["channels"]) == 2
        # Check both channels are present (order may vary based on sorting)
        channel_names = {c["name"] for c in data["channels"]}
        assert channel_names == {"Channel 1", "Channel 2"}

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_list_channels_empty(self, client_with_db: TestClient, test_db):
        """Test listing when no channels exist."""
        mock_channel_port = MagicMock()
        mock_channel_port.list_channels.return_value = []

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get("/api/v1/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["channels"] == []

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_list_channels_api_error(self, client_with_db: TestClient, test_db):
        """Test listing channels handles API errors."""
        mock_channel_port = MagicMock()
        mock_channel_port.list_channels.side_effect = Exception("API Error")

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get("/api/v1/channels")

        assert response.status_code == 500
        assert "Failed to list channels" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)


class TestGetChannel:
    """Tests for GET /api/v1/channels/{channel_id}."""

    def test_get_channel_success(self, client_with_db: TestClient, test_db):
        """Test getting a specific channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        use_case = _make_use_case(
            test_db, channel_port=mock_channel_port, document_port=mock_document_port,
        )
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get("/api/v1/channels/fileSearchStores/store-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "fileSearchStores/store-123"
        assert data["name"] == "My Channel"

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_get_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test getting non-existent channel returns 404."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get("/api/v1/channels/fileSearchStores/not-exists")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)


class TestDeleteChannel:
    """Tests for DELETE /api/v1/channels/{channel_id}."""

    def test_delete_channel_success(self, client_with_db: TestClient, test_db):
        """Test successful channel deletion (permanent delete)."""
        channel_id = "fileSearchStores/store-123"

        # Create channel metadata first
        channel = ChannelMetadata(
            gemini_store_id=channel_id,
            name="My Channel",
            created_at=datetime.now(UTC),
            last_accessed_at=datetime.now(UTC),
        )
        test_db.add(channel)
        test_db.commit()
        channel_db_id = channel.id

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=channel_id,
            display_name="My Channel",
        )
        mock_channel_port.delete_channel.return_value = True

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.delete(f"/api/v1/channels/{channel_id}")

        assert response.status_code == 204

        # Verify channel is permanently deleted from DB
        deleted_channel = test_db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_db_id
        ).first()
        assert deleted_channel is None

        # Verify channel port delete was called
        mock_channel_port.delete_channel.assert_called_once_with(channel_id, force=True)

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_delete_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test deleting non-existent channel returns 404."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.delete("/api/v1/channels/fileSearchStores/not-exists")

        assert response.status_code == 404

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_delete_channel_no_local_metadata(self, client_with_db: TestClient, test_db):
        """Test delete succeeds even when no local metadata exists.

        When a channel exists in Gemini but has no local metadata,
        the delete operation should still succeed (just delete from Gemini).
        """
        channel_id = "fileSearchStores/store-123"

        # Channel exists in Gemini but no local metadata
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=channel_id,
            display_name="My Channel",
        )
        mock_channel_port.delete_channel.return_value = True

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.delete(f"/api/v1/channels/{channel_id}")

        assert response.status_code == 204
        mock_channel_port.delete_channel.assert_called_once_with(channel_id, force=True)

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_delete_channel_gemini_error(self, client_with_db: TestClient, test_db):
        """Test delete returns 500 when Gemini deletion fails."""
        channel_id = "fileSearchStores/store-123"

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=channel_id,
            display_name="My Channel",
        )
        mock_channel_port.delete_channel.side_effect = Exception("Gemini API Error")

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.delete(f"/api/v1/channels/{channel_id}")

        assert response.status_code == 500
        assert "Failed to delete channel" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)


class TestUpdateChannel:
    """Tests for PUT /api/v1/channels/{channel_id}."""

    def test_update_channel_name_success(self, client_with_db: TestClient, test_db):
        """Test updating channel name."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="Old Name",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.put(
            "/api/v1/channels/fileSearchStores/store-123",
            json={"name": "New Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "fileSearchStores/store-123"
        assert data["name"] == "New Name"

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_update_channel_description_success(self, client_with_db: TestClient, test_db):
        """Test updating channel description."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="My Channel",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.put(
            "/api/v1/channels/fileSearchStores/store-123",
            json={"description": "New description"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "New description"

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_update_channel_both_fields(self, client_with_db: TestClient, test_db):
        """Test updating both name and description."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/store-123",
            display_name="Old Name",
        )

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.put(
            "/api/v1/channels/fileSearchStores/store-123",
            json={"name": "New Name", "description": "New description"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New description"

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_update_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test updating non-existent channel returns 404."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        use_case = _make_use_case(test_db, channel_port=mock_channel_port)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.put(
            "/api/v1/channels/fileSearchStores/not-exists",
            json={"name": "New Name"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_update_channel_empty_body(self, client_with_db: TestClient, test_db):
        """Test updating with no fields returns 400."""
        use_case = _make_use_case(test_db)
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.put(
            "/api/v1/channels/fileSearchStores/store-123",
            json={},
        )

        assert response.status_code == 400
        assert "At least one" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)


class TestAutoCreateMetadata:
    """Tests for CHA-118: auto-create metadata when local_meta is None."""

    def test_list_channels_auto_creates_metadata_when_none(
        self, client_with_db: TestClient, test_db
    ):
        """list_channels() should auto-create local metadata for channels without it.

        Before the fix, channels without local_meta would use datetime.now(UTC)
        on every request, showing the current time instead of a persisted one.
        """
        mock_channel_port = MagicMock()
        mock_channel_port.list_channels.return_value = [
            ChannelDTO(
                name="fileSearchStores/no-meta-store",
                display_name="No Meta Channel",
            ),
        ]

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        use_case = _make_use_case(
            test_db, channel_port=mock_channel_port, document_port=mock_document_port,
        )
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get("/api/v1/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        # Verify metadata was auto-created in the DB
        created_meta = (
            test_db.query(ChannelMetadata)
            .filter(ChannelMetadata.gemini_store_id == "fileSearchStores/no-meta-store")
            .first()
        )
        assert created_meta is not None
        assert created_meta.name == "No Meta Channel"
        assert created_meta.created_at is not None

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_list_channels_persists_timestamp_across_calls(
        self, client_with_db: TestClient, test_db
    ):
        """Subsequent list_channels() calls should return the same persisted timestamp,
        not a fresh datetime.now(UTC) each time.
        """
        mock_channel_port = MagicMock()
        mock_channel_port.list_channels.return_value = [
            ChannelDTO(
                name="fileSearchStores/persist-store",
                display_name="Persist Channel",
            ),
        ]

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        use_case = _make_use_case(
            test_db, channel_port=mock_channel_port, document_port=mock_document_port,
        )
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        # First call - auto-creates metadata
        response1 = client_with_db.get("/api/v1/channels")
        assert response1.status_code == 200
        created_at_1 = response1.json()["channels"][0]["created_at"]

        # Second call - should use persisted timestamp
        response2 = client_with_db.get("/api/v1/channels")
        assert response2.status_code == 200
        created_at_2 = response2.json()["channels"][0]["created_at"]

        # Timestamps must be identical (persisted, not regenerated)
        assert created_at_1 == created_at_2

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_get_channel_auto_creates_metadata_when_none(
        self, client_with_db: TestClient, test_db
    ):
        """get_channel() should auto-create local metadata for a channel without it."""
        channel_id = "fileSearchStores/no-meta-detail"

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=channel_id,
            display_name="Detail No Meta",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        use_case = _make_use_case(
            test_db, channel_port=mock_channel_port, document_port=mock_document_port,
        )
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        response = client_with_db.get(f"/api/v1/channels/{channel_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == channel_id
        assert "created_at" in data

        # Verify metadata was auto-created in the DB
        created_meta = (
            test_db.query(ChannelMetadata)
            .filter(ChannelMetadata.gemini_store_id == channel_id)
            .first()
        )
        assert created_meta is not None
        assert created_meta.name == "Detail No Meta"
        assert created_meta.created_at is not None

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)

    def test_get_channel_persists_timestamp_across_calls(
        self, client_with_db: TestClient, test_db
    ):
        """Subsequent get_channel() calls should return the same persisted timestamp."""
        channel_id = "fileSearchStores/persist-detail"

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=channel_id,
            display_name="Persist Detail",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        use_case = _make_use_case(
            test_db, channel_port=mock_channel_port, document_port=mock_document_port,
        )
        app.dependency_overrides[get_channel_crud_use_case_factory] = lambda: lambda: use_case

        # First call - auto-creates metadata
        response1 = client_with_db.get(f"/api/v1/channels/{channel_id}")
        assert response1.status_code == 200
        created_at_1 = response1.json()["created_at"]

        # Second call - should use persisted timestamp
        response2 = client_with_db.get(f"/api/v1/channels/{channel_id}")
        assert response2.status_code == 200
        created_at_2 = response2.json()["created_at"]

        assert created_at_1 == created_at_2

        app.dependency_overrides.pop(get_channel_crud_use_case_factory, None)
