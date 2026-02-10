# -*- coding: utf-8 -*-
"""Tests for FAQ API."""

from unittest.mock import MagicMock, patch, Mock

from fastapi.testclient import TestClient

from src.main import app
from src.shared.kernel.presentation.dependencies.channel_validation import get_channel_port, get_document_port_factory
from src.application.ports.channel import ChannelDTO
from src.application.ports.document import DocumentDTO
from src.application.use_cases.generate_faq import GenerateFAQUseCase, FAQResult
from src.application.ports.faq_generation import FAQItemDTO


class TestGenerateFAQ:
    """Tests for POST /api/v1/channels/{channel_id}/generate-faq."""

    def test_generate_faq_success(self, client_with_db: TestClient, test_db):
        """Test successful FAQ generation."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        # Mock the use case
        mock_use_case = Mock(spec=GenerateFAQUseCase)
        mock_use_case.execute.return_value = FAQResult(
            items=[
                FAQItemDTO(question="What is the main topic?", answer="The main topic is..."),
                FAQItemDTO(question="How does it work?", answer="It works by..."),
            ],
            channel_id="fileSearchStores/test-store",
            error=None,
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.faq.create_generate_faq_use_case", return_value=mock_use_case):
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

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_faq_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test FAQ generation for non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/generate-faq",
            json={"count": 5},
        )

        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)

    def test_generate_faq_no_documents(self, client_with_db: TestClient, test_db):
        """Test FAQ generation when channel has no documents."""
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
            "/api/v1/channels/fileSearchStores/empty-store/generate-faq",
            json={"count": 5},
        )

        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_faq_default_count(self, client_with_db: TestClient, test_db):
        """Test FAQ generation with default count."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        # Mock the use case
        mock_use_case = Mock(spec=GenerateFAQUseCase)
        mock_use_case.execute.return_value = FAQResult(
            items=[FAQItemDTO(question=f"Q{i}", answer=f"A{i}") for i in range(5)],
            channel_id="fileSearchStores/test-store",
            error=None,
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.faq.create_generate_faq_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-faq",
                json={},
            )

        assert response.status_code == 200
        # Verify default count is 5
        mock_use_case.execute.assert_called_once_with(
            channel_id="fileSearchStores/test-store", count=5
        )

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_faq_invalid_count(self, client_with_db: TestClient, test_db):
        """Test FAQ generation with invalid count."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

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

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)

    def test_generate_faq_api_error(self, client_with_db: TestClient, test_db):
        """Test handling API errors during FAQ generation."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        mock_document_port = MagicMock()
        mock_document_port.list_documents.return_value = [
            DocumentDTO(name="files/test-file", display_name="test.pdf", size_bytes=1024, state="ACTIVE"),
        ]

        # Mock the use case to return an error
        mock_use_case = Mock(spec=GenerateFAQUseCase)
        mock_use_case.execute.return_value = FAQResult(
            items=[],
            channel_id="fileSearchStores/test-store",
            error="API rate limit exceeded",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[get_document_port_factory] = lambda: lambda: mock_document_port

        with patch("src.modules.knowledge.presentation.api.faq.create_generate_faq_use_case", return_value=mock_use_case):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/generate-faq",
                json={"count": 5},
            )

        assert response.status_code == 500
        assert "Failed to generate FAQ" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(get_document_port_factory, None)
