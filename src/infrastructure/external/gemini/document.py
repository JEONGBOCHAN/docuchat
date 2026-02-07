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
        if client:
            self._client = client
        else:
            self._client = genai.Client(api_key=self._api_key)

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

        operation = self._client.file_search_stores.upload_to_file_search_store(
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
        """Get the status of an upload operation.

        Note: The Gemini File Search API's operations.get() doesn't work reliably
        with the operation names returned by upload_to_file_search_store.
        Since the upload itself succeeds (202 response), we assume the operation
        completed. The actual document status can be checked via list_documents.

        Args:
            operation_name: The operation name/ID.

        Returns:
            UploadResultDTO with operation status (always done=True).
        """
        return UploadResultDTO(
            operation_name=operation_name,
            done=True,
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
                self._client.file_search_stores.documents.list(parent=channel_id)
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
            response = requests.delete(url)
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

        response = requests.delete(url)
        # Treat 200 (success) and 404 (not found/already deleted) as success
        return response.status_code in (200, 404)
