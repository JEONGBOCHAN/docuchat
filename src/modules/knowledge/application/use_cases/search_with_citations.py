# -*- coding: utf-8 -*-
"""
Search With Citations Use Case.

This use case handles document search queries with inline citations.
It coordinates citation search through the port interface and returns
structured results with citation markers.
"""

from dataclasses import dataclass, field
from typing import Generator, Any

from src.application.ports.citation_search import (
    CitationSearchPort,
    CitationDTO,
    CitationResultDTO,
)


@dataclass
class CitationSearchResult:
    """Result of citation search use case.

    Attributes:
        response: Response text with inline citation markers [1], [2]
        response_plain: Response text without citation markers
        citations: List of citation DTOs
        error: Error message if search failed
    """

    response: str
    response_plain: str
    citations: list[CitationDTO] = field(default_factory=list)
    error: str | None = None


class SearchWithCitationsUseCase:
    """Use case for searching documents with inline citations.

    This use case coordinates:
    1. Citation search through the port interface
    2. Result formatting and error handling

    The citation search port abstracts the underlying implementation,
    allowing different search backends (Gemini, etc.) to be used
    interchangeably.

    Example:
        use_case = SearchWithCitationsUseCase(citation_port=gemini_adapter)
        result = use_case.execute(
            store_name="channel-123",
            query="What is the main topic?",
        )
    """

    def __init__(self, citation_port: CitationSearchPort):
        """Initialize the use case with dependencies.

        Args:
            citation_port: Citation search implementation
        """
        self.citation_port = citation_port

    def execute(
        self,
        store_name: str,
        query: str,
    ) -> CitationSearchResult:
        """Execute the citation search.

        Args:
            store_name: The document store to search
            query: The user's question

        Returns:
            CitationSearchResult with response and citations
        """
        try:
            result = self.citation_port.search_with_citations(store_name, query)

            return CitationSearchResult(
                response=result.response,
                response_plain=result.response_plain,
                citations=result.citations,
                error=result.error,
            )

        except Exception as e:
            return CitationSearchResult(
                response="",
                response_plain="",
                citations=[],
                error=str(e),
            )

    def execute_stream(
        self,
        store_name: str,
        query: str,
    ) -> Generator[dict[str, Any], None, None]:
        """Execute citation search with streaming response.

        This method streams events as the search processes,
        allowing real-time updates to be sent to clients via SSE.

        Args:
            store_name: The document store to search
            query: The user's question

        Yields:
            Event dictionaries with 'type' (content, citations, done, error)
        """
        try:
            yield from self.citation_port.search_with_citations_stream(
                store_name, query
            )
        except Exception as e:
            yield {"type": "error", "error": str(e)}
