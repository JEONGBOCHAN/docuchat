# -*- coding: utf-8 -*-
"""Tests for Capacity API."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.api.v1.capacity import get_channel_port
from src.application.ports.channel import ChannelDTO
from src.infrastructure.persistence.channel_repository import ChannelRepository


class TestGetCapacityUsage:
    """Tests for GET /api/v1/capacity."""

    def test_get_capacity_empty_channel(self, client_with_db: TestClient, test_db):
        """Test getting capacity for empty channel."""
        # Create channel in local DB
        repo = ChannelRepository(test_db)
        repo.create(gemini_store_id="fileSearchStores/test-store", name="Test")

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.get(
            "/api/v1/capacity",
            params={"channel_id": "fileSearchStores/test-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["file_count"] == 0
        assert data["max_files"] == 100
        assert data["file_usage_percent"] == 0.0
        assert data["can_upload"] is True
        assert data["remaining_files"] == 100

        app.dependency_overrides.pop(get_channel_port, None)

    def test_get_capacity_with_usage(self, client_with_db: TestClient, test_db):
        """Test getting capacity for channel with usage."""
        # Create channel with some usage
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="fileSearchStores/used-store", name="Used")
        repo.update_stats("fileSearchStores/used-store", file_count=25, total_size_bytes=50 * 1024 * 1024)

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/used-store",
            display_name="Used Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.get(
            "/api/v1/capacity",
            params={"channel_id": "fileSearchStores/used-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["file_count"] == 25
        assert data["file_usage_percent"] == 25.0
        assert data["size_mb"] == 50.0
        assert data["size_usage_percent"] == 10.0
        assert data["can_upload"] is True
        assert data["remaining_files"] == 75

        app.dependency_overrides.pop(get_channel_port, None)

    def test_get_capacity_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test getting capacity for nonexistent channel."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.get(
            "/api/v1/capacity",
            params={"channel_id": "fileSearchStores/not-exists"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_channel_port, None)

    def test_get_capacity_gemini_only_channel(self, client_with_db: TestClient, test_db):
        """Test getting capacity for channel only in Gemini (not in local DB)."""
        # Don't create local DB entry

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/gemini-only",
            display_name="Gemini Only",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.get(
            "/api/v1/capacity",
            params={"channel_id": "fileSearchStores/gemini-only"},
        )

        assert response.status_code == 200
        data = response.json()
        # Should return default empty usage
        assert data["file_count"] == 0
        assert data["can_upload"] is True

        app.dependency_overrides.pop(get_channel_port, None)

    def test_get_capacity_at_limit(self, client_with_db: TestClient, test_db):
        """Test getting capacity when at limits."""
        # Create channel at file limit
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="fileSearchStores/full-store", name="Full")
        repo.update_stats("fileSearchStores/full-store", file_count=100, total_size_bytes=0)

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/full-store",
            display_name="Full Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.get(
            "/api/v1/capacity",
            params={"channel_id": "fileSearchStores/full-store"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["file_count"] == 100
        assert data["file_usage_percent"] == 100.0
        assert data["can_upload"] is False
        assert data["remaining_files"] == 0

        app.dependency_overrides.pop(get_channel_port, None)
