# -*- coding: utf-8 -*-
"""
Gemini Document Adapter.

Implements DocumentPort using Google Gemini File Search Store API.
"""

import requests
from google import genai

from src.application.ports.document import DocumentPort, DocumentDTO, UploadResultDTO
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class GeminiDocumentAdapter(DocumentPort):
    """DocumentPort implementation using Google Gemini File Search Store.

    This adapter directly interacts with Gemini File Search Store API
    for document CRUD operations.

    Example:
        adapter = GeminiDocumentAdapter()
        result = adapter.upload_document("channel-123", "/path/to/file.pdf")
        documents = adapter.list_documents("channel-123")
        adapter.delete_document(documents[0].name)
    """

    def __init__(self, client: genai.Client | None = None):
        """Initialize adapter with Gemini client.

        Args:
            client: Optional Gemini client instance.
                   Creates one if not provided.
        """
        settings = get_settings()
        self._api_key = settings.google_api_key
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def upload_document(
        self,
        channel_id: str,
        file_path: str,
        display_name: str | None = None,
    ) -> UploadResultDTO:
        """Upload a document to a channel.

        Args:
            channel_id: The channel name/ID (e.g., "fileSearchStores/xxx").
            file_path: Path to the file to upload.
            display_name: Optional display name for the document.

        Returns:
            UploadResultDTO with operation information.

        Raises:
            Exception: If upload fails.
        """
        config = {}
        if display_name:
            config["display_name"] = display_name

        operation = self._get_client().file_search_stores.upload_to_file_search_store(
            file=file_path,
            file_search_store_name=channel_id,
            config=config if config else None,
        )

        # Handle None as False for done field
        is_done = operation.done if operation.done is not None else False

        # Include document_name from response if available
        document_name = None
        if operation.response and hasattr(operation.response, "document_name"):
            document_name = operation.response.document_name

        return UploadResultDTO(
            operation_name=operation.name,
            done=is_done,
            document_name=document_name,
        )

    def get_operation_status(self, operation_name: str) -> UploadResultDTO:
        """Get the status of a document by checking its state in the channel.

        The Gemini File Search API's operations.get() doesn't work reliably,
        so we check the document state via list_documents instead.
        If the document_id is a store document, we extract its channel and
        look up the document state directly.

        Args:
            operation_name: The document or operation name/ID.

        Returns:
            UploadResultDTO with document status based on actual state.
        """
        # Try to resolve document state from channel listing
        if operation_name.startswith("fileSearchStores/"):
            channel_id = self.extract_channel_id(operation_name)
            if channel_id:
                try:
                    documents = self.list_documents(channel_id)
                    for doc in documents:
                        if doc.name == operation_name:
                            is_done = doc.state == "ACTIVE"
                            return UploadResultDTO(
                                operation_name=operation_name,
                                done=is_done,
                                document_name=operation_name,
                            )
                except Exception:
                    logger.warning(
                        "Failed to check document status via listing",
                        document_id=operation_name,
                    )

        # Fallback: unknown status — assume NOT done to avoid false positives
        return UploadResultDTO(
            operation_name=operation_name,
            done=False,
            document_name=None,
        )

    def list_documents(self, channel_id: str) -> list[DocumentDTO]:
        """List all documents in a channel.

        Args:
            channel_id: The channel name/ID.

        Returns:
            List of DocumentDTO objects.
        """
        documents = []
        try:
            doc_list = list(
                self._get_client().file_search_stores.documents.list(parent=channel_id)
            )
            for doc in doc_list:
                # Get state as string
                state = "ACTIVE"
                if hasattr(doc, "state"):
                    state_val = doc.state
                    if hasattr(state_val, "name"):
                        state = state_val.name.replace("STATE_", "")
                    elif isinstance(state_val, str):
                        state = state_val.replace("STATE_", "")

                documents.append(
                    DocumentDTO(
                        name=doc.name if hasattr(doc, "name") else "",
                        display_name=doc.display_name if hasattr(doc, "display_name") else "",
                        size_bytes=doc.size_bytes if hasattr(doc, "size_bytes") else 0,
                        state=state,
                    )
                )
        except Exception:
            logger.error("Failed to list documents from Gemini", channel_id=channel_id)
            raise
        return documents

    def delete_file(self, file_name: str) -> bool:
        """Delete a file from the Files API.

        Args:
            file_name: The file name/ID (e.g., "files/xxx").

        Returns:
            True if deleted successfully.
        """
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}"
            url += f"?key={self._api_key}"
            response = requests.delete(url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def delete_document(self, document_name: str, force: bool = True) -> bool:
        """Delete a document from a channel.

        Uses REST API directly because SDK doesn't support force delete.

        Args:
            document_name: The document name (e.g., "fileSearchStores/xxx/documents/yyy").
            force: If True, delete even if document has chunks.

        Returns:
            True if deleted successfully or already deleted.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/{document_name}"
        if force:
            url += "?force=true"
        url += f"&key={self._api_key}" if force else f"?key={self._api_key}"

        response = requests.delete(url, timeout=10)
        # Treat 200 (success) and 404 (not found/already deleted) as success
        return response.status_code in (200, 404)

    # -- Provider-specific ID helpers (Gemini) --

    def extract_channel_id(self, document_id: str) -> str | None:
        """Extract channel ID from Gemini document ID.

        Gemini format: 'fileSearchStores/xxx/documents/yyy' -> 'fileSearchStores/xxx'
        """
        if document_id.startswith("fileSearchStores/"):
            parts = document_id.split("/documents/")
            if len(parts) >= 1:
                return parts[0]
        return None

    def is_store_document(self, document_id: str) -> bool:
        """Check if ID is a Gemini store document (vs. a files/ reference)."""
        return document_id.startswith("fileSearchStores/")

    def is_valid_file_reference(self, file_id: str) -> bool:
        """Check if ID is a valid Gemini files/ reference."""
        return bool(file_id) and file_id.startswith("files/")
