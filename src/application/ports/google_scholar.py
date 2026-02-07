# -*- coding: utf-8 -*-
"""
Google Scholar Search Port.

Defines the interface for Google Scholar paper search operations.
This abstracts the actual Google Scholar API implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GoogleScholarResult:
    """A single Google Scholar search result.

    Attributes:
        title: Title of the paper
        authors: List of author names
        year: Publication year
        citation_count: Number of citations
        snippet: Brief description or abstract snippet
        url: URL to the paper page
        pub_url: Direct URL to the publication
        venue: Journal or conference name
    """

    title: str
    authors: list[str]
    year: int | None
    citation_count: int
    snippet: str
    url: str
    pub_url: str = ""
    venue: str = ""


class GoogleScholarSearchPort(ABC):
    """Abstract interface for Google Scholar search operations.

    Implementations of this port handle searching Google Scholar
    for academic papers. This allows the application to search papers
    without being coupled to a specific implementation.

    Example:
        search = GoogleScholarAdapter()
        results = search.search("transformer neural networks", max_results=5)
    """

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[GoogleScholarResult]:
        """Search Google Scholar for papers.

        Args:
            query: The search query
            max_results: Maximum number of results to return (default 5)

        Returns:
            List of GoogleScholarResult objects
        """
        pass

    @abstractmethod
    def search_advanced(
        self,
        query: str,
        author: str | None = None,
        year_range: tuple[int, int] | None = None,
        max_results: int = 5,
    ) -> list[GoogleScholarResult]:
        """Advanced search with filtering options.

        Args:
            query: The search query
            author: Optional author name filter
            year_range: Optional (start_year, end_year) filter
            max_results: Maximum number of results to return (default 5)

        Returns:
            List of GoogleScholarResult objects
        """
        pass
