# -*- coding: utf-8 -*-
"""
Tests for GeminiCitationAdapter.

Tests the adapter implementation for citation search using Gemini API.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.infrastructure.external.gemini.citation import GeminiCitationAdapter
from src.application.ports.citation_search import CitationDTO, CitationResultDTO


class TestGeminiCitationAdapter:
    """Tests for GeminiCitationAdapter."""

    def _create_mock_client_with_grounding(self, text: str, sources: list):
        """Create a mock Gemini client with grounding metadata."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = text

        # Create grounding metadata
        mock_candidate = Mock()
        mock_metadata = Mock()

        grounding_chunks = []
        for i, src in enumerate(sources, start=1):
            chunk = Mock()
            ctx = Mock()
            ctx.title = src.get("source", "unknown")
            ctx.uri = src.get("source", "unknown")
            ctx.text = src.get("content", "")
            chunk.retrieved_context = ctx
            chunk.page = src.get("page")
            chunk.start_index = src.get("start_index")
            chunk.end_index = src.get("end_index")
            grounding_chunks.append(chunk)

        mock_metadata.grounding_chunks = grounding_chunks
        mock_candidate.grounding_metadata = mock_metadata
        mock_response.candidates = [mock_candidate]

        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_search_with_citations_success(self):
        """Test successful citation search through adapter."""
        sources = [
            {
                "source": "document1.pdf",
                "content": "Relevant content from doc 1",
                "page": 5,
                "start_index": 100,
                "end_index": 200,
            },
            {
                "source": "document2.pdf",
                "content": "Content from doc 2",
                "page": 3,
                "start_index": None,
                "end_index": None,
            },
        ]
        mock_client = self._create_mock_client_with_grounding(
            "The answer is here. More info.", sources
        )

        adapter = GeminiCitationAdapter(client=mock_client)
        result = adapter.search_with_citations("test-store", "What is this?")

        assert isinstance(result, CitationResultDTO)
        assert "The answer is here" in result.response_plain
        assert len(result.citations) == 2
        assert result.error is None

        assert isinstance(result.citations[0], CitationDTO)
        assert result.citations[0].index == 1
        assert result.citations[0].source == "document1.pdf"
        assert result.citations[0].content == "Relevant content from doc 1"
        assert result.citations[0].page == 5
        assert result.citations[0].start_index == 100
        assert result.citations[0].end_index == 200

        mock_client.models.generate_content.assert_called_once()

    def test_search_with_citations_no_citations(self):
        """Test citation search when no citations are returned."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "General answer without sources."

        # No grounding metadata
        mock_candidate = Mock()
        mock_candidate.grounding_metadata = None
        mock_response.candidates = [mock_candidate]

        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiCitationAdapter(client=mock_client)
        result = adapter.search_with_citations("test-store", "What is this?")

        assert result.response_plain == "General answer without sources."
        assert result.citations == []
        assert result.error is None

    def test_search_with_citations_exception(self):
        """Test citation search when client raises exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API Error")

        adapter = GeminiCitationAdapter(client=mock_client)
        result = adapter.search_with_citations("test-store", "What is this?")

        assert result.response == ""
        assert result.error == "API Error"

    def test_search_with_citations_handles_missing_fields(self):
        """Test adapter handles citations with missing optional fields."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Answer"

        mock_candidate = Mock()
        mock_metadata = Mock()

        chunk = Mock()
        ctx = Mock()
        ctx.title = None
        ctx.uri = None
        ctx.text = None
        chunk.retrieved_context = ctx
        # No page, start_index, end_index
        del chunk.page
        del chunk.start_index
        del chunk.end_index
        mock_metadata.grounding_chunks = [chunk]
        mock_candidate.grounding_metadata = mock_metadata
        mock_response.candidates = [mock_candidate]

        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiCitationAdapter(client=mock_client)
        result = adapter.search_with_citations("test-store", "What is this?")

        assert len(result.citations) == 1
        assert result.citations[0].source == "unknown"
        assert result.citations[0].content == ""


class TestGeminiCitationAdapterStreaming:
    """Tests for GeminiCitationAdapter streaming."""

    def test_search_with_citations_stream_success(self):
        """Test successful streaming citation search."""
        mock_client = Mock()

        def mock_stream(*args, **kwargs):
            # First chunk with text
            chunk1 = Mock()
            chunk1.text = "Hello "
            chunk1.candidates = None
            yield chunk1

            # Second chunk with text
            chunk2 = Mock()
            chunk2.text = "World!"
            chunk2.candidates = None
            yield chunk2

            # Final chunk with grounding metadata
            chunk3 = Mock()
            chunk3.text = None
            mock_candidate = Mock()
            mock_metadata = Mock()
            grounding_chunk = Mock()
            ctx = Mock()
            ctx.title = "doc.pdf"
            ctx.uri = "doc.pdf"
            ctx.text = "test content"
            grounding_chunk.retrieved_context = ctx
            grounding_chunk.page = 1
            mock_metadata.grounding_chunks = [grounding_chunk]
            mock_candidate.grounding_metadata = mock_metadata
            chunk3.candidates = [mock_candidate]
            yield chunk3

        mock_client.models.generate_content_stream.return_value = mock_stream()

        adapter = GeminiCitationAdapter(client=mock_client)
        events = list(adapter.search_with_citations_stream("test-store", "What is this?"))

        content_events = [e for e in events if e.get("type") == "content"]
        assert len(content_events) == 2
        assert content_events[0]["text"] == "Hello "
        assert content_events[1]["text"] == "World!"

        citation_events = [e for e in events if e.get("type") == "citations"]
        assert len(citation_events) == 1
        assert len(citation_events[0]["citations"]) == 1

        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1

    def test_search_with_citations_stream_error(self):
        """Test streaming when error occurs."""
        mock_client = Mock()
        mock_client.models.generate_content_stream.side_effect = Exception("API Error")

        adapter = GeminiCitationAdapter(client=mock_client)
        events = list(adapter.search_with_citations_stream("test-store", "What is this?"))

        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["error"] == "API Error"


class TestGeminiCitationAdapterDTOConversion:
    """Tests for DTO conversion helper."""

    def test_convert_to_citation_dto_with_all_fields(self):
        """Test conversion with all fields present."""
        mock_client = Mock()
        adapter = GeminiCitationAdapter(client=mock_client)

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
        mock_client = Mock()
        adapter = GeminiCitationAdapter(client=mock_client)

        source = {}

        dto = adapter._convert_to_citation_dto(source, 5)

        assert dto.index == 5
        assert dto.source == "unknown"
        assert dto.content == ""
        assert dto.page is None
        assert dto.start_index is None
        assert dto.end_index is None

    def test_adapter_creates_client_if_not_provided(self):
        """Test that adapter creates Gemini client via lazy-init."""
        with patch('src.infrastructure.external.gemini.citation.get_settings') as mock_settings:
            mock_settings.return_value.google_api_key = "test-api-key"
            with patch('src.infrastructure.external.gemini.citation.genai.Client') as mock_client_class:
                adapter = GeminiCitationAdapter()
                adapter._get_client()
                mock_client_class.assert_called_once_with(api_key="test-api-key")
