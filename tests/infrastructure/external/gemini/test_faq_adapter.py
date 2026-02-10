# -*- coding: utf-8 -*-
"""
Tests for GeminiFAQAdapter.

Tests the Gemini adapter implementation for FAQ generation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.infrastructure.external.gemini.faq import GeminiFAQAdapter
from src.shared.kernel.contracts.ports.faq_generation import FAQItemDTO


class TestGeminiFAQAdapter:
    """Tests for GeminiFAQAdapter."""

    def _create_mock_response(self, text: str):
        """Create a mock Gemini response."""
        mock_response = Mock()
        mock_response.text = text
        return mock_response

    def _create_mock_client(self, response_text: str):
        """Create a mock Gemini client."""
        mock_client = Mock()
        mock_response = self._create_mock_response(response_text)
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_generate_faq_success(self):
        """Test successful FAQ generation."""
        json_response = '''[
            {"question": "What is the main topic?", "answer": "The main topic is AI."},
            {"question": "How does it work?", "answer": "It works by learning."}
        ]'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store", count=2)

        assert len(result) == 2
        assert isinstance(result[0], FAQItemDTO)
        assert result[0].question == "What is the main topic?"
        assert result[0].answer == "The main topic is AI."
        assert result[1].question == "How does it work?"
        assert result[1].answer == "It works by learning."

        mock_client.models.generate_content.assert_called_once()

    def test_generate_faq_default_count(self):
        """Test FAQ generation with default count."""
        json_response = '[' + ','.join([f'{{"question": "Q{i}", "answer": "A{i}"}}' for i in range(5)]) + ']'
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store")

        assert len(result) == 5

    def test_generate_faq_empty_result(self):
        """Test FAQ generation with empty result."""
        mock_client = self._create_mock_client("[]")

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store", count=5)

        assert result == []

    def test_generate_faq_invalid_json(self):
        """Test FAQ generation with invalid JSON response."""
        mock_client = self._create_mock_client("This is not JSON")

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store", count=5)

        assert result == []

    def test_generate_faq_json_with_extra_text(self):
        """Test FAQ generation when JSON is embedded in extra text."""
        json_response = '''Here are the FAQs:
        [{"question": "Q1", "answer": "A1"}]
        That's all!'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store", count=1)

        assert len(result) == 1
        assert result[0].question == "Q1"

    def test_generate_faq_service_exception(self):
        """Test FAQ generation when client raises exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store", count=5)

        assert result == []

    def test_generate_faq_missing_fields(self):
        """Test FAQ generation with missing fields in items."""
        json_response = '''[
            {"question": "Q1"},
            {"answer": "A2"},
            {},
            {"question": "Q4", "answer": "A4"}
        ]'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store", count=5)

        assert len(result) == 4
        assert result[0].question == "Q1"
        assert result[0].answer == ""
        assert result[1].question == ""
        assert result[1].answer == "A2"
        assert result[2].question == ""
        assert result[2].answer == ""
        assert result[3].question == "Q4"
        assert result[3].answer == "A4"

    def test_generate_faq_null_response_text(self):
        """Test FAQ generation when response text is None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("test-store", count=5)

        assert result == []

    def test_adapter_creates_client_if_not_provided(self):
        """Test that adapter creates Gemini client via lazy-init."""
        with patch('src.infrastructure.external.gemini.faq.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            with patch('src.infrastructure.external.gemini.faq.genai.Client') as mock_client_class:
                adapter = GeminiFAQAdapter()
                adapter._get_client()
                mock_client_class.assert_called_once_with(api_key="test-api-key")


class TestGeminiFAQAdapterIntegration:
    """Integration tests for GeminiFAQAdapter (mocked)."""

    def test_full_workflow(self):
        """Test full FAQ generation workflow."""
        json_response = '''[
            {
                "question": "What is machine learning?",
                "answer": "Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed."
            },
            {
                "question": "What are neural networks?",
                "answer": "Neural networks are computing systems inspired by biological neural networks that can learn to perform tasks by considering examples."
            },
            {
                "question": "How is deep learning different from machine learning?",
                "answer": "Deep learning is a specialized subset of machine learning that uses multi-layered neural networks to progressively extract higher-level features from raw input."
            }
        ]'''

        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = json_response
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiFAQAdapter(client=mock_client)
        result = adapter.generate_faq("channel-123", count=3)

        assert len(result) == 3
        assert all(isinstance(item, FAQItemDTO) for item in result)
        assert all(item.question for item in result)
        assert all(item.answer for item in result)
