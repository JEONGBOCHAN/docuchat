# -*- coding: utf-8 -*-
"""Tests for Summarize API."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.api.v1.deps import get_channel_port, get_document_port, get_document_port_factory
from src.application.ports.channel import ChannelDTO
from src.application.ports.document import DocumentDTO
from src.application.use_cases.summarize import SummarizeResult


class TestSummarizeChannel:
    """Tests for POST /api/v1/channels/{channel_id}/summarize."""

    def test_summarize_channel_short_success(self, client_with_db: TestClient, test_db):
        """Test successful short channel summary."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = SummarizeResult(
            summary="This is a short summary of the documents.",
            channel_id="fileSearchStores/test-store",
            summary_type="short",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.summarize.create_summarize_channel_use_case", return_value=mock_use_case):
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

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_summarize_channel_detailed_success(self, client_with_db: TestClient, test_db):
        """Test successful detailed channel summary."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = SummarizeResult(
            summary="**Overview**: Detailed summary...\n**Key Topics**: ...",
            channel_id="fileSearchStores/test-store",
            summary_type="detailed",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.summarize.create_summarize_channel_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/summarize",
                json={"summary_type": "detailed"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["summary_type"] == "detailed"
        assert "Overview" in data["summary"]

        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store", summary_type="detailed"
        )

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_summarize_channel_default_type(self, client_with_db: TestClient, test_db):
        """Test channel summary with default type (short)."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = SummarizeResult(
            summary="Short summary.",
            channel_id="fileSearchStores/test-store",
            summary_type="short",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.summarize.create_summarize_channel_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/summarize",
                json={},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["summary_type"] == "short"

        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store", summary_type="short"
        )

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_summarize_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test channel summary for non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/summarize",
            json={},
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)

    def test_summarize_channel_no_documents(self, client_with_db: TestClient, test_db):
        """Test channel summary when channel has no documents."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/empty-store",
            display_name="Empty Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = []

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/empty-store/summarize",
            json={},
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_summarize_channel_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors during channel summarization."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = SummarizeResult(
            summary="",
            channel_id="fileSearchStores/test-store",
            error="API rate limit exceeded",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.summarize.create_summarize_channel_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/summarize",
                json={},
            )

        assert response.status_code == 500
        assert "Failed to generate summary" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)


class TestValidationPrecedence:
    """Regression: channel validation must precede document-port factory invocation."""

    def test_channel_not_found_skips_document_port_factory(
        self, client_with_db: TestClient, test_db
    ):
        """When channel is not found, the document-port factory must NOT be called."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        mock_factory = MagicMock()

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: mock_factory

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/summarize",
            json={},
        )

        assert response.status_code == 404
        mock_factory.assert_not_called()

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)


class TestSummarizeDocument:
    """Tests for POST /api/v1/channels/{channel_id}/documents/{document_id}/summarize."""

    def test_summarize_document_short_success(self, client_with_db: TestClient, test_db):
        """Test successful short document summary."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file-123", display_name="report.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = SummarizeResult(
            summary="This document is about...",
            channel_id="fileSearchStores/test-store",
            document_id="report.pdf",
            summary_type="short",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port] = lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.summarize.create_summarize_document_use_case", return_value=mock_use_case):
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

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port, None)

    def test_summarize_document_detailed_success(self, client_with_db: TestClient, test_db):
        """Test successful detailed document summary."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file-123", display_name="report.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = SummarizeResult(
            summary="**Overview**: Document details...\n**Key Points**: ...",
            channel_id="fileSearchStores/test-store",
            document_id="report.pdf",
            summary_type="detailed",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port] = lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.summarize.create_summarize_document_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/documents/files/test-file-123/summarize",
                json={"summary_type": "detailed"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["summary_type"] == "detailed"
        assert "Overview" in data["summary"]

        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store",
            document_name="report.pdf",
            summary_type="detailed",
        )

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port, None)

    def test_summarize_document_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test document summary for non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/documents/files/doc-123/summarize",
            json={},
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)

    def test_summarize_document_not_found(self, client_with_db: TestClient, test_db):
        """Test document summary for non-existent document."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/other-file", display_name="other.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port] = lambda: mock_document_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/documents/files/not-exists/summarize",
            json={},
        )

        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port, None)

    def test_summarize_document_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors during document summarization."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file-123", display_name="report.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = SummarizeResult(
            summary="",
            channel_id="fileSearchStores/test-store",
            document_id="report.pdf",
            error="Processing failed",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port] = lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.summarize.create_summarize_document_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/documents/files/test-file-123/summarize",
                json={},
            )

        assert response.status_code == 500
        assert "Failed to generate summary" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port, None)

    def test_summarize_document_invalid_type(self, client_with_db: TestClient, test_db):
        """Test document summary with invalid summary type."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/documents/files/doc-123/summarize",
            json={"summary_type": "invalid"},
        )

        assert response.status_code == 422

        app.dependency_overrides.pop(get_channel_port, None)
