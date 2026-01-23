# -*- coding: utf-8 -*-
"""
Tests for Summarization Use Cases.

Tests the Clean Architecture use cases for document and channel summarization.
"""

import pytest
from unittest.mock import Mock

from src.application.use_cases.summarize import (
    SummarizeChannelUseCase,
    SummarizeDocumentUseCase,
    SummarizeResult,
)
from src.application.ports.summarization import SummarizationPort, SummaryDTO


class TestSummarizeChannelUseCase:
    """Tests for SummarizeChannelUseCase."""

    def test_execute_success(self):
        """Test successful channel summarization."""
        mock_port = Mock(spec=SummarizationPort)
        mock_port.summarize_channel.return_value = SummaryDTO(
            summary="This is a summary of all documents."
        )

        use_case = SummarizeChannelUseCase(summarization_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            summary_type="short",
        )

        assert result.error is None
        assert result.channel_id == "test-channel"
        assert result.summary == "This is a summary of all documents."
        assert result.summary_type == "short"

        mock_port.summarize_channel.assert_called_once_with(
            store_name="test-channel",
            summary_type="short",
        )

    def test_execute_detailed_summary(self):
        """Test detailed summary type."""
        mock_port = Mock(spec=SummarizationPort)
        mock_port.summarize_channel.return_value = SummaryDTO(
            summary="## Overview\nDetailed summary with sections."
        )

        use_case = SummarizeChannelUseCase(summarization_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            summary_type="detailed",
        )

        assert result.error is None
        assert "Detailed summary" in result.summary
        assert result.summary_type == "detailed"

    def test_execute_error_handling(self):
        """Test error handling during summarization."""
        mock_port = Mock(spec=SummarizationPort)
        mock_port.summarize_channel.side_effect = Exception("API error")

        use_case = SummarizeChannelUseCase(summarization_port=mock_port)

        result = use_case.execute(channel_id="test-channel")

        assert result.error is not None
        assert "API error" in result.error
        assert result.summary == ""
        assert result.channel_id == "test-channel"


class TestSummarizeDocumentUseCase:
    """Tests for SummarizeDocumentUseCase."""

    def test_execute_success(self):
        """Test successful document summarization."""
        mock_port = Mock(spec=SummarizationPort)
        mock_port.summarize_document.return_value = SummaryDTO(
            summary="This document discusses machine learning."
        )

        use_case = SummarizeDocumentUseCase(summarization_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            document_name="ml_paper.pdf",
            summary_type="short",
        )

        assert result.error is None
        assert result.channel_id == "test-channel"
        assert result.document_id == "ml_paper.pdf"
        assert result.summary == "This document discusses machine learning."

        mock_port.summarize_document.assert_called_once_with(
            store_name="test-channel",
            document_name="ml_paper.pdf",
            summary_type="short",
        )

    def test_execute_error_handling(self):
        """Test error handling during document summarization."""
        mock_port = Mock(spec=SummarizationPort)
        mock_port.summarize_document.side_effect = Exception("Document not found")

        use_case = SummarizeDocumentUseCase(summarization_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            document_name="missing.pdf",
        )

        assert result.error is not None
        assert "Document not found" in result.error
        assert result.summary == ""


class TestSummarizeResult:
    """Tests for SummarizeResult dataclass."""

    def test_default_values(self):
        """Test SummarizeResult with default values."""
        result = SummarizeResult()

        assert result.summary == ""
        assert result.channel_id is None
        assert result.document_id is None
        assert result.summary_type == "short"
        assert result.error is None

    def test_with_all_values(self):
        """Test SummarizeResult with all values."""
        result = SummarizeResult(
            summary="Test summary",
            channel_id="ch-1",
            document_id="doc-1",
            summary_type="detailed",
            error=None,
        )

        assert result.summary == "Test summary"
        assert result.channel_id == "ch-1"
        assert result.document_id == "doc-1"
        assert result.summary_type == "detailed"

    def test_with_error(self):
        """Test SummarizeResult with error."""
        result = SummarizeResult(
            channel_id="ch-1",
            error="Something went wrong",
        )

        assert result.error == "Something went wrong"
        assert result.summary == ""
