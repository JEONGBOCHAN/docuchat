# -*- coding: utf-8 -*-
"""
Tavily Web Search Adapter.

Implements WebSearchPort using Tavily API.
Tavily is designed for AI agents and returns LLM-friendly results.
"""

from typing import Any

from src.application.ports.web_search import WebSearchPort, WebSearchResult
from src.core.config import get_settings


class TavilyWebSearchAdapter(WebSearchPort):
    """WebSearchPort implementation using Tavily.

    Tavily is an AI-native search API that returns results optimized
    for LLM consumption. It can also provide AI-generated answers.

    Example:
        adapter = TavilyWebSearchAdapter(api_key="...")
        results = adapter.search("latest AI news")

    Note:
        Requires tavily-python package: pip install tavily-python
        Set TAVILY_API_KEY in environment or pass to constructor.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize Tavily adapter.

        Args:
            api_key: Tavily API key. If not provided, reads from
                    TAVILY_API_KEY environment variable.
        """
        self._api_key = api_key or get_settings().tavily_api_key
        self._client = None

    def _get_client(self):
        """Lazy-load Tavily client."""
        if self._client is None:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "tavily-python is not installed. "
                    "Run: pip install tavily-python"
                )
        return self._client

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        """Search the web using Tavily.

        Args:
            query: The search query
            max_results: Maximum number of results
            include_domains: Only include results from these domains
            exclude_domains: Exclude results from these domains

        Returns:
            List of WebSearchResult objects
        """
        if not self._api_key:
            return []

        try:
            client = self._get_client()

            # Build search parameters
            search_params: dict[str, Any] = {
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            }

            if include_domains:
                search_params["include_domains"] = include_domains
            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains

            # Execute search
            response = client.search(**search_params)

            # Convert to WebSearchResult format
            results = []
            for item in response.get("results", []):
                results.append(WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    score=item.get("score", 0.0),
                    published_date=item.get("published_date"),
                ))

            return results

        except Exception as e:
            print(f"Tavily search error: {e}")
            return []

    def search_with_context(
        self,
        query: str,
        max_results: int = 5,
    ) -> dict:
        """Search and return results with AI-generated context.

        Tavily can provide an AI-generated answer along with search results.

        Args:
            query: The search query
            max_results: Maximum number of results

        Returns:
            Dictionary with 'results', 'answer', 'sources'
        """
        if not self._api_key:
            return {
                "results": [],
                "answer": "",
                "sources": [],
                "error": "Tavily API key not configured",
            }

        try:
            client = self._get_client()

            # Use Tavily's QnA search for AI-generated answer
            response = client.qna_search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
            )

            # Parse results
            results = []
            sources = []

            for item in response.get("results", []):
                results.append(WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    score=item.get("score", 0.0),
                ))
                sources.append({
                    "source": item.get("url", ""),
                    "title": item.get("title", ""),
                })

            return {
                "results": results,
                "answer": response.get("answer", ""),
                "sources": sources,
            }

        except Exception as e:
            return {
                "results": [],
                "answer": "",
                "sources": [],
                "error": str(e),
            }
