# -*- coding: utf-8 -*-
"""
Google Scholar MCP Adapter.

Implements GoogleScholarSearchPort using the google-scholar-mcp-server via stdio.
This adapter communicates with the google-scholar-mcp-server subprocess,
providing paper search functionality through MCP protocol.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any

from src.shared.kernel.contracts.ports.google_scholar import GoogleScholarSearchPort, GoogleScholarResult

logger = logging.getLogger(__name__)


class GoogleScholarMcpAdapter(GoogleScholarSearchPort):
    """GoogleScholarSearchPort implementation using google-scholar-mcp-server via stdio.

    This adapter spawns a google-scholar-mcp-server subprocess and communicates
    with it using the Model Context Protocol (MCP) over stdio.

    Features:
        - search_google_scholar_key_words: Keyword search
        - search_google_scholar_advanced: Advanced search with filters
        - get_author_info: Author information retrieval

    Example:
        adapter = GoogleScholarMcpAdapter()
        results = adapter.search("attention is all you need", max_results=5)
        for paper in results:
            print(f"{paper.title} ({paper.year}) - {paper.citation_count} citations")
    """

    def __init__(self):
        """Initialize the Google Scholar MCP adapter."""
        self._initialized = False

    def _get_server_command(self) -> list[str]:
        """Get the command to start google-scholar-mcp-server.

        Returns:
            List of command arguments for subprocess.
        """
        if sys.platform == "win32":
            # On Windows, try the Python Scripts directory
            from pathlib import Path
            scripts_dir = Path(sys.executable).parent / "Scripts"
            server_path = scripts_dir / "google_scholar_mcp_server.exe"
            if server_path.exists():
                return [str(server_path)]

            user_scripts = (
                Path.home()
                / "AppData"
                / "Roaming"
                / "Python"
                / f"Python{sys.version_info.major}{sys.version_info.minor}"
                / "Scripts"
            )
            server_path = user_scripts / "google_scholar_mcp_server.exe"
            if server_path.exists():
                return [str(server_path)]

        # Default: use python -m
        return [sys.executable, "-m", "google_scholar_mcp_server"]

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on the google-scholar-mcp-server.

        Args:
            tool_name: Name of the MCP tool to call
            arguments: Arguments to pass to the tool

        Returns:
            The tool result as a dictionary
        """
        from mcp.client.session import ClientSession
        from mcp.client.stdio import stdio_client
        from mcp import StdioServerParameters

        try:
            server_params = StdioServerParameters(
                command=self._get_server_command()[0],
                args=self._get_server_command()[1:],
                env={**os.environ},
            )

            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    result = await session.call_tool(tool_name, arguments)

                    # Parse the result content
                    if result.content:
                        for content_item in result.content:
                            if hasattr(content_item, "text"):
                                try:
                                    return json.loads(content_item.text)
                                except json.JSONDecodeError:
                                    return {"text": content_item.text}
                    return {}

        except Exception as e:
            logger.error(f"Google Scholar MCP call error: {e}")
            return {"error": str(e)}

    def _run_async(self, coro):
        """Run an async coroutine in sync context.

        Handles the case where we may already be in an async context.

        Args:
            coro: The coroutine to run

        Returns:
            The result of the coroutine
        """
        try:
            loop = asyncio.get_running_loop()
            # Already in async context, need to run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(coro)

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[GoogleScholarResult]:
        """Search Google Scholar for papers using MCP server.

        Args:
            query: The search query
            max_results: Maximum number of results to return (default 5)

        Returns:
            List of GoogleScholarResult objects
        """
        arguments: dict[str, Any] = {
            "query": query,
            "num_results": max_results,
        }

        result = self._run_async(
            self._call_mcp_tool("search_google_scholar_key_words", arguments)
        )

        if "error" in result:
            logger.error(f"Google Scholar MCP search error: {result['error']}")
            return []

        return self._parse_results(result, query)

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
        arguments: dict[str, Any] = {
            "query": query,
            "num_results": max_results,
        }
        if author:
            arguments["author"] = author
        if year_range:
            arguments["year_range"] = list(year_range)

        result = self._run_async(
            self._call_mcp_tool("search_google_scholar_advanced", arguments)
        )

        if "error" in result:
            logger.error(f"Google Scholar MCP advanced search error: {result['error']}")
            return []

        return self._parse_results(result, query)

    def _parse_results(
        self, result: dict[str, Any], query: str
    ) -> list[GoogleScholarResult]:
        """Parse MCP response into GoogleScholarResult list.

        Args:
            result: Raw MCP response dictionary
            query: Original query for logging

        Returns:
            List of GoogleScholarResult objects
        """
        papers = []

        # Handle various response formats
        paper_list = result.get("results", result.get("papers", []))

        # If result is a list directly
        if isinstance(result, list):
            paper_list = result

        for paper in paper_list:
            try:
                papers.append(self._convert_to_result(paper))
            except Exception as e:
                logger.warning(f"Failed to convert Google Scholar paper: {e}")
                continue

        logger.info(
            f"Google Scholar MCP search for '{query}' returned {len(papers)} results"
        )
        return papers

    def _convert_to_result(self, paper: dict[str, Any]) -> GoogleScholarResult:
        """Convert MCP response to GoogleScholarResult.

        Args:
            paper: Dictionary from MCP response

        Returns:
            GoogleScholarResult DTO
        """
        # Authors can be a list of strings or a single string
        authors = paper.get("authors", paper.get("author", []))
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",")]

        # Year handling
        year = paper.get("year", paper.get("pub_year", None))
        if isinstance(year, str):
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None

        # Citation count
        citation_count = paper.get(
            "citation_count",
            paper.get("num_citations", paper.get("citations", 0)),
        )
        if isinstance(citation_count, str):
            try:
                citation_count = int(citation_count)
            except (ValueError, TypeError):
                citation_count = 0

        return GoogleScholarResult(
            title=paper.get("title", ""),
            authors=authors,
            year=year,
            citation_count=citation_count,
            snippet=paper.get("snippet", paper.get("abstract", "")),
            url=paper.get("url", paper.get("link", "")),
            pub_url=paper.get("pub_url", paper.get("eprint_url", "")),
            venue=paper.get("venue", paper.get("journal", "")),
        )
