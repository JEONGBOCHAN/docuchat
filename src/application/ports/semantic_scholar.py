# -*- coding: utf-8 -*-
"""
Semantic Scholar Search Port.

Defines the interface for Semantic Scholar paper search operations.
This abstracts the actual Semantic Scholar API implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SemanticScholarPaper:
    """A single Semantic Scholar paper result.

    Attributes:
        paper_id: The Semantic Scholar paper ID
        title: Title of the paper
        authors: List of author names
        abstract: Abstract of the paper
        year: Publication year
        citation_count: Number of citations
        reference_count: Number of references
        venue: Publication venue (journal/conference)
        url: URL to the paper page
        fields_of_study: List of fields (e.g., ["Computer Science", "Mathematics"])
        is_open_access: Whether the paper is open access
        external_ids: External identifiers (DOI, arXiv, etc.)
    """

    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    year: int | None
    citation_count: int
    reference_count: int
    venue: str
    url: str
    fields_of_study: list[str] = field(default_factory=list)
    is_open_access: bool = False
    external_ids: dict[str, str] = field(default_factory=dict)


@dataclass
class SemanticScholarAuthor:
    """A Semantic Scholar author profile.

    Attributes:
        author_id: The Semantic Scholar author ID
        name: Author's name
        affiliations: List of affiliations
        paper_count: Number of papers
        citation_count: Total citations
        h_index: h-index value
        url: URL to the author page
    """

    author_id: str
    name: str
    affiliations: list[str]
    paper_count: int
    citation_count: int
    h_index: int
    url: str


class SemanticScholarSearchPort(ABC):
    """Abstract interface for Semantic Scholar search operations.

    Implementations of this port handle searching the Semantic Scholar
    database for academic papers and authors. This provides access to
    citation analysis and author profiles.

    Example:
        search = SemanticScholarMcpAdapter()
        results = search.search("transformer attention mechanism", max_results=5)
        citations = search.get_citations(paper_id)
    """

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
        year_from: int | None = None,
        year_to: int | None = None,
        fields_of_study: list[str] | None = None,
    ) -> list[SemanticScholarPaper]:
        """Search Semantic Scholar for papers.

        Args:
            query: The search query
            max_results: Maximum number of results to return (default 5)
            year_from: Filter papers from this year
            year_to: Filter papers until this year
            fields_of_study: Filter by fields (e.g., ["Computer Science"])

        Returns:
            List of SemanticScholarPaper objects
        """
        pass

    @abstractmethod
    def get_paper(self, paper_id: str) -> SemanticScholarPaper | None:
        """Get a specific paper by its ID.

        Args:
            paper_id: The Semantic Scholar paper ID or external ID (DOI, arXiv ID)

        Returns:
            SemanticScholarPaper if found, None otherwise
        """
        pass

    @abstractmethod
    def get_author(self, author_id: str) -> SemanticScholarAuthor | None:
        """Get author details by ID.

        Args:
            author_id: The Semantic Scholar author ID

        Returns:
            SemanticScholarAuthor if found, None otherwise
        """
        pass

    @abstractmethod
    def get_citations(
        self,
        paper_id: str,
        max_results: int = 10,
    ) -> list[SemanticScholarPaper]:
        """Get papers that cite the given paper.

        Args:
            paper_id: The Semantic Scholar paper ID
            max_results: Maximum number of citing papers to return

        Returns:
            List of citing papers
        """
        pass

    @abstractmethod
    def get_references(
        self,
        paper_id: str,
        max_results: int = 10,
    ) -> list[SemanticScholarPaper]:
        """Get papers referenced by the given paper.

        Args:
            paper_id: The Semantic Scholar paper ID
            max_results: Maximum number of referenced papers to return

        Returns:
            List of referenced papers
        """
        pass
