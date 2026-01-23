# -*- coding: utf-8 -*-
"""
Tests for GenerateFAQUseCase.

Tests the Clean Architecture use case for generating FAQ items.
"""

import pytest
from unittest.mock import Mock

from src.application.use_cases.generate_faq import GenerateFAQUseCase, FAQResult
from src.application.ports.faq_generation import FAQGenerationPort, FAQItemDTO


class TestGenerateFAQUseCase:
    """Tests for GenerateFAQUseCase."""

    def test_execute_success(self):
        """Test successful FAQ generation."""
        # Mock FAQ port
        mock_port = Mock(spec=FAQGenerationPort)
        mock_port.generate_faq.return_value = [
            FAQItemDTO(question="What is AI?", answer="AI is artificial intelligence."),
            FAQItemDTO(question="How does ML work?", answer="ML learns from data."),
        ]

        # Create use case
        use_case = GenerateFAQUseCase(faq_port=mock_port)

        # Execute
        result = use_case.execute(
            channel_id="test-channel",
            count=2,
        )

        # Verify result
        assert result.error is None
        assert result.channel_id == "test-channel"
        assert len(result.items) == 2
        assert result.items[0].question == "What is AI?"
        assert result.items[0].answer == "AI is artificial intelligence."
        assert result.items[1].question == "How does ML work?"
        assert result.items[1].answer == "ML learns from data."

        # Verify port was called correctly
        mock_port.generate_faq.assert_called_once_with(
            store_name="test-channel",
            count=2,
        )

    def test_execute_with_default_count(self):
        """Test FAQ generation with default count."""
        # Mock port
        mock_port = Mock(spec=FAQGenerationPort)
        mock_port.generate_faq.return_value = [
            FAQItemDTO(question=f"Question {i}", answer=f"Answer {i}")
            for i in range(5)
        ]

        use_case = GenerateFAQUseCase(faq_port=mock_port)

        # Execute without specifying count
        result = use_case.execute(channel_id="test-channel")

        # Verify default count is 5
        mock_port.generate_faq.assert_called_once_with(
            store_name="test-channel",
            count=5,
        )
        assert len(result.items) == 5

    def test_execute_empty_result(self):
        """Test FAQ generation returns empty list."""
        mock_port = Mock(spec=FAQGenerationPort)
        mock_port.generate_faq.return_value = []

        use_case = GenerateFAQUseCase(faq_port=mock_port)

        result = use_case.execute(channel_id="test-channel", count=5)

        assert result.error is None
        assert result.items == []
        assert result.channel_id == "test-channel"

    def test_execute_error_handling(self):
        """Test error handling during FAQ generation."""
        # Mock port that raises exception
        mock_port = Mock(spec=FAQGenerationPort)
        mock_port.generate_faq.side_effect = Exception("API error occurred")

        use_case = GenerateFAQUseCase(faq_port=mock_port)

        # Execute
        result = use_case.execute(channel_id="test-channel", count=5)

        # Verify error is captured
        assert result.error is not None
        assert "API error occurred" in result.error
        assert result.items == []
        assert result.channel_id == "test-channel"

    def test_execute_various_counts(self):
        """Test FAQ generation with various count values."""
        mock_port = Mock(spec=FAQGenerationPort)

        use_case = GenerateFAQUseCase(faq_port=mock_port)

        # Test with different counts
        for count in [1, 5, 10, 20]:
            mock_port.generate_faq.return_value = [
                FAQItemDTO(question=f"Q{i}", answer=f"A{i}")
                for i in range(count)
            ]

            result = use_case.execute(channel_id="test-channel", count=count)

            assert len(result.items) == count


class TestFAQResult:
    """Tests for FAQResult dataclass."""

    def test_faq_result_defaults(self):
        """Test FAQResult with defaults."""
        result = FAQResult()

        assert result.items == []
        assert result.channel_id is None
        assert result.error is None

    def test_faq_result_with_values(self):
        """Test FAQResult with all values."""
        items = [
            FAQItemDTO(question="Q1", answer="A1"),
            FAQItemDTO(question="Q2", answer="A2"),
        ]

        result = FAQResult(
            items=items,
            channel_id="test-channel",
            error=None,
        )

        assert len(result.items) == 2
        assert result.channel_id == "test-channel"
        assert result.error is None

    def test_faq_result_with_error(self):
        """Test FAQResult with error."""
        result = FAQResult(
            items=[],
            channel_id="test-channel",
            error="Something went wrong",
        )

        assert result.items == []
        assert result.channel_id == "test-channel"
        assert result.error == "Something went wrong"


class TestFAQItemDTO:
    """Tests for FAQItemDTO dataclass."""

    def test_faq_item_dto_creation(self):
        """Test creating FAQItemDTO."""
        item = FAQItemDTO(
            question="What is machine learning?",
            answer="Machine learning is a subset of AI.",
        )

        assert item.question == "What is machine learning?"
        assert item.answer == "Machine learning is a subset of AI."

    def test_faq_item_dto_empty_strings(self):
        """Test FAQItemDTO with empty strings."""
        item = FAQItemDTO(question="", answer="")

        assert item.question == ""
        assert item.answer == ""
