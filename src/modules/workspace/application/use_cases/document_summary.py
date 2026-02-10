# -*- coding: utf-8 -*-
"""
Document Summary Use Cases.

Use cases for generating and retrieving document summaries.
These summaries are used to inject document context into the agent's
system prompt, helping it choose the right tool (search_documents vs web_search).
"""

import logging
from dataclasses import dataclass, field

from src.application.ports.document_summary import (
    DocumentSummaryGenerationPort,
    DocumentSummaryCachePort,
    DocumentSummaryDTO,
)


logger = logging.getLogger(__name__)


@dataclass
class GenerateSummaryResult:
    """Result of generating a document summary.

    Attributes:
        success: Whether the summary was generated successfully
        summary: The generated summary (if successful)
        document_id: ID of the document
        document_name: Name of the document
        error: Error message (if failed)
    """
    success: bool
    summary: str = ""
    document_id: str = ""
    document_name: str = ""
    error: str | None = None


@dataclass
class GetSummariesResult:
    """Result of getting summaries for a channel.

    Attributes:
        summaries: List of document summaries
        channel_id: The channel ID
        count: Number of summaries returned
    """
    summaries: list[DocumentSummaryDTO] = field(default_factory=list)
    channel_id: str = ""
    count: int = 0


class GenerateDocumentSummaryUseCase:
    """Use case for generating and caching a document summary.

    This use case:
    1. Generates a concise summary using Gemini API
    2. Caches the summary in the database
    3. Gracefully handles failures (document upload should not fail if summary fails)

    Example:
        use_case = GenerateDocumentSummaryUseCase(
            generation_port=gemini_adapter,
            cache_port=repository,
        )
        result = use_case.execute(
            channel_id="channel-123",
            document_id="file-abc",
            document_name="transformer.pdf",
        )
        if result.success:
            print(f"Summary: {result.summary}")
    """

    def __init__(
        self,
        generation_port: DocumentSummaryGenerationPort,
        cache_port: DocumentSummaryCachePort,
    ):
        """Initialize the use case with dependencies.

        Args:
            generation_port: Port for generating summaries (e.g., Gemini)
            cache_port: Port for caching summaries (e.g., Database)
        """
        self.generation_port = generation_port
        self.cache_port = cache_port

    def execute(
        self,
        channel_id: str,
        document_id: str,
        document_name: str,
        max_tokens: int = 100,
    ) -> GenerateSummaryResult:
        """Generate and cache a document summary.

        IMPORTANT: This method implements graceful degradation.
        If summary generation or caching fails, it logs the error
        but does NOT raise an exception. The calling code (document upload)
        should continue normally even if summary generation fails.

        Args:
            channel_id: The channel (store) containing the document
            document_id: Unique ID of the document (Gemini file ID)
            document_name: Display name of the document
            max_tokens: Maximum tokens for the summary (default: ~100)

        Returns:
            GenerateSummaryResult with success/failure status
        """
        try:
            # Generate summary using Gemini
            summary_text = self.generation_port.generate_summary(
                channel_id=channel_id,
                document_name=document_name,
                max_tokens=max_tokens,
            )

            # Create DTO
            summary_dto = DocumentSummaryDTO(
                document_id=document_id,
                channel_id=channel_id,
                document_name=document_name,
                summary=summary_text,
            )

            # Cache the summary
            saved_summary = self.cache_port.save(summary_dto)

            logger.info(
                f"Generated summary for document {document_name} "
                f"in channel {channel_id}"
            )

            return GenerateSummaryResult(
                success=True,
                summary=saved_summary.summary,
                document_id=document_id,
                document_name=document_name,
            )

        except Exception as e:
            # Graceful degradation: log error but don't fail
            logger.warning(
                f"Failed to generate summary for {document_name}: {str(e)}"
            )
            return GenerateSummaryResult(
                success=False,
                document_id=document_id,
                document_name=document_name,
                error=str(e),
            )


class GetChannelDocumentSummariesUseCase:
    """Use case for retrieving document summaries for a channel.

    This use case retrieves cached summaries that can be injected
    into the agent's system prompt.

    Example:
        use_case = GetChannelDocumentSummariesUseCase(cache_port=repository)
        result = use_case.execute(channel_id="channel-123", limit=10)

        for summary in result.summaries:
            print(f"- {summary.document_name}: {summary.summary}")
    """

    def __init__(self, cache_port: DocumentSummaryCachePort):
        """Initialize the use case with dependencies.

        Args:
            cache_port: Port for retrieving cached summaries
        """
        self.cache_port = cache_port

    def execute(
        self,
        channel_id: str,
        limit: int = 10,
    ) -> GetSummariesResult:
        """Get document summaries for a channel.

        Args:
            channel_id: The channel (store) ID
            limit: Maximum number of summaries to return (default: 10)

        Returns:
            GetSummariesResult with list of summaries
        """
        summaries = self.cache_port.get_by_channel(
            channel_id=channel_id,
            limit=limit,
        )

        return GetSummariesResult(
            summaries=summaries,
            channel_id=channel_id,
            count=len(summaries),
        )

    def build_context_string(
        self,
        channel_id: str,
        limit: int = 10,
    ) -> str:
        """Build a formatted string of document summaries for system prompt.

        This method creates a human-readable summary list that can be
        directly injected into the agent's system prompt.

        Args:
            channel_id: The channel (store) ID
            limit: Maximum number of summaries to include

        Returns:
            Formatted string describing available documents

        Example output:
            "This channel contains the following documents:
            - transformer.pdf: A research paper about the Transformer architecture...
            - attention_guide.md: A guide explaining attention mechanisms..."
        """
        result = self.execute(channel_id=channel_id, limit=limit)

        if not result.summaries:
            return ""

        lines = ["This channel contains the following documents:"]
        for summary in result.summaries:
            # Truncate summary if too long (keep prompt lean)
            short_summary = summary.summary[:200]
            if len(summary.summary) > 200:
                short_summary += "..."
            lines.append(f"- {summary.document_name}: {short_summary}")

        return "\n".join(lines)
