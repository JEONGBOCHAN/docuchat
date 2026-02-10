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

    def delete_any(self, document_id: str) -> bool:
        """Delete a document or file by its ID, regardless of format.

        Determines the correct deletion method based on the ID format.
        Subclasses may override for provider-specific logic.

        Args:
            document_id: Document or file ID in any supported format.

        Returns:
            True if deleted successfully.
        """
        # Default: try document delete, fall back to file delete.
        if self.is_store_document(document_id):
            return self.delete_document(document_id)
        return self.delete_file(document_id)

    def extract_channel_id(self, document_id: str) -> str | None:
        """Extract the channel ID from a document ID.

        Provider-specific parsing of compound IDs. Returns None if
        the document ID format does not contain a channel reference.

        Args:
            document_id: The document identifier.

        Returns:
            Channel ID string, or None if not extractable.
        """
        return None

    def is_store_document(self, document_id: str) -> bool:
        """Check if the given ID refers to a store document (vs. a file).

        Args:
            document_id: The document/file identifier.

        Returns:
            True if this is a store document ID.
        """
        return False

    def is_valid_file_reference(self, file_id: str) -> bool:
        """Check if the given ID is a valid file reference.

        Args:
            file_id: The file identifier to validate.

        Returns:
            True if the format is valid for this provider.
        """
        return bool(file_id)
