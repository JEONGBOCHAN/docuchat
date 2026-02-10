# -*- coding: utf-8 -*-
"""
Summarization Port.

Defines the interface for document and channel summarization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SummaryDTO:
    """Result of summarization."""

    summary: str


class SummarizationPort(ABC):
    """Abstract interface for document summarization.

    Implementations generate summaries from documents or channels.

    Example:
        # Using Gemini
        adapter = GeminiSummarizationAdapter(gemini_service)
        result = adapter.summarize_channel("channel-123", summary_type="short")

        # Summarize single document
        result = adapter.summarize_document(
            "channel-123",
            document_name="report.pdf",
            summary_type="detailed",
        )
    """

    @abstractmethod
    def summarize_channel(
        self,
        store_name: str,
        summary_type: str = "short",
    ) -> SummaryDTO:
        """Summarize all documents in a channel.

        Args:
            store_name: The document store to summarize
            summary_type: 'short' (2-3 sentences) or 'detailed' (comprehensive)

        Returns:
            SummaryDTO with the generated summary
        """
        pass

    @abstractmethod
    def summarize_document(
        self,
        store_name: str,
        document_name: str,
        summary_type: str = "short",
    ) -> SummaryDTO:
        """Summarize a specific document.

        Args:
            store_name: The document store containing the document
            document_name: The name of the document to summarize
            summary_type: 'short' (2-3 sentences) or 'detailed' (comprehensive)

        Returns:
            SummaryDTO with the generated summary
        """
        pass
