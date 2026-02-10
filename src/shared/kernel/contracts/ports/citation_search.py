# -*- coding: utf-8 -*-
"""
Citation Search Port.

Defines the interface for document search with inline citations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Any


@dataclass
class CitationDTO:
    """A single citation with source information."""
    index: int
    source: str
    content: str
    page: int | None = None
    start_index: int | None = None
    end_index: int | None = None


@dataclass
class CitationResultDTO:
    """Result of citation search."""
    response: str  # Response with inline citation markers [1], [2]
    response_plain: str  # Response without markers
    citations: list[CitationDTO] = field(default_factory=list)
    error: str | None = None


class CitationSearchPort(ABC):
    """Abstract interface for citation search.

    Implementations search documents and return answers with citations.
    """

    @abstractmethod
    def search_with_citations(
        self,
        store_name: str,
        query: str,
    ) -> CitationResultDTO:
        """Search documents and generate answer with citations.

        Args:
            store_name: The document store to search
            query: The user's question

        Returns:
            CitationResultDTO with response and citations
        """
        pass

    @abstractmethod
    def search_with_citations_stream(
        self,
        store_name: str,
        query: str,
    ) -> Generator[dict[str, Any], None, None]:
        """Search documents with streaming response.

        Args:
            store_name: The document store to search
            query: The user's question

        Yields:
            Event dicts with 'type' (content, citations, done, error)
        """
        pass
