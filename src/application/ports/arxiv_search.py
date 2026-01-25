# -*- coding: utf-8 -*-
"""
arXiv Search Port.

Defines the interface for arXiv paper search operations.
This abstracts the actual arXiv API implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ArxivPaperResult:
    """A single arXiv paper result.

    Attributes:
        arxiv_id: The arXiv paper ID (e.g., "2301.00001")
        title: Title of the paper
        authors: List of author names
        summary: Abstract/summary of the paper
        published: Publication date string
        updated: Last update date string
        pdf_url: URL to the PDF
        primary_category: Primary arXiv category (e.g., "cs.AI")
        categories: List of all categories
    """

    arxiv_id: str
    title: str
    authors: list[str]
    summary: str
    published: str
    updated: str
    pdf_url: str
    primary_category: str
    categories: list[str]


class ArxivSearchPort(ABC):
    """Abstract interface for arXiv paper search operations.

    Implementations of this port handle searching the arXiv repository
    for academic papers. This allows the application to search papers
    without being coupled to a specific implementation.

    Example:
        search = ArxivAdapter()
        results = search.search("transformer neural networks", max_results=5)
    """

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
        sort_by: str = "relevance",
        category: str | None = None,
    ) -> list[ArxivPaperResult]:
        """Search arXiv for papers.

        Args:
            query: The search query
            max_results: Maximum number of results to return (default 5)
            sort_by: Sort order - "relevance", "lastUpdatedDate", "submittedDate"
            category: Optional arXiv category filter (e.g., "cs.AI", "cs.CL")

        Returns:
            List of ArxivPaperResult objects
        """
        pass

    @abstractmethod
    def get_paper(self, arxiv_id: str) -> ArxivPaperResult | None:
        """Get a specific paper by its arXiv ID.

        Args:
            arxiv_id: The arXiv paper ID (e.g., "2301.00001" or "2301.00001v1")

        Returns:
            ArxivPaperResult if found, None otherwise
        """
        pass
