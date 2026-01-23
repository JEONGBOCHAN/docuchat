# -*- coding: utf-8 -*-
"""
Tests for GeminiCitationAdapter.

Tests the adapter implementation for citation search using GeminiService.
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.infrastructure.external.gemini.citation import GeminiCitationAdapter
from src.application.ports.citation_search import CitationDTO, CitationResultDTO
from src.services.gemini import GeminiService


class TestGeminiCitationAdapter:
    """Tests for GeminiCitationAdapter."""

    def test_search_with_citations_success(self):
        """Test successful citation search through adapter."""
        # Mock GeminiService
        mock_service = Mock(spec=GeminiService)
        mock_service.search_with_citations.return_value = {
            "response": "The answer is here. [1] More info. [2]",
            "response_plain": "The answer is here. More info.",
            "citations": [
                {
                    "index": 1,
                    "source": "document1.pdf",
                    "content": "Relevant content from doc 1",
                    "page": 5,
                    "start_index": 100,
                    "end_index": 200,
                },
                {
                    "index": 2,
                    "source": "document2.pdf",
                    "content": "Content from doc 2",
                    "page": 3,
                    "start_index": None,
                    "end_index": None,
                },
            ],
        }

        # Create adapter with mock service
        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        # Execute search
        result = adapter.search_with_citations("test-store", "What is this?")

        # Verify result type and content
        assert isinstance(result, CitationResultDTO)
        assert result.response == "The answer is here. [1] More info. [2]"
        assert result.response_plain == "The answer is here. More info."
        assert len(result.citations) == 2
        assert result.error is None

        # Verify citations were converted to DTOs
        assert isinstance(result.citations[0], CitationDTO)
        assert result.citations[0].index == 1
        assert result.citations[0].source == "document1.pdf"
        assert result.citations[0].content == "Relevant content from doc 1"
        assert result.citations[0].page == 5
        assert result.citations[0].start_index == 100
        assert result.citations[0].end_index == 200

        assert result.citations[1].index == 2
        assert result.citations[1].source == "document2.pdf"
        assert result.citations[1].page == 3

        # Verify service was called correctly
        mock_service.search_with_citations.assert_called_once_with("test-store", "What is this?")

    def test_search_with_citations_no_citations(self):
        """Test citation search when no citations are returned."""
        mock_service = Mock(spec=GeminiService)
        mock_service.search_with_citations.return_value = {
            "response": "General answer without sources.",
            "response_plain": "General answer without sources.",
            "citations": [],
        }

        adapter = GeminiCitationAdapter(gemini_service=mock_service)
        result = adapter.search_with_citations("test-store", "What is this?")

        assert result.response == "General answer without sources."
        assert result.citations == []
        assert result.error is None

    def test_search_with_citations_with_error(self):
        """Test citation search when service returns an error."""
        mock_service = Mock(spec=GeminiService)
        mock_service.search_with_citations.return_value = {
            "response": "",
            "response_plain": "",
            "citations": [],
            "error": "API Error occurred",
        }

        adapter = GeminiCitationAdapter(gemini_service=mock_service)
        result = adapter.search_with_citations("test-store", "What is this?")

        assert result.response == ""
        assert result.error == "API Error occurred"

    def test_search_with_citations_handles_missing_fields(self):
        """Test adapter handles citations with missing optional fields."""
        mock_service = Mock(spec=GeminiService)
        mock_service.search_with_citations.return_value = {
            "response": "Answer [1]",
            "response_plain": "Answer",
            "citations": [
                {
                    "index": 1,
                    # source is None
                    "source": None,
                    # content is None
                    "content": None,
                    # no page, start_index, end_index
                },
            ],
        }

        adapter = GeminiCitationAdapter(gemini_service=mock_service)
        result = adapter.search_with_citations("test-store", "What is this?")

        assert len(result.citations) == 1
        assert result.citations[0].source == "unknown"
        assert result.citations[0].content == ""
        assert result.citations[0].page is None


class TestGeminiCitationAdapterStreaming:
    """Tests for GeminiCitationAdapter streaming."""

    def test_search_with_citations_stream_success(self):
        """Test successful streaming citation search."""
        mock_service = Mock(spec=GeminiService)

        def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": "Hello "}
            yield {"type": "content", "text": "World!"}
            yield {
                "type": "citations",
                "response_with_citations": "Hello World! [1]",
                "citations": [
                    {
                        "index": 1,
                        "source": "doc.pdf",
                        "content": "test content",
                        "page": 1,
                    }
                ],
            }
            yield {"type": "done"}

        mock_service.search_with_citations_stream = mock_stream

        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        # Collect stream events
        events = list(adapter.search_with_citations_stream("test-store", "What is this?"))

        assert len(events) == 4
        assert events[0] == {"type": "content", "text": "Hello "}
        assert events[1] == {"type": "content", "text": "World!"}
        assert events[2]["type"] == "citations"
        assert events[2]["response_with_citations"] == "Hello World! [1]"
        assert len(events[2]["citations"]) == 1
        assert events[3] == {"type": "done"}

    def test_search_with_citations_stream_error_event(self):
        """Test streaming when error event is yielded."""
        mock_service = Mock(spec=GeminiService)

        def mock_stream(*args, **kwargs):
            yield {"type": "error", "error": "API Error"}

        mock_service.search_with_citations_stream = mock_stream

        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        events = list(adapter.search_with_citations_stream("test-store", "What is this?"))

        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["error"] == "API Error"

    def test_search_with_citations_stream_converts_citations(self):
        """Test that streaming citations are properly converted."""
        mock_service = Mock(spec=GeminiService)

        def mock_stream(*args, **kwargs):
            yield {
                "type": "citations",
                "response_with_citations": "Answer [1] [2]",
                "citations": [
                    {
                        "index": 1,
                        "source": "doc1.pdf",
                        "content": "Content 1",
                        "page": 5,
                        "start_index": 10,
                        "end_index": 50,
                    },
                    {
                        "source": None,  # Test missing source
                        "content": None,  # Test missing content
                    },
                ],
            }
            yield {"type": "done"}

        mock_service.search_with_citations_stream = mock_stream

        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        events = list(adapter.search_with_citations_stream("test-store", "What is this?"))

        assert len(events) == 2
        citations_event = events[0]

        assert citations_event["type"] == "citations"
        assert len(citations_event["citations"]) == 2

        # First citation should have all fields
        assert citations_event["citations"][0]["index"] == 1
        assert citations_event["citations"][0]["source"] == "doc1.pdf"
        assert citations_event["citations"][0]["content"] == "Content 1"
        assert citations_event["citations"][0]["page"] == 5

        # Second citation should have defaults for missing fields
        assert citations_event["citations"][1]["source"] == "unknown"
        assert citations_event["citations"][1]["content"] == ""

    def test_search_with_citations_stream_only_content(self):
        """Test streaming with only content events (no citations)."""
        mock_service = Mock(spec=GeminiService)

        def mock_stream(*args, **kwargs):
            yield {"type": "content", "text": "First "}
            yield {"type": "content", "text": "Second "}
            yield {"type": "content", "text": "Third"}
            yield {"type": "done"}

        mock_service.search_with_citations_stream = mock_stream

        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        events = list(adapter.search_with_citations_stream("test-store", "What is this?"))

        content_events = [e for e in events if e.get("type") == "content"]
        assert len(content_events) == 3
        assert content_events[0]["text"] == "First "
        assert content_events[1]["text"] == "Second "
        assert content_events[2]["text"] == "Third"


class TestGeminiCitationAdapterDTOConversion:
    """Tests for DTO conversion helper."""

    def test_convert_to_citation_dto_with_all_fields(self):
        """Test conversion with all fields present."""
        mock_service = Mock(spec=GeminiService)
        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        source = {
            "index": 1,
            "source": "test.pdf",
            "content": "Test content",
            "page": 10,
            "start_index": 100,
            "end_index": 200,
        }

        dto = adapter._convert_to_citation_dto(source, 1)

        assert isinstance(dto, CitationDTO)
        assert dto.index == 1
        assert dto.source == "test.pdf"
        assert dto.content == "Test content"
        assert dto.page == 10
        assert dto.start_index == 100
        assert dto.end_index == 200

    def test_convert_to_citation_dto_with_missing_fields(self):
        """Test conversion with missing optional fields."""
        mock_service = Mock(spec=GeminiService)
        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        source = {}

        dto = adapter._convert_to_citation_dto(source, 5)

        assert dto.index == 5  # Uses fallback index
        assert dto.source == "unknown"
        assert dto.content == ""
        assert dto.page is None
        assert dto.start_index is None
        assert dto.end_index is None

    def test_convert_to_citation_dto_prefers_source_index(self):
        """Test that source index takes precedence over fallback."""
        mock_service = Mock(spec=GeminiService)
        adapter = GeminiCitationAdapter(gemini_service=mock_service)

        source = {"index": 3, "source": "doc.pdf", "content": "Test"}

        dto = adapter._convert_to_citation_dto(source, 10)  # fallback is 10

        assert dto.index == 3  # Uses source index, not fallback
