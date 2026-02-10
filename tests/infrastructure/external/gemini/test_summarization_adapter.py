# -*- coding: utf-8 -*-
"""
Tests for GeminiSummarizationAdapter.

Tests the Gemini adapter implementation for document summarization.
"""

import pytest
from unittest.mock import Mock, patch

from src.infrastructure.external.gemini.summarization import GeminiSummarizationAdapter
from src.application.ports.summarization import SummaryDTO


class TestGeminiSummarizationAdapter:
    """Tests for GeminiSummarizationAdapter."""

    def _create_mock_client(self, response_text: str):
        """Create a mock Gemini client."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = response_text
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_summarize_channel_success(self):
        """Test successful channel summarization."""
        mock_client = self._create_mock_client(
            "This is a comprehensive summary of all documents."
        )

        adapter = GeminiSummarizationAdapter(client=mock_client)

        result = adapter.summarize_channel("test-store", summary_type="short")

        assert isinstance(result, SummaryDTO)
        assert result.summary == "This is a comprehensive summary of all documents."

        mock_client.models.generate_content.assert_called_once()

    def test_summarize_channel_detailed(self):
        """Test detailed channel summarization."""
        mock_client = self._create_mock_client(
            "## Overview\nDetailed analysis of all documents..."
        )

        adapter = GeminiSummarizationAdapter(client=mock_client)

        result = adapter.summarize_channel("test-store", summary_type="detailed")

        assert "Detailed analysis" in result.summary

    def test_summarize_channel_with_exception(self):
        """Test channel summarization with exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API quota exceeded")

        adapter = GeminiSummarizationAdapter(client=mock_client)

        with pytest.raises(Exception) as exc_info:
            adapter.summarize_channel("test-store")

        assert "API quota exceeded" in str(exc_info.value)

    def test_summarize_channel_empty_response(self):
        """Test channel summarization with empty response."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiSummarizationAdapter(client=mock_client)

        result = adapter.summarize_channel("test-store")

        assert result.summary == ""

    def test_summarize_document_success(self):
        """Test successful document summarization."""
        mock_client = self._create_mock_client(
            "This document covers machine learning basics."
        )

        adapter = GeminiSummarizationAdapter(client=mock_client)

        result = adapter.summarize_document(
            "test-store",
            document_name="ml_intro.pdf",
            summary_type="short",
        )

        assert isinstance(result, SummaryDTO)
        assert result.summary == "This document covers machine learning basics."

        mock_client.models.generate_content.assert_called_once()

    def test_summarize_document_detailed(self):
        """Test detailed document summarization."""
        mock_client = self._create_mock_client(
            "## Overview\nThis document provides comprehensive coverage of ML..."
        )

        adapter = GeminiSummarizationAdapter(client=mock_client)

        result = adapter.summarize_document(
            "test-store",
            document_name="ml_intro.pdf",
            summary_type="detailed",
        )

        assert "comprehensive coverage" in result.summary

    def test_summarize_document_with_exception(self):
        """Test document summarization with exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("Document not found")

        adapter = GeminiSummarizationAdapter(client=mock_client)

        with pytest.raises(Exception) as exc_info:
            adapter.summarize_document("test-store", "missing.pdf")

        assert "Document not found" in str(exc_info.value)

    def test_adapter_creates_client_if_not_provided(self):
        """Test that adapter creates Gemini client via lazy-init."""
        with patch('src.infrastructure.external.gemini.summarization.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            with patch('src.infrastructure.external.gemini.summarization.genai.Client') as mock_client_class:
                adapter = GeminiSummarizationAdapter()
                adapter._get_client()
                mock_client_class.assert_called_once_with(api_key="test-api-key")
