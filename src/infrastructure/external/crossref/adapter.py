# -*- coding: utf-8 -*-
"""
Crossref Adapter.

Implements CrossrefSearchPort using the habanero library.
This adapter provides access to Crossref's publication metadata,
including DOI lookup, journal search, and funder information.

Note: When a Crossref MCP server becomes available on PyPI,
this can be replaced with an MCP-based adapter while keeping
the same port interface.
"""

import logging
from typing import Any

from habanero import Crossref

from src.shared.kernel.contracts.ports.crossref import (
    CrossrefSearchPort,
    CrossrefWork,
    CrossrefJournal,
    CrossrefFunder,
)

logger = logging.getLogger(__name__)


class CrossrefAdapter(CrossrefSearchPort):
    """CrossrefSearchPort implementation using habanero library.

    This adapter wraps the habanero library to provide publication
    metadata search through the Clean Architecture port interface.

    Features:
        - Search works by query (title, author, keywords)
        - Get work metadata by DOI
        - Search journals
        - Search funding organizations

    Example:
        adapter = CrossrefAdapter()
        results = adapter.search("machine learning", max_results=5)
        work = adapter.get_work_by_doi("10.1038/nature12373")

    Note:
        Providing an email address improves API priority (polite pool).
    """

    def __init__(self, email: str | None = None):
        """Initialize the Crossref adapter.

        Args:
            email: Optional email for polite pool access (higher priority).
                  Crossref gives better rate limits to identified users.
        """
        self._client = Crossref(mailto=email) if email else Crossref()

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
        try:
            # Map sort parameter
            sort_map = {
                "relevance": "relevance",
                "published": "published",
                "cited": "is-referenced-by-count",
            }
            sort_field = sort_map.get(sort, "relevance")

            # Build filter if type specified
            filter_dict = {}
            if filter_type:
                filter_dict["type"] = filter_type

            # Execute search
            result = self._client.works(
                query=query,
                limit=max_results,
                sort=sort_field,
                order="desc",
                filter=filter_dict if filter_dict else None,
            )

            works = []
            items = result.get("message", {}).get("items", [])

            for item in items:
                try:
                    works.append(self._convert_to_work(item))
                except Exception as e:
                    logger.warning(f"Failed to convert work: {e}")
                    continue

            logger.info(f"Crossref search for '{query}' returned {len(works)} results")
            return works

        except Exception as e:
            logger.error(f"Crossref search failed: {e}")
            return []

    def get_work_by_doi(self, doi: str) -> CrossrefWork | None:
        """Get work metadata by DOI.

        Args:
            doi: The Digital Object Identifier

        Returns:
            CrossrefWork if found, None otherwise
        """
        try:
            # Clean DOI (remove URL prefix if present)
            if doi.startswith("https://doi.org/"):
                doi = doi[16:]
            elif doi.startswith("http://doi.org/"):
                doi = doi[15:]
            elif doi.startswith("doi:"):
                doi = doi[4:]

            result = self._client.works(ids=doi)

            if result and "message" in result:
                return self._convert_to_work(result["message"])

            logger.warning(f"Work not found for DOI: {doi}")
            return None

        except Exception as e:
            logger.error(f"Crossref get_work_by_doi failed: {e}")
            return None

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
        try:
            result = self._client.journals(query=query, limit=max_results)

            journals = []
            items = result.get("message", {}).get("items", [])

            for item in items:
                try:
                    journals.append(self._convert_to_journal(item))
                except Exception as e:
                    logger.warning(f"Failed to convert journal: {e}")
                    continue

            logger.info(f"Crossref journal search for '{query}' returned {len(journals)} results")
            return journals

        except Exception as e:
            logger.error(f"Crossref journal search failed: {e}")
            return []

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
        try:
            result = self._client.funders(query=query, limit=max_results)

            funders = []
            items = result.get("message", {}).get("items", [])

            for item in items:
                try:
                    funders.append(self._convert_to_funder(item))
                except Exception as e:
                    logger.warning(f"Failed to convert funder: {e}")
                    continue

            logger.info(f"Crossref funder search for '{query}' returned {len(funders)} results")
            return funders

        except Exception as e:
            logger.error(f"Crossref funder search failed: {e}")
            return []

    def _convert_to_work(self, item: dict[str, Any]) -> CrossrefWork:
        """Convert Crossref API response to CrossrefWork.

        Args:
            item: Dictionary from Crossref API response

        Returns:
            CrossrefWork DTO
        """
        # Extract DOI
        doi = item.get("DOI", "")

        # Extract title (can be a list)
        title_list = item.get("title", [])
        title = title_list[0] if title_list else ""

        # Extract authors
        authors = []
        for author in item.get("author", []):
            name_parts = []
            if "given" in author:
                name_parts.append(author["given"])
            if "family" in author:
                name_parts.append(author["family"])
            if name_parts:
                authors.append(" ".join(name_parts))
            elif "name" in author:
                authors.append(author["name"])

        # Extract abstract
        abstract = item.get("abstract", "")
        if abstract:
            # Remove HTML tags if present
            import re
            abstract = re.sub(r'<[^>]+>', '', abstract)

        # Extract published date
        published_parts = item.get("published-print", item.get("published-online", {}))
        date_parts = published_parts.get("date-parts", [[]])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            if len(parts) >= 3:
                published_date = f"{parts[0]}-{parts[1]:02d}-{parts[2]:02d}"
            elif len(parts) >= 2:
                published_date = f"{parts[0]}-{parts[1]:02d}"
            elif len(parts) >= 1:
                published_date = str(parts[0])
            else:
                published_date = ""
        else:
            published_date = ""

        # Extract container title (journal name)
        container_title_list = item.get("container-title", [])
        container_title = container_title_list[0] if container_title_list else ""

        # Extract license
        licenses = item.get("license", [])
        license_url = licenses[0].get("URL", "") if licenses else ""

        # Extract subjects
        subjects = item.get("subject", [])

        return CrossrefWork(
            doi=doi,
            title=title,
            authors=authors,
            abstract=abstract,
            type=item.get("type", ""),
            published_date=published_date,
            container_title=container_title,
            publisher=item.get("publisher", ""),
            volume=item.get("volume", ""),
            issue=item.get("issue", ""),
            page=item.get("page", ""),
            url=item.get("URL", f"https://doi.org/{doi}"),
            is_referenced_by_count=item.get("is-referenced-by-count", 0),
            references_count=item.get("references-count", 0),
            license=license_url,
            subject=subjects,
        )

    def _convert_to_journal(self, item: dict[str, Any]) -> CrossrefJournal:
        """Convert Crossref API response to CrossrefJournal.

        Args:
            item: Dictionary from Crossref API response

        Returns:
            CrossrefJournal DTO
        """
        issn = item.get("ISSN", [])
        if isinstance(issn, str):
            issn = [issn]

        return CrossrefJournal(
            issn=issn,
            title=item.get("title", ""),
            publisher=item.get("publisher", ""),
            subject=item.get("subjects", []),
            counts=item.get("counts", {}),
        )

    def _convert_to_funder(self, item: dict[str, Any]) -> CrossrefFunder:
        """Convert Crossref API response to CrossrefFunder.

        Args:
            item: Dictionary from Crossref API response

        Returns:
            CrossrefFunder DTO
        """
        return CrossrefFunder(
            funder_id=item.get("id", item.get("DOI", "")),
            name=item.get("name", ""),
            location=item.get("location", ""),
            alt_names=item.get("alt-names", []),
            work_count=item.get("work-count", 0),
        )
