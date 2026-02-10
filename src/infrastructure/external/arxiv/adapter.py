# -*- coding: utf-8 -*-
"""
arXiv Adapter.

Implements ArxivSearchPort using the official arxiv Python package.
"""

import logging
from typing import Literal

import arxiv

from src.shared.kernel.contracts.ports.arxiv_search import ArxivSearchPort, ArxivPaperResult

logger = logging.getLogger(__name__)


class ArxivAdapter(ArxivSearchPort):
    """ArxivSearchPort implementation using the arxiv Python package.

    This adapter wraps the official arxiv package to provide paper search
    functionality through the Clean Architecture port interface.

    Example:
        adapter = ArxivAdapter()
        results = adapter.search("attention is all you need", max_results=5)
        for paper in results:
            print(f"{paper.title} by {', '.join(paper.authors)}")
    """

    # Map sort options to arxiv.SortCriterion
    SORT_MAP = {
        "relevance": arxiv.SortCriterion.Relevance,
        "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
        "submittedDate": arxiv.SortCriterion.SubmittedDate,
    }

    def __init__(self):
        """Initialize the arXiv adapter."""
        self._client = arxiv.Client()

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
        try:
            # Build the query string
            search_query = query
            if category:
                search_query = f"cat:{category} AND ({query})"

            # Get sort criterion
            sort_criterion = self.SORT_MAP.get(sort_by, arxiv.SortCriterion.Relevance)

            # Create search object
            search = arxiv.Search(
                query=search_query,
                max_results=max_results,
                sort_by=sort_criterion,
            )

            # Execute search and convert results
            results = []
            for paper in self._client.results(search):
                results.append(self._convert_paper(paper))

            logger.info(f"arXiv search for '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []

    def get_paper(self, arxiv_id: str) -> ArxivPaperResult | None:
        """Get a specific paper by its arXiv ID.

        Args:
            arxiv_id: The arXiv paper ID (e.g., "2301.00001" or "2301.00001v1")

        Returns:
            ArxivPaperResult if found, None otherwise
        """
        try:
            # Search by ID
            search = arxiv.Search(id_list=[arxiv_id])
            results = list(self._client.results(search))

            if results:
                return self._convert_paper(results[0])

            logger.warning(f"Paper not found: {arxiv_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get paper {arxiv_id}: {e}")
            return None

    def _convert_paper(self, paper: arxiv.Result) -> ArxivPaperResult:
        """Convert arxiv.Result to ArxivPaperResult.

        Args:
            paper: The arxiv.Result object

        Returns:
            ArxivPaperResult DTO
        """
        return ArxivPaperResult(
            arxiv_id=paper.entry_id.split("/")[-1],  # Extract ID from URL
            title=paper.title,
            authors=[author.name for author in paper.authors],
            summary=paper.summary,
            published=paper.published.isoformat() if paper.published else "",
            updated=paper.updated.isoformat() if paper.updated else "",
            pdf_url=paper.pdf_url or "",
            primary_category=paper.primary_category,
            categories=paper.categories,
        )
