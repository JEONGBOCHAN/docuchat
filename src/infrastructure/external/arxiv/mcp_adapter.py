# -*- coding: utf-8 -*-
"""
arXiv MCP Adapter.

Implements ArxivSearchPort using the arxiv-mcp-server via stdio.
This adapter communicates with the arxiv-mcp-server subprocess,
providing paper search and download functionality through MCP protocol.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from src.shared.kernel.contracts.ports.arxiv_search import ArxivSearchPort, ArxivPaperResult
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class ArxivMcpAdapter(ArxivSearchPort):
    """ArxivSearchPort implementation using arxiv-mcp-server via stdio.

    This adapter spawns an arxiv-mcp-server subprocess and communicates
    with it using the Model Context Protocol (MCP) over stdio.

    Features:
        - search_papers: Search arXiv for papers
        - download_paper: Download paper PDFs
        - list_papers: List downloaded papers
        - read_paper: Read paper content

    Example:
        adapter = ArxivMcpAdapter()
        results = adapter.search("attention is all you need", max_results=5)
        for paper in results:
            print(f"{paper.title} by {', '.join(paper.authors)}")

    Note:
        The subprocess is lazily initialized on first use and reused
        for subsequent calls to minimize startup overhead.
    """

    def __init__(self, storage_path: str | None = None):
        """Initialize the arXiv MCP adapter.

        Args:
            storage_path: Path to store downloaded papers.
                         If not provided, reads from settings.
        """
        settings = get_settings()
        self._storage_path = storage_path or settings.arxiv_storage_path
        self._storage_path = os.path.expanduser(self._storage_path)

        # Ensure storage directory exists
        Path(self._storage_path).mkdir(parents=True, exist_ok=True)

        # Connection state (lazy initialization)
        self._initialized = False

    def _get_server_command(self) -> list[str]:
        """Get the command to start arxiv-mcp-server.

        Returns:
            List of command arguments for subprocess.
        """
        # Try to find arxiv-mcp-server in PATH or Python scripts
        if sys.platform == "win32":
            # On Windows, try the Python Scripts directory
            scripts_dir = Path(sys.executable).parent / "Scripts"
            server_path = scripts_dir / "arxiv-mcp-server.exe"
            if server_path.exists():
                return [str(server_path)]

            # Also check user's Python Scripts
            user_scripts = Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts"
            server_path = user_scripts / "arxiv-mcp-server.exe"
            if server_path.exists():
                return [str(server_path)]

        # Default: use python -m
        return [sys.executable, "-m", "arxiv_mcp_server"]

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on the arxiv-mcp-server.

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
            # Set up server parameters with storage path as environment variable
            server_params = StdioServerParameters(
                command=self._get_server_command()[0],
                args=self._get_server_command()[1:],
                env={
                    **os.environ,
                    "ARXIV_STORAGE_PATH": self._storage_path,
                },
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
            logger.error(f"arXiv MCP call error: {e}")
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
        sort_by: str = "relevance",
        category: str | None = None,
    ) -> list[ArxivPaperResult]:
        """Search arXiv for papers using MCP server.

        Args:
            query: The search query
            max_results: Maximum number of results to return (default 5)
            sort_by: Sort order - "relevance", "lastUpdatedDate", "submittedDate"
            category: Optional arXiv category filter (e.g., "cs.AI", "cs.CL")

        Returns:
            List of ArxivPaperResult objects
        """
        # Build arguments for search_papers tool
        arguments: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
        }

        # Add category to query if specified
        if category:
            arguments["query"] = f"cat:{category} AND ({query})"

        # Call MCP tool
        result = self._run_async(self._call_mcp_tool("search_papers", arguments))

        if "error" in result:
            logger.error(f"arXiv MCP search error: {result['error']}")
            return []

        # Convert results to ArxivPaperResult format
        papers = []
        paper_list = result.get("papers", result.get("results", []))

        for paper in paper_list:
            try:
                papers.append(self._convert_to_result(paper))
            except Exception as e:
                logger.warning(f"Failed to convert paper: {e}")
                continue

        logger.info(f"arXiv MCP search for '{query}' returned {len(papers)} results")
        return papers

    def get_paper(self, arxiv_id: str) -> ArxivPaperResult | None:
        """Get a specific paper by its arXiv ID.

        Uses search_papers with the specific ID to find the paper.

        Args:
            arxiv_id: The arXiv paper ID (e.g., "2301.00001" or "2301.00001v1")

        Returns:
            ArxivPaperResult if found, None otherwise
        """
        # Search for the specific paper ID
        arguments = {
            "query": f"id:{arxiv_id}",
            "max_results": 1,
        }

        result = self._run_async(self._call_mcp_tool("search_papers", arguments))

        if "error" in result:
            logger.error(f"arXiv MCP get_paper error: {result['error']}")
            return None

        paper_list = result.get("papers", result.get("results", []))
        if paper_list:
            try:
                return self._convert_to_result(paper_list[0])
            except Exception as e:
                logger.warning(f"Failed to convert paper: {e}")

        logger.warning(f"Paper not found: {arxiv_id}")
        return None

    def _convert_to_result(self, paper: dict[str, Any]) -> ArxivPaperResult:
        """Convert MCP response to ArxivPaperResult.

        Args:
            paper: Dictionary from MCP search_papers response

        Returns:
            ArxivPaperResult DTO

        Field mapping:
            MCP field         -> ArxivPaperResult field
            id                -> arxiv_id
            title             -> title
            authors           -> authors
            abstract/summary  -> summary
            published         -> published, updated
            url/pdf_url       -> pdf_url
            categories[0]     -> primary_category
            categories        -> categories
        """
        # Handle different possible field names from MCP server
        arxiv_id = paper.get("id", paper.get("arxiv_id", ""))
        if "/" in arxiv_id:
            arxiv_id = arxiv_id.split("/")[-1]

        # Authors can be a list of strings or list of dicts
        authors = paper.get("authors", [])
        if authors and isinstance(authors[0], dict):
            authors = [a.get("name", str(a)) for a in authors]

        # Categories handling
        categories = paper.get("categories", [])
        if isinstance(categories, str):
            categories = [categories]

        primary_category = paper.get("primary_category", "")
        if not primary_category and categories:
            primary_category = categories[0]

        # Summary can be 'abstract' or 'summary'
        summary = paper.get("abstract", paper.get("summary", ""))

        # Published date
        published = paper.get("published", "")
        updated = paper.get("updated", published)

        # PDF URL
        pdf_url = paper.get("url", paper.get("pdf_url", ""))

        return ArxivPaperResult(
            arxiv_id=arxiv_id,
            title=paper.get("title", ""),
            authors=authors,
            summary=summary,
            published=published,
            updated=updated,
            pdf_url=pdf_url,
            primary_category=primary_category,
            categories=categories,
        )
