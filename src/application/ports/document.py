# -*- coding: utf-8 -*-
"""
Document Port (Interface).

Defines the interface for document operations within channels.
This abstracts the Gemini File Search Store document operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DocumentDTO:
    """Data Transfer Object for document information."""

    name: str  # The document name/ID (e.g., "fileSearchStores/xxx/documents/yyy")
    display_name: str  # Human-readable name
    size_bytes: int  # File size in bytes
    state: str  # Document state (e.g., "ACTIVE", "PENDING")


@dataclass
class UploadResultDTO:
    """Data Transfer Object for upload operation result."""

    operation_name: str  # The operation name/ID
    done: bool  # Whether the operation is complete
    document_name: str | None = None  # The document name if available


class DocumentPort(ABC):
    """Port for document operations within channels.

    This interface abstracts the document CRUD operations,
    allowing different implementations (Gemini, mock, etc.).
    """

    @abstractmethod
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
        pass

    @abstractmethod
    def get_operation_status(self, operation_name: str) -> UploadResultDTO:
        """Get the status of an upload operation.

        Args:
            operation_name: The operation name/ID.

        Returns:
            UploadResultDTO with operation status.
        """
        pass

    @abstractmethod
    def list_documents(self, channel_id: str) -> list[DocumentDTO]:
        """List all documents in a channel.

        Args:
            channel_id: The channel name/ID.

        Returns:
            List of DocumentDTO objects.
        """
        pass

    @abstractmethod
    def delete_file(self, file_name: str) -> bool:
        """Delete a file from the Files API.

        Args:
            file_name: The file name/ID (e.g., "files/xxx").

        Returns:
            True if deleted successfully.
        """
        pass

    @abstractmethod
    def delete_document(self, document_name: str, force: bool = True) -> bool:
        """Delete a document from a channel.

        Args:
            document_name: The document name (e.g., "fileSearchStores/xxx/documents/yyy").
            force: If True, delete even if document has chunks.

        Returns:
            True if deleted successfully or already deleted.
        """
        pass
