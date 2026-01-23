# -*- coding: utf-8 -*-
"""
Tests for GeminiFAQAdapter.

Tests the Gemini adapter implementation for FAQ generation.
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.infrastructure.external.gemini.faq import GeminiFAQAdapter
from src.application.ports.faq_generation import FAQItemDTO
from src.services.gemini import GeminiService


class TestGeminiFAQAdapter:
    """Tests for GeminiFAQAdapter."""

    def test_generate_faq_success(self):
        """Test successful FAQ generation."""
        # Mock GeminiService
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.return_value = {
            "items": [
                {"question": "What is the main topic?", "answer": "The main topic is AI."},
                {"question": "How does it work?", "answer": "It works by learning."},
            ],
        }

        # Create adapter
        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        # Execute
        result = adapter.generate_faq("test-store", count=2)

        # Verify result
        assert len(result) == 2
        assert isinstance(result[0], FAQItemDTO)
        assert result[0].question == "What is the main topic?"
        assert result[0].answer == "The main topic is AI."
        assert result[1].question == "How does it work?"
        assert result[1].answer == "It works by learning."

        # Verify service was called correctly
        mock_service.generate_faq.assert_called_once_with("test-store", count=2)

    def test_generate_faq_default_count(self):
        """Test FAQ generation with default count."""
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.return_value = {
            "items": [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(5)],
        }

        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        # Call without count (should default to 5)
        result = adapter.generate_faq("test-store")

        mock_service.generate_faq.assert_called_once_with("test-store", count=5)
        assert len(result) == 5

    def test_generate_faq_empty_result(self):
        """Test FAQ generation with empty result."""
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.return_value = {"items": []}

        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        result = adapter.generate_faq("test-store", count=5)

        assert result == []

    def test_generate_faq_with_error_in_response(self):
        """Test FAQ generation when response contains error but also items."""
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.return_value = {
            "items": [{"question": "Q1", "answer": "A1"}],
            "error": "Partial error",
        }

        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        # Should still return items even with error
        result = adapter.generate_faq("test-store", count=5)

        assert len(result) == 1
        assert result[0].question == "Q1"

    def test_generate_faq_service_exception(self):
        """Test FAQ generation when service raises exception."""
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.side_effect = Exception("API error")

        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        # Should return empty list on exception
        result = adapter.generate_faq("test-store", count=5)

        assert result == []

    def test_generate_faq_missing_fields(self):
        """Test FAQ generation with missing fields in items."""
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.return_value = {
            "items": [
                {"question": "Q1"},  # Missing answer
                {"answer": "A2"},  # Missing question
                {},  # Missing both
                {"question": "Q4", "answer": "A4"},  # Complete
            ],
        }

        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        result = adapter.generate_faq("test-store", count=5)

        # All items should be converted with empty strings for missing fields
        assert len(result) == 4
        assert result[0].question == "Q1"
        assert result[0].answer == ""
        assert result[1].question == ""
        assert result[1].answer == "A2"
        assert result[2].question == ""
        assert result[2].answer == ""
        assert result[3].question == "Q4"
        assert result[3].answer == "A4"

    def test_generate_faq_missing_items_key(self):
        """Test FAQ generation when items key is missing."""
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.return_value = {}

        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        result = adapter.generate_faq("test-store", count=5)

        assert result == []

    def test_adapter_creates_service_if_not_provided(self):
        """Test that adapter creates GeminiService if not provided."""
        # This test verifies the constructor works without explicit service
        # The adapter should create a GeminiService internally
        adapter = GeminiFAQAdapter()  # No service provided

        # Verify adapter was created and has a service
        assert adapter._service is not None
        assert isinstance(adapter._service, GeminiService)


class TestGeminiFAQAdapterIntegration:
    """Integration tests for GeminiFAQAdapter (mocked)."""

    def test_full_workflow(self):
        """Test full FAQ generation workflow."""
        # Setup mock service with realistic data
        mock_service = Mock(spec=GeminiService)
        mock_service.generate_faq.return_value = {
            "items": [
                {
                    "question": "What is machine learning?",
                    "answer": "Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed.",
                },
                {
                    "question": "What are neural networks?",
                    "answer": "Neural networks are computing systems inspired by biological neural networks that can learn to perform tasks by considering examples.",
                },
                {
                    "question": "How is deep learning different from machine learning?",
                    "answer": "Deep learning is a specialized subset of machine learning that uses multi-layered neural networks to progressively extract higher-level features from raw input.",
                },
            ],
        }

        adapter = GeminiFAQAdapter(gemini_service=mock_service)

        result = adapter.generate_faq("channel-123", count=3)

        assert len(result) == 3
        assert all(isinstance(item, FAQItemDTO) for item in result)
        assert all(item.question for item in result)
        assert all(item.answer for item in result)
