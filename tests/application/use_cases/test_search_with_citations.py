# -*- coding: utf-8 -*-
"""
Tests for SearchWithCitationsUseCase.

Tests the Clean Architecture use case for document search with inline citations.
"""

import pytest
from unittest.mock import Mock

from src.application.use_cases.search_with_citations import (
    SearchWithCitationsUseCase,
    CitationSearchResult,
)
from src.application.ports.citation_search import (
    CitationSearchPort,
    CitationDTO,
    CitationResultDTO,
)


class TestSearchWithCitationsUseCase:
    """Tests for SearchWithCitationsUseCase."""

    def test_execute_success(self):
        """Test successful citation search execution."""
        # Mock citation port
        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations.return_value = CitationResultDTO(
            response="The answer is here. [1] More info. [2]",
            response_plain="The answer is here. More info.",
            citations=[
                CitationDTO(
                    index=1,
                    source="document1.pdf",
                    content="Relevant content from doc 1",
                    page=5,
                    start_index=100,
                    end_index=200,
                ),
                CitationDTO(
                    index=2,
                    source="document2.pdf",
                    content="Content from doc 2",
                    page=3,
                ),
            ],
            error=None,
        )

        # Create use case
        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        # Execute
        result = use_case.execute(
            store_name="test-store",
            query="What is the main topic?",
        )

        # Verify result
        assert result.response == "The answer is here. [1] More info. [2]"
        assert result.response_plain == "The answer is here. More info."
        assert len(result.citations) == 2
        assert result.citations[0].index == 1
        assert result.citations[0].source == "document1.pdf"
        assert result.citations[0].page == 5
        assert result.citations[1].index == 2
        assert result.citations[1].source == "document2.pdf"
        assert result.error is None

        # Verify port was called correctly
        mock_port.search_with_citations.assert_called_once_with("test-store", "What is the main topic?")

    def test_execute_with_no_citations(self):
        """Test execution when no citations are returned."""
        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations.return_value = CitationResultDTO(
            response="General answer without specific sources.",
            response_plain="General answer without specific sources.",
            citations=[],
            error=None,
        )

        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        result = use_case.execute(
            store_name="test-store",
            query="What is this about?",
        )

        assert result.response == "General answer without specific sources."
        assert result.citations == []
        assert result.error is None

    def test_execute_with_error(self):
        """Test execution when API returns an error."""
        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations.return_value = CitationResultDTO(
            response="",
            response_plain="",
            citations=[],
            error="API Error occurred",
        )

        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        result = use_case.execute(
            store_name="test-store",
            query="Test query",
        )

        assert result.response == ""
        assert result.error == "API Error occurred"

    def test_execute_handles_exception(self):
        """Test that exceptions are handled gracefully."""
        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations.side_effect = Exception("Unexpected error")

        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        result = use_case.execute(
            store_name="test-store",
            query="Test query",
        )

        assert result.response == ""
        assert result.citations == []
        assert result.error is not None
        assert "Unexpected error" in result.error


class TestSearchWithCitationsUseCaseStreaming:
    """Tests for SearchWithCitationsUseCase.execute_stream()."""

    def test_execute_stream_success(self):
        """Test successful streaming citation search."""
        # Define stream events
        stream_events = [
            {"type": "content", "text": "Hello "},
            {"type": "content", "text": "World!"},
            {
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
            },
            {"type": "done"},
        ]

        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations_stream.return_value = iter(stream_events)

        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        # Collect streamed events
        events = list(use_case.execute_stream(
            store_name="test-store",
            query="Test query",
        ))

        assert len(events) == 4
        assert events[0] == {"type": "content", "text": "Hello "}
        assert events[1] == {"type": "content", "text": "World!"}
        assert events[2]["type"] == "citations"
        assert events[2]["response_with_citations"] == "Hello World! [1]"
        assert len(events[2]["citations"]) == 1
        assert events[3] == {"type": "done"}

        # Verify port was called
        mock_port.search_with_citations_stream.assert_called_once_with("test-store", "Test query")

    def test_execute_stream_with_error_event(self):
        """Test streaming when an error event is yielded."""
        stream_events = [
            {"type": "error", "error": "API Error"},
        ]

        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations_stream.return_value = iter(stream_events)

        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        events = list(use_case.execute_stream(
            store_name="test-store",
            query="Test query",
        ))

        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["error"] == "API Error"

    def test_execute_stream_handles_exception(self):
        """Test that exceptions during streaming are handled."""
        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations_stream.side_effect = Exception("Stream failed")

        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        events = list(use_case.execute_stream(
            store_name="test-store",
            query="Test query",
        ))

        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert "Stream failed" in events[0]["error"]

    def test_execute_stream_yields_content_events(self):
        """Test that content events are properly yielded."""
        stream_events = [
            {"type": "content", "text": "First chunk"},
            {"type": "content", "text": "Second chunk"},
            {"type": "content", "text": "Third chunk"},
            {"type": "done"},
        ]

        mock_port = Mock(spec=CitationSearchPort)
        mock_port.search_with_citations_stream.return_value = iter(stream_events)

        use_case = SearchWithCitationsUseCase(citation_port=mock_port)

        events = list(use_case.execute_stream(
            store_name="test-store",
            query="Test query",
        ))

        content_events = [e for e in events if e.get("type") == "content"]
        assert len(content_events) == 3
        assert content_events[0]["text"] == "First chunk"
        assert content_events[1]["text"] == "Second chunk"
        assert content_events[2]["text"] == "Third chunk"


class TestCitationSearchResult:
    """Tests for CitationSearchResult dataclass."""

    def test_citation_search_result_defaults(self):
        """Test CitationSearchResult with defaults."""
        result = CitationSearchResult(
            response="Test response",
            response_plain="Test response",
        )

        assert result.response == "Test response"
        assert result.response_plain == "Test response"
        assert result.citations == []
        assert result.error is None

    def test_citation_search_result_with_values(self):
        """Test CitationSearchResult with all values."""
        citations = [
            CitationDTO(index=1, source="doc.pdf", content="Content"),
        ]

        result = CitationSearchResult(
            response="Response [1]",
            response_plain="Response",
            citations=citations,
            error=None,
        )

        assert result.response == "Response [1]"
        assert result.response_plain == "Response"
        assert len(result.citations) == 1
        assert result.citations[0].source == "doc.pdf"
        assert result.error is None

    def test_citation_search_result_with_error(self):
        """Test CitationSearchResult with error."""
        result = CitationSearchResult(
            response="",
            response_plain="",
            citations=[],
            error="Something went wrong",
        )

        assert result.response == ""
        assert result.error == "Something went wrong"
