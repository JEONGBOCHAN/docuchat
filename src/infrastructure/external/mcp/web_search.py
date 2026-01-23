# -*- coding: utf-8 -*-
"""
MCP Web Search Adapter.

Implements WebSearchPort using Tavily's remote MCP server.
This adapter communicates with Tavily via the Model Context Protocol,
providing a standardized interface for web search operations.
"""

import asyncio
from typing import Any

from src.application.ports.web_search import WebSearchPort, WebSearchResult
from src.core.config import get_settings


class McpWebSearchAdapter(WebSearchPort):
    """WebSearchPort implementation using Tavily MCP server.

    Connects to Tavily's remote MCP server at:
    https://mcp.tavily.com/mcp/?tavilyApiKey=<key>

    This provides the same functionality as the direct API,
    but uses the MCP protocol for communication.

    Example:
        adapter = McpWebSearchAdapter(api_key="...")
        results = adapter.search("latest AI news")

    Note:
        Requires mcp package: pip install mcp
        Set TAVILY_API_KEY in environment or pass to constructor.
    """

    MCP_SERVER_URL = "https://mcp.tavily.com/mcp"

    def __init__(self, api_key: str | None = None):
        """Initialize MCP adapter.

        Args:
            api_key: Tavily API key. If not provided, reads from
                    TAVILY_API_KEY environment variable.
        """
        self._api_key = api_key or get_settings().tavily_api_key

    def _get_server_url(self) -> str:
        """Get the Tavily MCP server URL with API key."""
        return f"{self.MCP_SERVER_URL}?tavilyApiKey={self._api_key}"

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on the Tavily MCP server.

        Args:
            tool_name: Name of the MCP tool to call
            arguments: Arguments to pass to the tool

        Returns:
            The tool result as a dictionary
        """
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        if not self._api_key:
            return {"error": "Tavily API key not configured"}

        try:
            async with streamablehttp_client(self._get_server_url()) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    result = await session.call_tool(tool_name, arguments)

                    # Parse the result content
                    if result.content:
                        for content_item in result.content:
                            if hasattr(content_item, "text"):
                                import json
                                try:
                                    return json.loads(content_item.text)
                                except json.JSONDecodeError:
                                    return {"text": content_item.text}
                    return {}

        except Exception as e:
            print(f"MCP call error: {e}")
            return {"error": str(e)}

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        """Search the web using Tavily MCP server.

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

        # Build arguments for the MCP tool
        arguments: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
        }

        if include_domains:
            arguments["include_domains"] = include_domains
        if exclude_domains:
            arguments["exclude_domains"] = exclude_domains

        # Run async call in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                self._call_mcp_tool("tavily_search", arguments)
            )
        except RuntimeError:
            # Already in async context, create a new loop
            result = asyncio.run(self._call_mcp_tool("tavily_search", arguments))

        if "error" in result:
            print(f"Tavily MCP search error: {result['error']}")
            return []

        # Convert results to WebSearchResult format
        results = []
        for item in result.get("results", []):
            results.append(
                WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    score=item.get("score", 0.0),
                    published_date=item.get("published_date"),
                )
            )

        return results

    def search_with_context(
        self,
        query: str,
        max_results: int = 5,
    ) -> dict:
        """Search and return results with AI-generated context.

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

        arguments = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": True,
        }

        # Run async call in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                self._call_mcp_tool("tavily_search", arguments)
            )
        except RuntimeError:
            result = asyncio.run(self._call_mcp_tool("tavily_search", arguments))

        if "error" in result:
            return {
                "results": [],
                "answer": "",
                "sources": [],
                "error": result["error"],
            }

        # Parse results
        results = []
        sources = []

        for item in result.get("results", []):
            results.append(
                WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    score=item.get("score", 0.0),
                )
            )
            sources.append(
                {
                    "source": item.get("url", ""),
                    "title": item.get("title", ""),
                }
            )

        return {
            "results": results,
            "answer": result.get("answer", ""),
            "sources": sources,
        }
