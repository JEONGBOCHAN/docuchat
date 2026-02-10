# -*- coding: utf-8 -*-
"""
Document Summary Ports.

Defines interfaces for document summary generation and caching.
This enables the agent to know what documents are uploaded to a channel
and choose the appropriate tool (search_documents vs web_search).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DocumentSummaryDTO:
    """Data transfer object for document summary.

    Attributes:
        document_id: Unique identifier for the document (Gemini file ID)
        channel_id: The channel (store) containing the document
        document_name: Display name of the document
        summary: Short summary of document content (~100 tokens)
        created_at: When the summary was created
        updated_at: When the summary was last updated
    """
    document_id: str
    channel_id: str
    document_name: str
    summary: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentSummaryGenerationPort(ABC):
    """Abstract interface for generating document summaries.

    Implementations generate concise summaries from documents
    that can be injected into the agent's system prompt.

    Example:
        adapter = GeminiDocumentSummaryAdapter()
        summary = adapter.generate_summary(
            channel_id="channel-123",
            document_name="transformer.pdf",
        )
    """

    @abstractmethod
    def generate_summary(
        self,
        channel_id: str,
        document_name: str,
        max_tokens: int = 100,
    ) -> str:
        """Generate a concise summary for a document.

        Args:
            channel_id: The channel (store) containing the document
            document_name: Name of the document to summarize
            max_tokens: Maximum tokens for the summary (default: ~100)

        Returns:
            Concise summary string suitable for system prompt injection

        Raises:
            Exception: If summary generation fails
        """
        pass


class DocumentSummaryCachePort(ABC):
    """Abstract interface for document summary persistence.

    Implementations store and retrieve document summaries
    for efficient access during chat.

    Example:
        repo = DocumentSummaryCacheRepository(db)

        # Save summary after document upload
        repo.save(summary_dto)

        # Get all summaries for a channel during chat
        summaries = repo.get_by_channel("channel-123")
    """

    @abstractmethod
    def save(self, summary: DocumentSummaryDTO) -> DocumentSummaryDTO:
        """Save or update a document summary.

        Args:
            summary: The summary to save

        Returns:
            Saved DocumentSummaryDTO with timestamps
        """
        pass

    @abstractmethod
    def get_by_document_id(self, document_id: str) -> DocumentSummaryDTO | None:
        """Get summary by document ID.

        Args:
            document_id: The document's unique ID

        Returns:
            DocumentSummaryDTO or None if not found
        """
        pass

    @abstractmethod
    def get_by_channel(
        self,
        channel_id: str,
        limit: int = 10,
    ) -> list[DocumentSummaryDTO]:
        """Get all summaries for a channel.

        Args:
            channel_id: The channel (store) ID
            limit: Maximum number of summaries to return

        Returns:
            List of DocumentSummaryDTO for the channel
        """
        pass

    @abstractmethod
    def delete_by_document_id(self, document_id: str) -> bool:
        """Delete a summary by document ID.

        Args:
            document_id: The document's unique ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def delete_by_channel(self, channel_id: str) -> int:
        """Delete all summaries for a channel.

        Args:
            channel_id: The channel (store) ID

        Returns:
            Number of summaries deleted
        """
        pass
