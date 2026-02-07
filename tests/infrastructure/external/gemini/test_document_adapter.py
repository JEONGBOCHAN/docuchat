# -*- coding: utf-8 -*-
"""
Tests for GeminiDocumentAdapter.

Tests the Gemini adapter implementation for document operations.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.infrastructure.external.gemini.document import GeminiDocumentAdapter
from src.application.ports.document import DocumentDTO, UploadResultDTO


class TestGeminiDocumentAdapter:
    """Tests for GeminiDocumentAdapter."""

    def _create_mock_client(self):
        """Create a mock Gemini client."""
        return Mock()

    def _create_mock_operation(
        self, name: str, done: bool = False, document_name: str | None = None
    ):
        """Create a mock upload operation."""
        mock_op = Mock()
        mock_op.name = name
        mock_op.done = done
        if document_name:
            mock_op.response = Mock()
            mock_op.response.document_name = document_name
        else:
            mock_op.response = None
        return mock_op

    def _create_mock_document(
        self,
        name: str,
        display_name: str = "",
        size_bytes: int = 0,
        state: str = "ACTIVE",
    ):
        """Create a mock document object."""
        mock_doc = Mock()
        mock_doc.name = name
        mock_doc.display_name = display_name
        mock_doc.size_bytes = size_bytes
        mock_state = Mock()
        mock_state.name = f"STATE_{state}"
        mock_doc.state = mock_state
        return mock_doc

    def test_upload_document_success(self):
        """Test successful document upload."""
        mock_client = self._create_mock_client()
        mock_op = self._create_mock_operation(
            "operations/op-123",
            done=True,
            document_name="fileSearchStores/ch-1/documents/doc-1"
        )
        mock_client.file_search_stores.upload_to_file_search_store.return_value = mock_op

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.upload_document(
            "fileSearchStores/ch-1",
            "/path/to/file.pdf",
            display_name="My Document"
        )

        assert isinstance(result, UploadResultDTO)
        assert result.operation_name == "operations/op-123"
        assert result.done is True
        assert result.document_name == "fileSearchStores/ch-1/documents/doc-1"

        mock_client.file_search_stores.upload_to_file_search_store.assert_called_once_with(
            file="/path/to/file.pdf",
            file_search_store_name="fileSearchStores/ch-1",
            config={"display_name": "My Document"},
        )

    def test_upload_document_without_display_name(self):
        """Test document upload without display name."""
        mock_client = self._create_mock_client()
        mock_op = self._create_mock_operation("operations/op-123", done=False)
        mock_client.file_search_stores.upload_to_file_search_store.return_value = mock_op

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.upload_document("fileSearchStores/ch-1", "/path/to/file.pdf")

        assert result.operation_name == "operations/op-123"
        mock_client.file_search_stores.upload_to_file_search_store.assert_called_once_with(
            file="/path/to/file.pdf",
            file_search_store_name="fileSearchStores/ch-1",
            config=None,
        )

    def test_upload_document_done_is_none(self):
        """Test document upload when done is None."""
        mock_client = self._create_mock_client()
        mock_op = Mock()
        mock_op.name = "operations/op-123"
        mock_op.done = None
        mock_op.response = None
        mock_client.file_search_stores.upload_to_file_search_store.return_value = mock_op

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.upload_document("fileSearchStores/ch-1", "/path/to/file.pdf")

        assert result.done is False

    def test_get_operation_status(self):
        """Test get operation status always returns done=True."""
        mock_client = self._create_mock_client()

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.get_operation_status("operations/op-123")

        assert isinstance(result, UploadResultDTO)
        assert result.operation_name == "operations/op-123"
        assert result.done is True
        assert result.document_name is None

    def test_list_documents_success(self):
        """Test successful document listing."""
        mock_client = self._create_mock_client()
        mock_docs = [
            self._create_mock_document(
                "fileSearchStores/ch-1/documents/doc-1",
                "Document 1",
                1024,
                "ACTIVE"
            ),
            self._create_mock_document(
                "fileSearchStores/ch-1/documents/doc-2",
                "Document 2",
                2048,
                "PENDING"
            ),
        ]
        mock_client.file_search_stores.documents.list.return_value = mock_docs

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.list_documents("fileSearchStores/ch-1")

        assert len(result) == 2
        assert all(isinstance(doc, DocumentDTO) for doc in result)
        assert result[0].name == "fileSearchStores/ch-1/documents/doc-1"
        assert result[0].display_name == "Document 1"
        assert result[0].size_bytes == 1024
        assert result[0].state == "ACTIVE"
        assert result[1].state == "PENDING"

        mock_client.file_search_stores.documents.list.assert_called_once_with(
            parent="fileSearchStores/ch-1"
        )

    def test_list_documents_empty(self):
        """Test document listing when no documents exist."""
        mock_client = self._create_mock_client()
        mock_client.file_search_stores.documents.list.return_value = []

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.list_documents("fileSearchStores/ch-1")

        assert result == []

    def test_list_documents_missing_attributes(self):
        """Test document listing when documents have missing attributes."""
        mock_client = self._create_mock_client()
        mock_doc = Mock()
        # Remove all attributes except name
        del mock_doc.display_name
        del mock_doc.size_bytes
        del mock_doc.state
        mock_doc.name = "fileSearchStores/ch-1/documents/doc-1"
        mock_client.file_search_stores.documents.list.return_value = [mock_doc]

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.list_documents("fileSearchStores/ch-1")

        assert len(result) == 1
        assert result[0].name == "fileSearchStores/ch-1/documents/doc-1"
        assert result[0].display_name == ""
        assert result[0].size_bytes == 0
        assert result[0].state == "ACTIVE"

    def test_list_documents_state_as_string(self):
        """Test document listing when state is a string."""
        mock_client = self._create_mock_client()
        mock_doc = Mock()
        mock_doc.name = "fileSearchStores/ch-1/documents/doc-1"
        mock_doc.display_name = "Doc"
        mock_doc.size_bytes = 100
        mock_doc.state = "STATE_ACTIVE"
        mock_client.file_search_stores.documents.list.return_value = [mock_doc]

        adapter = GeminiDocumentAdapter(client=mock_client)
        result = adapter.list_documents("fileSearchStores/ch-1")

        assert result[0].state == "ACTIVE"

    def test_list_documents_exception(self):
        """Test document listing when exception occurs raises instead of swallowing."""
        mock_client = self._create_mock_client()
        mock_client.file_search_stores.documents.list.side_effect = Exception("API error")

        adapter = GeminiDocumentAdapter(client=mock_client)
        with pytest.raises(Exception, match="API error"):
            adapter.list_documents("fileSearchStores/ch-1")

    @patch('src.infrastructure.external.gemini.document.requests.delete')
    def test_delete_file_success(self, mock_delete):
        """Test successful file deletion."""
        mock_delete.return_value.status_code = 200
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)
            result = adapter.delete_file("files/file-123")

        assert result is True
        mock_delete.assert_called_once()
        call_url = mock_delete.call_args[0][0]
        assert "files/file-123" in call_url

    @patch('src.infrastructure.external.gemini.document.requests.delete')
    def test_delete_file_failure(self, mock_delete):
        """Test file deletion failure."""
        mock_delete.return_value.status_code = 404
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)
            result = adapter.delete_file("files/nonexistent")

        assert result is False

    @patch('src.infrastructure.external.gemini.document.requests.delete')
    def test_delete_file_exception(self, mock_delete):
        """Test file deletion exception handling."""
        mock_delete.side_effect = Exception("Network error")
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)
            result = adapter.delete_file("files/file-123")

        assert result is False

    @patch('src.infrastructure.external.gemini.document.requests.delete')
    def test_delete_document_success(self, mock_delete):
        """Test successful document deletion."""
        mock_delete.return_value.status_code = 200
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)
            result = adapter.delete_document("fileSearchStores/ch-1/documents/doc-1")

        assert result is True
        call_url = mock_delete.call_args[0][0]
        assert "fileSearchStores/ch-1/documents/doc-1" in call_url
        assert "force=true" in call_url

    @patch('src.infrastructure.external.gemini.document.requests.delete')
    def test_delete_document_already_deleted(self, mock_delete):
        """Test document deletion when already deleted (404)."""
        mock_delete.return_value.status_code = 404
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)
            result = adapter.delete_document("fileSearchStores/ch-1/documents/nonexistent")

        assert result is True

    @patch('src.infrastructure.external.gemini.document.requests.delete')
    def test_delete_document_failure(self, mock_delete):
        """Test document deletion failure (500 error)."""
        mock_delete.return_value.status_code = 500
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)
            result = adapter.delete_document("fileSearchStores/ch-1/documents/doc-1")

        assert result is False

    @patch('src.infrastructure.external.gemini.document.requests.delete')
    def test_delete_document_without_force(self, mock_delete):
        """Test document deletion without force flag."""
        mock_delete.return_value.status_code = 200
        mock_client = self._create_mock_client()

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)
            result = adapter.delete_document(
                "fileSearchStores/ch-1/documents/doc-1",
                force=False
            )

        assert result is True
        call_url = mock_delete.call_args[0][0]
        assert "force=true" not in call_url

    def test_adapter_creates_client_if_not_provided(self):
        """Test that adapter creates Gemini client if not provided."""
        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            with patch('src.infrastructure.external.gemini.document.genai.Client') as mock_client_class:
                adapter = GeminiDocumentAdapter()
                mock_client_class.assert_called_once_with(api_key="test-api-key")


class TestGeminiDocumentAdapterIntegration:
    """Integration tests for GeminiDocumentAdapter (mocked)."""

    def test_full_document_workflow(self):
        """Test full document workflow."""
        mock_client = Mock()

        # Upload
        mock_op = Mock()
        mock_op.name = "operations/op-123"
        mock_op.done = True
        mock_op.response = Mock()
        mock_op.response.document_name = "fileSearchStores/ch-1/documents/doc-1"
        mock_client.file_search_stores.upload_to_file_search_store.return_value = mock_op

        # List
        mock_doc = Mock()
        mock_doc.name = "fileSearchStores/ch-1/documents/doc-1"
        mock_doc.display_name = "test.pdf"
        mock_doc.size_bytes = 1024
        mock_state = Mock()
        mock_state.name = "STATE_ACTIVE"
        mock_doc.state = mock_state
        mock_client.file_search_stores.documents.list.return_value = [mock_doc]

        with patch('src.infrastructure.external.gemini.document.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            adapter = GeminiDocumentAdapter(client=mock_client)

            # Upload document
            upload_result = adapter.upload_document(
                "fileSearchStores/ch-1",
                "/path/to/test.pdf",
                display_name="test.pdf"
            )
            assert upload_result.done is True
            assert upload_result.document_name is not None

            # Check operation status
            status = adapter.get_operation_status(upload_result.operation_name)
            assert status.done is True

            # List documents
            documents = adapter.list_documents("fileSearchStores/ch-1")
            assert len(documents) == 1
            assert documents[0].display_name == "test.pdf"

            # Delete document
            with patch('src.infrastructure.external.gemini.document.requests.delete') as mock_delete:
                mock_delete.return_value.status_code = 200
                deleted = adapter.delete_document(documents[0].name)
                assert deleted is True
