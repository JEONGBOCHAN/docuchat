# -*- coding: utf-8 -*-
"""
Crossref Search Port.

Defines the interface for Crossref metadata search operations.
This abstracts the actual Crossref API implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CrossrefWork:
    """A single Crossref work (publication) result.

    Attributes:
        doi: Digital Object Identifier
        title: Title of the work
        authors: List of author names
        abstract: Abstract (if available)
        type: Work type (journal-article, book-chapter, etc.)
        published_date: Publication date string (YYYY-MM-DD or YYYY)
        container_title: Journal or book title
        publisher: Publisher name
        volume: Volume number
        issue: Issue number
        page: Page range
        url: URL to the work
        is_referenced_by_count: Citation count
        references_count: Number of references
        license: License information
        subject: Subject categories
    """

    doi: str
    title: str
    authors: list[str]
    abstract: str
    type: str
    published_date: str
    container_title: str
    publisher: str
    volume: str
    issue: str
    page: str
    url: str
    is_referenced_by_count: int = 0
    references_count: int = 0
    license: str = ""
    subject: list[str] = field(default_factory=list)


@dataclass
class CrossrefJournal:
    """A Crossref journal entry.

    Attributes:
        issn: ISSN identifier(s)
        title: Journal title
        publisher: Publisher name
        subject: Subject categories
        counts: Article counts
    """

    issn: list[str]
    title: str
    publisher: str
    subject: list[str]
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class CrossrefFunder:
    """A Crossref funder entry.

    Attributes:
        funder_id: Funder DOI or ID
        name: Funder name
        location: Funder location
        alt_names: Alternative names
        work_count: Number of funded works
    """

    funder_id: str
    name: str
    location: str
    alt_names: list[str]
    work_count: int


class CrossrefSearchPort(ABC):
    """Abstract interface for Crossref search operations.

    Implementations of this port handle searching the Crossref database
    for publication metadata. This provides access to DOI-based metadata,
    journal information, and funder data.

    Example:
        search = CrossrefAdapter()
        results = search.search("machine learning", max_results=5)
        work = search.get_work_by_doi("10.1234/example")
    """

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
        sort: str = "relevance",
        filter_type: str | None = None,
    ) -> list[CrossrefWork]:
        """Search Crossref for works.

        Args:
            query: The search query (title, author, or keywords)
            max_results: Maximum number of results to return (default 5)
            sort: Sort order - "relevance", "published", "cited"
            filter_type: Filter by type (e.g., "journal-article", "book-chapter")

        Returns:
            List of CrossrefWork objects
        """
        pass

    @abstractmethod
    def get_work_by_doi(self, doi: str) -> CrossrefWork | None:
        """Get work metadata by DOI.

        Args:
            doi: The Digital Object Identifier

        Returns:
            CrossrefWork if found, None otherwise
        """
        pass

    @abstractmethod
    def search_journals(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[CrossrefJournal]:
        """Search for journals.

        Args:
            query: The search query
            max_results: Maximum number of results to return

        Returns:
            List of CrossrefJournal objects
        """
        pass

    @abstractmethod
    def search_funders(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[CrossrefFunder]:
        """Search for funding organizations.

        Args:
            query: The search query
            max_results: Maximum number of results to return

        Returns:
            List of CrossrefFunder objects
        """
        pass
