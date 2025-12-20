# -*- coding: utf-8 -*-
"""Tests for Channel CRUD API."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service


class TestCreateChannel:
    """Tests for POST /api/v1/channels."""

    def test_create_channel_success(self, client: TestClient):
        """Test successful channel creation."""
        mock_gemini = MagicMock()
        mock_gemini.create_store.return_value = {
            "name": "fileSearchStores/test-store-123",
            "display_name": "Test Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.post(
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
        app.dependency_overrides.clear()

    def test_create_channel_empty_name(self, client: TestClient):
        """Test channel creation with empty name fails."""
        response = client.post(
            "/api/v1/channels",
            json={"name": ""},
        )

        assert response.status_code == 422  # Validation error

    def test_create_channel_api_error(self, client: TestClient):
        """Test channel creation handles API errors."""
        mock_gemini = MagicMock()
        mock_gemini.create_store.side_effect = Exception("API Error")

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.post(
            "/api/v1/channels",
            json={"name": "Test Channel"},
        )

        assert response.status_code == 500
        assert "Failed to create channel" in response.json()["detail"]

        app.dependency_overrides.clear()


class TestListChannels:
    """Tests for GET /api/v1/channels."""

    def test_list_channels_success(self, client: TestClient):
        """Test listing channels."""
        mock_gemini = MagicMock()
        mock_gemini.list_stores.return_value = [
            {"name": "fileSearchStores/store-1", "display_name": "Channel 1"},
            {"name": "fileSearchStores/store-2", "display_name": "Channel 2"},
        ]

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.get("/api/v1/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["channels"]) == 2
        assert data["channels"][0]["name"] == "Channel 1"
        assert data["channels"][1]["name"] == "Channel 2"

        app.dependency_overrides.clear()

    def test_list_channels_empty(self, client: TestClient):
        """Test listing when no channels exist."""
        mock_gemini = MagicMock()
        mock_gemini.list_stores.return_value = []

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.get("/api/v1/channels")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["channels"] == []

        app.dependency_overrides.clear()


class TestGetChannel:
    """Tests for GET /api/v1/channels/{channel_id}."""

    def test_get_channel_success(self, client: TestClient):
        """Test getting a specific channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/store-123",
            "display_name": "My Channel",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.get("/api/v1/channels/fileSearchStores/store-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "fileSearchStores/store-123"
        assert data["name"] == "My Channel"

        app.dependency_overrides.clear()

    def test_get_channel_not_found(self, client: TestClient):
        """Test getting non-existent channel returns 404."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.get("/api/v1/channels/fileSearchStores/not-exists")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

        app.dependency_overrides.clear()


class TestDeleteChannel:
    """Tests for DELETE /api/v1/channels/{channel_id}."""

    def test_delete_channel_success(self, client: TestClient):
        """Test successful channel deletion."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/store-123",
            "display_name": "My Channel",
        }
        mock_gemini.delete_store.return_value = True

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.delete("/api/v1/channels/fileSearchStores/store-123")

        assert response.status_code == 204

        app.dependency_overrides.clear()

    def test_delete_channel_not_found(self, client: TestClient):
        """Test deleting non-existent channel returns 404."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.delete("/api/v1/channels/fileSearchStores/not-exists")

        assert response.status_code == 404

        app.dependency_overrides.clear()

    def test_delete_channel_api_error(self, client: TestClient):
        """Test delete handles API errors."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/store-123",
            "display_name": "My Channel",
        }
        mock_gemini.delete_store.return_value = False

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client.delete("/api/v1/channels/fileSearchStores/store-123")

        assert response.status_code == 500
        assert "Failed to delete" in response.json()["detail"]

        app.dependency_overrides.clear()
