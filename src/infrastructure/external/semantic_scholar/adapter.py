# -*- coding: utf-8 -*-
"""
Semantic Scholar Adapter.

Implements SemanticScholarSearchPort using direct HTTP API calls.
This adapter provides paper search, author lookup, and citation analysis
through the Clean Architecture port interface.

Note: Uses httpx for direct API calls instead of the semanticscholar library
which has compatibility issues with Python 3.14+.
"""

import logging
from typing import Any

import httpx

from src.application.ports.semantic_scholar import (
    SemanticScholarSearchPort,
    SemanticScholarPaper,
    SemanticScholarAuthor,
)

logger = logging.getLogger(__name__)


class SemanticScholarAdapter(SemanticScholarSearchPort):
    """SemanticScholarSearchPort implementation using direct API calls.

    This adapter calls the Semantic Scholar API directly via httpx,
    providing paper search, author lookup, and citation analysis.

    Features:
        - Search papers by query with filters
        - Get paper details by ID (Semantic Scholar ID, DOI, arXiv ID)
        - Get author profiles
        - Get citations and references for papers

    Example:
        adapter = SemanticScholarAdapter()
        results = adapter.search("attention mechanism", max_results=5)
        for paper in results:
            print(f"{paper.title} - {paper.citation_count} citations")

    Note:
        Without an API key, requests share a pool of 100 requests/5min.
        With an API key, you get dedicated rate limits.
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    PAPER_FIELDS = "paperId,title,authors,abstract,year,citationCount,referenceCount,venue,url,fieldsOfStudy,isOpenAccess,externalIds"
    AUTHOR_FIELDS = "authorId,name,affiliations,paperCount,citationCount,hIndex,url"

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        """Initialize the Semantic Scholar adapter.

        Args:
            api_key: Optional API key for higher rate limits.
                    Get one at https://www.semanticscholar.org/product/api
            timeout: Request timeout in seconds (default 30).
        """
        self._api_key = api_key
        self._timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        """Get request headers including API key if available."""
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def _make_request(self, method: str, endpoint: str, params: dict | None = None) -> dict | None:
        """Make HTTP request to Semantic Scholar API.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response JSON or None on error
        """
        url = f"{self.BASE_URL}{endpoint}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Semantic Scholar API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Semantic Scholar request failed: {e}")
            return None

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
        params = {
            "query": query,
            "limit": max_results,
            "fields": self.PAPER_FIELDS,
        }

        # Add year filter
        if year_from and year_to:
            params["year"] = f"{year_from}-{year_to}"
        elif year_from:
            params["year"] = f"{year_from}-"
        elif year_to:
            params["year"] = f"-{year_to}"

        # Add fields of study filter
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)

        result = self._make_request("GET", "/paper/search", params)

        if not result:
            return []

        papers = []
        for item in result.get("data", []):
            try:
                papers.append(self._convert_to_paper(item))
            except Exception as e:
                logger.warning(f"Failed to convert paper: {e}")
                continue

        logger.info(f"Semantic Scholar search for '{query}' returned {len(papers)} results")
        return papers

    def get_paper(self, paper_id: str) -> SemanticScholarPaper | None:
        """Get a specific paper by its ID.

        Args:
            paper_id: The Semantic Scholar paper ID or external ID
                     (DOI like "10.1234/...", arXiv ID like "arXiv:2301.00001")

        Returns:
            SemanticScholarPaper if found, None otherwise
        """
        # Handle different ID formats
        if paper_id.startswith("10."):
            paper_id = f"DOI:{paper_id}"

        params = {"fields": self.PAPER_FIELDS}
        result = self._make_request("GET", f"/paper/{paper_id}", params)

        if not result:
            logger.warning(f"Paper not found: {paper_id}")
            return None

        try:
            return self._convert_to_paper(result)
        except Exception as e:
            logger.warning(f"Failed to convert paper: {e}")
            return None

    def get_author(self, author_id: str) -> SemanticScholarAuthor | None:
        """Get author details by ID.

        Args:
            author_id: The Semantic Scholar author ID

        Returns:
            SemanticScholarAuthor if found, None otherwise
        """
        params = {"fields": self.AUTHOR_FIELDS}
        result = self._make_request("GET", f"/author/{author_id}", params)

        if not result:
            logger.warning(f"Author not found: {author_id}")
            return None

        try:
            return self._convert_to_author(result)
        except Exception as e:
            logger.warning(f"Failed to convert author: {e}")
            return None

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
        params = {
            "fields": f"citingPaper.{self.PAPER_FIELDS}",
            "limit": max_results,
        }
        result = self._make_request("GET", f"/paper/{paper_id}/citations", params)

        if not result:
            return []

        papers = []
        for item in result.get("data", []):
            try:
                citing_paper = item.get("citingPaper", item)
                papers.append(self._convert_to_paper(citing_paper))
            except Exception as e:
                logger.warning(f"Failed to convert citation: {e}")
                continue

        return papers

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
        params = {
            "fields": f"citedPaper.{self.PAPER_FIELDS}",
            "limit": max_results,
        }
        result = self._make_request("GET", f"/paper/{paper_id}/references", params)

        if not result:
            return []

        papers = []
        for item in result.get("data", []):
            try:
                cited_paper = item.get("citedPaper", item)
                papers.append(self._convert_to_paper(cited_paper))
            except Exception as e:
                logger.warning(f"Failed to convert reference: {e}")
                continue

        return papers

    def _convert_to_paper(self, paper: dict[str, Any]) -> SemanticScholarPaper:
        """Convert API response to SemanticScholarPaper DTO.

        Args:
            paper: Paper dict from API response

        Returns:
            SemanticScholarPaper DTO
        """
        paper_id = paper.get("paperId", "")

        # Extract author names
        authors = []
        for author in paper.get("authors", []) or []:
            name = author.get("name", "") if isinstance(author, dict) else str(author)
            if name:
                authors.append(name)

        # Handle fields of study
        fields = paper.get("fieldsOfStudy", []) or []

        # Handle external IDs
        external_ids = paper.get("externalIds", {}) or {}
        if not isinstance(external_ids, dict):
            external_ids = {}

        return SemanticScholarPaper(
            paper_id=paper_id,
            title=paper.get("title", "") or "",
            authors=authors,
            abstract=paper.get("abstract", "") or "",
            year=paper.get("year"),
            citation_count=paper.get("citationCount", 0) or 0,
            reference_count=paper.get("referenceCount", 0) or 0,
            venue=paper.get("venue", "") or "",
            url=paper.get("url", "") or f"https://www.semanticscholar.org/paper/{paper_id}",
            fields_of_study=fields,
            is_open_access=paper.get("isOpenAccess", False) or False,
            external_ids=external_ids,
        )

    def _convert_to_author(self, author: dict[str, Any]) -> SemanticScholarAuthor:
        """Convert API response to SemanticScholarAuthor DTO.

        Args:
            author: Author dict from API response

        Returns:
            SemanticScholarAuthor DTO
        """
        author_id = author.get("authorId", "")

        # Handle affiliations
        affiliations = author.get("affiliations", []) or []
        if affiliations and isinstance(affiliations[0], dict):
            affiliations = [a.get("name", str(a)) for a in affiliations]

        return SemanticScholarAuthor(
            author_id=author_id,
            name=author.get("name", "") or "",
            affiliations=affiliations,
            paper_count=author.get("paperCount", 0) or 0,
            citation_count=author.get("citationCount", 0) or 0,
            h_index=author.get("hIndex", 0) or 0,
            url=author.get("url", "") or f"https://www.semanticscholar.org/author/{author_id}",
        )
