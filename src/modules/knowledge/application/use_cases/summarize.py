# -*- coding: utf-8 -*-
"""
Summarization Use Cases.

These use cases handle document and channel summarization.
They orchestrate the summarization process through the port interface.
"""

from dataclasses import dataclass

from src.application.ports.summarization import SummarizationPort, SummaryDTO


@dataclass
class SummarizeResult:
    """Result of summarization use case.

    Attributes:
        summary: The generated summary text
        channel_id: The channel/store that was analyzed
        document_id: The document that was summarized (if applicable)
        summary_type: The type of summary generated
        error: Error message if summarization failed
    """

    summary: str = ""
    channel_id: str | None = None
    document_id: str | None = None
    summary_type: str = "short"
    error: str | None = None


class SummarizeChannelUseCase:
    """Use case for summarizing all documents in a channel.

    This use case coordinates channel summarization through the port interface,
    allowing the underlying implementation to be swapped without changing
    the application logic.

    Example:
        use_case = SummarizeChannelUseCase(summarization_port=adapter)
        result = use_case.execute(
            channel_id="channel-123",
            summary_type="detailed",
        )
        print(result.summary)
    """

    def __init__(self, summarization_port: SummarizationPort):
        """Initialize the use case with dependencies.

        Args:
            summarization_port: The summarization port implementation
        """
        self.summarization_port = summarization_port

    def execute(
        self,
        channel_id: str,
        summary_type: str = "short",
    ) -> SummarizeResult:
        """Execute channel summarization.

        Args:
            channel_id: The channel (document store) to summarize
            summary_type: 'short' (2-3 sentences) or 'detailed' (comprehensive)

        Returns:
            SummarizeResult with generated summary or error
        """
        try:
            result = self.summarization_port.summarize_channel(
                store_name=channel_id,
                summary_type=summary_type,
            )

            return SummarizeResult(
                summary=result.summary,
                channel_id=channel_id,
                summary_type=summary_type,
                error=None,
            )

        except Exception as e:
            return SummarizeResult(
                summary="",
                channel_id=channel_id,
                summary_type=summary_type,
                error=str(e),
            )


class SummarizeDocumentUseCase:
    """Use case for summarizing a specific document.

    This use case coordinates document summarization through the port interface.

    Example:
        use_case = SummarizeDocumentUseCase(summarization_port=adapter)
        result = use_case.execute(
            channel_id="channel-123",
            document_name="report.pdf",
            summary_type="detailed",
        )
        print(result.summary)
    """

    def __init__(self, summarization_port: SummarizationPort):
        """Initialize the use case with dependencies.

        Args:
            summarization_port: The summarization port implementation
        """
        self.summarization_port = summarization_port

    def execute(
        self,
        channel_id: str,
        document_name: str,
        summary_type: str = "short",
    ) -> SummarizeResult:
        """Execute document summarization.

        Args:
            channel_id: The channel (document store) containing the document
            document_name: The name of the document to summarize
            summary_type: 'short' (2-3 sentences) or 'detailed' (comprehensive)

        Returns:
            SummarizeResult with generated summary or error
        """
        try:
            result = self.summarization_port.summarize_document(
                store_name=channel_id,
                document_name=document_name,
                summary_type=summary_type,
            )

            return SummarizeResult(
                summary=result.summary,
                channel_id=channel_id,
                document_id=document_name,
                summary_type=summary_type,
                error=None,
            )

        except Exception as e:
            return SummarizeResult(
                summary="",
                channel_id=channel_id,
                document_id=document_name,
                summary_type=summary_type,
                error=str(e),
            )
