# -*- coding: utf-8 -*-
"""Tests for FAQ API."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service


class TestGenerateFAQ:
    """Tests for POST /api/v1/channels/{channel_id}/generate-faq."""

    def test_generate_faq_success(self, client_with_db: TestClient, test_db):
        """Test successful FAQ generation."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file", "display_name": "test.pdf", "size_bytes": 1024},
        ]
        mock_gemini.generate_faq.return_value = {
            "items": [
                {"question": "What is the main topic?", "answer": "The main topic is..."},
                {"question": "How does it work?", "answer": "It works by..."},
            ],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-faq",
            json={"count": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert len(data["items"]) == 2
        assert data["items"][0]["question"] == "What is the main topic?"
        assert data["items"][0]["answer"] == "The main topic is..."
        assert "generated_at" in data

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_faq_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test FAQ generation for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/generate-faq",
            json={"count": 5},
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_faq_no_documents(self, client_with_db: TestClient, test_db):
        """Test FAQ generation when channel has no documents."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/empty-store",
            "display_name": "Empty Channel",
        }
        mock_gemini.list_store_files.return_value = []

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/empty-store/generate-faq",
            json={"count": 5},
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_faq_default_count(self, client_with_db: TestClient, test_db):
        """Test FAQ generation with default count."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file", "display_name": "test.pdf", "size_bytes": 1024},
        ]
        mock_gemini.generate_faq.return_value = {
            "items": [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(5)],
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-faq",
            json={},
        )

        assert response.status_code == 200
        # Default count is 5
        mock_gemini.generate_faq.assert_called_once_with(
            "fileSearchStores/test-store", count=5
        )

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_generate_faq_invalid_count(self, client_with_db: TestClient, test_db):
        """Test FAQ generation with invalid count."""
        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-faq",
            json={"count": 0},  # Must be >= 1
        )
        assert response.status_code == 422

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-faq",
            json={"count": 25},  # Must be <= 20
        )
        assert response.status_code == 422

    def test_generate_faq_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors during FAQ generation."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file", "display_name": "test.pdf", "size_bytes": 1024},
        ]
        mock_gemini.generate_faq.return_value = {
            "items": [],
            "error": "API rate limit exceeded",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/generate-faq",
            json={"count": 5},
        )

        assert response.status_code == 500
        assert "Failed to generate FAQ" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)
