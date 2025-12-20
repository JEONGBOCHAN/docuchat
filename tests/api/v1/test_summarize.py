# -*- coding: utf-8 -*-
"""Tests for Summarize API."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.main import app
from src.services.gemini import get_gemini_service


class TestSummarizeChannel:
    """Tests for POST /api/v1/channels/{channel_id}/summarize."""

    def test_summarize_channel_short_success(self, client_with_db: TestClient, test_db):
        """Test successful short channel summary."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file", "display_name": "test.pdf", "size_bytes": 1024},
        ]
        mock_gemini.summarize_channel.return_value = {
            "summary": "This is a short summary of the documents.",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/summarize",
            json={"summary_type": "short"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["summary_type"] == "short"
        assert data["summary"] == "This is a short summary of the documents."
        assert data["document_id"] is None
        assert "generated_at" in data

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_channel_detailed_success(self, client_with_db: TestClient, test_db):
        """Test successful detailed channel summary."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file", "display_name": "test.pdf", "size_bytes": 1024},
        ]
        mock_gemini.summarize_channel.return_value = {
            "summary": "**Overview**: Detailed summary...\n**Key Topics**: ...",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/summarize",
            json={"summary_type": "detailed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary_type"] == "detailed"
        assert "Overview" in data["summary"]

        mock_gemini.summarize_channel.assert_called_once_with(
            "fileSearchStores/test-store", summary_type="detailed"
        )

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_channel_default_type(self, client_with_db: TestClient, test_db):
        """Test channel summary with default type (short)."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file", "display_name": "test.pdf", "size_bytes": 1024},
        ]
        mock_gemini.summarize_channel.return_value = {
            "summary": "Short summary.",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/summarize",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary_type"] == "short"

        mock_gemini.summarize_channel.assert_called_once_with(
            "fileSearchStores/test-store", summary_type="short"
        )

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test channel summary for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/summarize",
            json={},
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_channel_no_documents(self, client_with_db: TestClient, test_db):
        """Test channel summary when channel has no documents."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/empty-store",
            "display_name": "Empty Channel",
        }
        mock_gemini.list_store_files.return_value = []

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/empty-store/summarize",
            json={},
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_channel_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors during channel summarization."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file", "display_name": "test.pdf", "size_bytes": 1024},
        ]
        mock_gemini.summarize_channel.return_value = {
            "summary": "",
            "error": "API rate limit exceeded",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/summarize",
            json={},
        )

        assert response.status_code == 500
        assert "Failed to generate summary" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)


class TestSummarizeDocument:
    """Tests for POST /api/v1/channels/{channel_id}/documents/{document_id}/summarize."""

    def test_summarize_document_short_success(self, client_with_db: TestClient, test_db):
        """Test successful short document summary."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file-123", "display_name": "report.pdf", "size_bytes": 1024},
        ]
        mock_gemini.summarize_document.return_value = {
            "summary": "This document is about...",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/documents/files/test-file-123/summarize",
            json={"summary_type": "short"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["document_id"] == "files/test-file-123"
        assert data["summary_type"] == "short"
        assert data["summary"] == "This document is about..."
        assert "generated_at" in data

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_document_detailed_success(self, client_with_db: TestClient, test_db):
        """Test successful detailed document summary."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file-123", "display_name": "report.pdf", "size_bytes": 1024},
        ]
        mock_gemini.summarize_document.return_value = {
            "summary": "**Overview**: Document details...\n**Key Points**: ...",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/documents/files/test-file-123/summarize",
            json={"summary_type": "detailed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary_type"] == "detailed"
        assert "Overview" in data["summary"]

        mock_gemini.summarize_document.assert_called_once_with(
            "fileSearchStores/test-store",
            document_name="report.pdf",
            summary_type="detailed",
        )

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_document_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test document summary for non-existent channel."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = None

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/documents/files/doc-123/summarize",
            json={},
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_document_not_found(self, client_with_db: TestClient, test_db):
        """Test document summary for non-existent document."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/other-file", "display_name": "other.pdf", "size_bytes": 1024},
        ]

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/documents/files/not-exists/summarize",
            json={},
        )

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_document_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors during document summarization."""
        mock_gemini = MagicMock()
        mock_gemini.get_store.return_value = {
            "name": "fileSearchStores/test-store",
            "display_name": "Test Channel",
        }
        mock_gemini.list_store_files.return_value = [
            {"name": "files/test-file-123", "display_name": "report.pdf", "size_bytes": 1024},
        ]
        mock_gemini.summarize_document.return_value = {
            "summary": "",
            "error": "Processing failed",
        }

        app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/documents/files/test-file-123/summarize",
            json={},
        )

        assert response.status_code == 500
        assert "Failed to generate summary" in response.json()["detail"]

        app.dependency_overrides.pop(get_gemini_service, None)

    def test_summarize_document_invalid_type(self, client_with_db: TestClient, test_db):
        """Test document summary with invalid summary type."""
        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/documents/files/doc-123/summarize",
            json={"summary_type": "invalid"},
        )

        assert response.status_code == 422
