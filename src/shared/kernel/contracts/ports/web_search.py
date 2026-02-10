# -*- coding: utf-8 -*-
"""
Web Search Port.

Defines the interface for web search operations.
This abstracts the actual search implementation (Tavily, Brave, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class WebSearchResult:
    """A single web search result.

    Attributes:
        title: Title of the web page
        url: URL of the page
        snippet: Text snippet/summary from the page
        score: Relevance score (if provided)
        published_date: Publication date (if available)
    """

    title: str
    url: str
    snippet: str
    score: float = 0.0
    published_date: str | None = None


class WebSearchPort(ABC):
    """Abstract interface for web search operations.

    Implementations of this port handle searching the web for real-time
    information. This allows the application to use web search without
    being coupled to a specific provider.

    Example:
        # Using Tavily
        search = TavilyWebSearchAdapter(api_key)
        results = search.search("latest news about AI")

        # Can be replaced with Brave
        search = BraveWebSearchAdapter(api_key)
        results = search.search("latest news about AI")
    """

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        """Search the web for information.

        Args:
            query: The search query
            max_results: Maximum number of results to return
            include_domains: Only include results from these domains
            exclude_domains: Exclude results from these domains

        Returns:
            List of WebSearchResult objects
        """
        pass

    @abstractmethod
    def search_with_context(
        self,
        query: str,
        max_results: int = 5,
    ) -> dict:
        """Search and return results with additional context.

        This is useful for AI agents that need structured context.

        Args:
            query: The search query
            max_results: Maximum number of results

        Returns:
            Dictionary with 'results', 'answer' (if AI-powered), 'sources'
        """
        pass
