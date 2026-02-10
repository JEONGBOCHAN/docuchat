# -*- coding: utf-8 -*-
"""
Semantic Scholar MCP Adapter.

Implements SemanticScholarSearchPort using the semanticscholar-mcp-server via stdio.
This adapter communicates with the MCP server subprocess, providing paper search,
author lookup, and citation analysis through the MCP protocol.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from src.shared.kernel.contracts.ports.semantic_scholar import (
    SemanticScholarSearchPort,
    SemanticScholarPaper,
    SemanticScholarAuthor,
)
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class SemanticScholarMcpAdapter(SemanticScholarSearchPort):
    """SemanticScholarSearchPort implementation using MCP server via stdio.

    This adapter spawns a semanticscholar-mcp-server subprocess and communicates
    with it using the Model Context Protocol (MCP) over stdio.

    Features:
        - search_semantic_scholar: Search papers by query
        - get_semantic_scholar_paper_details: Get paper details
        - get_semantic_scholar_author_details: Get author details
        - get_semantic_scholar_citations_and_references: Get citations/references

    Example:
        adapter = SemanticScholarMcpAdapter()
        results = adapter.search("attention mechanism", max_results=5)
        for paper in results:
            print(f"{paper.title} - {paper.citation_count} citations")
    """

    def __init__(self, api_key: str | None = None):
        """Initialize the Semantic Scholar MCP adapter.

        Args:
            api_key: Optional API key for higher rate limits.
                    If not provided, uses shared rate limit pool.
        """
        self._api_key = api_key
        self._initialized = False

    def _get_server_command(self) -> list[str]:
        """Get the command to start semanticscholar-mcp-server.

        Returns:
            List of command arguments for subprocess.
        """
        if sys.platform == "win32":
            # On Windows, check Python Scripts directories
            scripts_dir = Path(sys.executable).parent / "Scripts"
            server_path = scripts_dir / "semanticscholar-mcp-server.exe"
            if server_path.exists():
                return [str(server_path)]

            user_scripts = Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts"
            server_path = user_scripts / "semanticscholar-mcp-server.exe"
            if server_path.exists():
                return [str(server_path)]

        # Default: use python -m
        return [sys.executable, "-m", "semanticscholar_mcp_server"]

    async def _call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on the semanticscholar-mcp-server.

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
            env = dict(os.environ)
            if self._api_key:
                env["SEMANTIC_SCHOLAR_API_KEY"] = self._api_key

            server_params = StdioServerParameters(
                command=self._get_server_command()[0],
                args=self._get_server_command()[1:],
                env=env,
            )

            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    result = await session.call_tool(tool_name, arguments)

                    if result.content:
                        for content_item in result.content:
                            if hasattr(content_item, "text"):
                                try:
                                    return json.loads(content_item.text)
                                except json.JSONDecodeError:
                                    return {"text": content_item.text}
                    return {}

        except Exception as e:
            logger.error(f"Semantic Scholar MCP call error: {e}")
            return {"error": str(e)}

    def _run_async(self, coro):
        """Run an async coroutine in sync context."""
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            return asyncio.run(coro)

    def search(
        self,
        query: str,
        max_results: int = 5,
        year_from: int | None = None,
        year_to: int | None = None,
        fields_of_study: list[str] | None = None,
    ) -> list[SemanticScholarPaper]:
        """Search Semantic Scholar for papers using MCP server.

        Args:
            query: The search query
            max_results: Maximum number of results to return (default 5)
            year_from: Filter papers from this year
            year_to: Filter papers until this year
            fields_of_study: Filter by fields (e.g., ["Computer Science"])

        Returns:
            List of SemanticScholarPaper objects
        """
        arguments: dict[str, Any] = {
            "query": query,
            "limit": max_results,
        }

        if year_from:
            arguments["year_from"] = year_from
        if year_to:
            arguments["year_to"] = year_to
        if fields_of_study:
            arguments["fields_of_study"] = fields_of_study

        result = self._run_async(self._call_mcp_tool("search_semantic_scholar", arguments))

        if "error" in result:
            logger.error(f"Semantic Scholar search error: {result['error']}")
            return []

        papers = []
        paper_list = result.get("papers", result.get("results", []))

        for paper in paper_list:
            try:
                papers.append(self._convert_to_paper(paper))
            except Exception as e:
                logger.warning(f"Failed to convert paper: {e}")
                continue

        logger.info(f"Semantic Scholar search for '{query}' returned {len(papers)} results")
        return papers

    def get_paper(self, paper_id: str) -> SemanticScholarPaper | None:
        """Get a specific paper by its ID.

        Args:
            paper_id: The Semantic Scholar paper ID or external ID (DOI, arXiv ID)

        Returns:
            SemanticScholarPaper if found, None otherwise
        """
        arguments = {"paper_id": paper_id}

        result = self._run_async(
            self._call_mcp_tool("get_semantic_scholar_paper_details", arguments)
        )

        if "error" in result:
            logger.error(f"Semantic Scholar get_paper error: {result['error']}")
            return None

        if result and "paper_id" not in result and "paperId" not in result:
            # Result might be wrapped
            result = result.get("paper", result)

        if result:
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
        arguments = {"author_id": author_id}

        result = self._run_async(
            self._call_mcp_tool("get_semantic_scholar_author_details", arguments)
        )

        if "error" in result:
            logger.error(f"Semantic Scholar get_author error: {result['error']}")
            return None

        if result:
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
        arguments = {
            "paper_id": paper_id,
            "limit": max_results,
        }

        result = self._run_async(
            self._call_mcp_tool("get_semantic_scholar_citations_and_references", arguments)
        )

        if "error" in result:
            logger.error(f"Semantic Scholar get_citations error: {result['error']}")
            return []

        papers = []
        citations = result.get("citations", [])

        for paper in citations[:max_results]:
            try:
                papers.append(self._convert_to_paper(paper))
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
        arguments = {
            "paper_id": paper_id,
            "limit": max_results,
        }

        result = self._run_async(
            self._call_mcp_tool("get_semantic_scholar_citations_and_references", arguments)
        )

        if "error" in result:
            logger.error(f"Semantic Scholar get_references error: {result['error']}")
            return []

        papers = []
        references = result.get("references", [])

        for paper in references[:max_results]:
            try:
                papers.append(self._convert_to_paper(paper))
            except Exception as e:
                logger.warning(f"Failed to convert reference: {e}")
                continue

        return papers

    def _convert_to_paper(self, paper: dict[str, Any]) -> SemanticScholarPaper:
        """Convert MCP response to SemanticScholarPaper.

        Args:
            paper: Dictionary from MCP response

        Returns:
            SemanticScholarPaper DTO
        """
        # Handle nested citingPaper/citedPaper structure
        if "citingPaper" in paper:
            paper = paper["citingPaper"]
        elif "citedPaper" in paper:
            paper = paper["citedPaper"]

        paper_id = paper.get("paperId", paper.get("paper_id", ""))

        # Authors can be list of strings or list of dicts
        authors = paper.get("authors", [])
        if authors and isinstance(authors[0], dict):
            authors = [a.get("name", str(a)) for a in authors]

        # External IDs
        external_ids = paper.get("externalIds", paper.get("external_ids", {}))
        if not isinstance(external_ids, dict):
            external_ids = {}

        # Fields of study
        fields = paper.get("fieldsOfStudy", paper.get("fields_of_study", []))
        if fields and isinstance(fields[0], dict):
            fields = [f.get("category", str(f)) for f in fields]

        return SemanticScholarPaper(
            paper_id=paper_id,
            title=paper.get("title", ""),
            authors=authors,
            abstract=paper.get("abstract", "") or "",
            year=paper.get("year"),
            citation_count=paper.get("citationCount", paper.get("citation_count", 0)) or 0,
            reference_count=paper.get("referenceCount", paper.get("reference_count", 0)) or 0,
            venue=paper.get("venue", "") or "",
            url=paper.get("url", f"https://www.semanticscholar.org/paper/{paper_id}"),
            fields_of_study=fields or [],
            is_open_access=paper.get("isOpenAccess", paper.get("is_open_access", False)) or False,
            external_ids=external_ids,
        )

    def _convert_to_author(self, author: dict[str, Any]) -> SemanticScholarAuthor:
        """Convert MCP response to SemanticScholarAuthor.

        Args:
            author: Dictionary from MCP response

        Returns:
            SemanticScholarAuthor DTO
        """
        author_id = author.get("authorId", author.get("author_id", ""))

        # Affiliations can be list of strings or list of dicts
        affiliations = author.get("affiliations", [])
        if affiliations and isinstance(affiliations[0], dict):
            affiliations = [a.get("name", str(a)) for a in affiliations]

        return SemanticScholarAuthor(
            author_id=author_id,
            name=author.get("name", ""),
            affiliations=affiliations or [],
            paper_count=author.get("paperCount", author.get("paper_count", 0)) or 0,
            citation_count=author.get("citationCount", author.get("citation_count", 0)) or 0,
            h_index=author.get("hIndex", author.get("h_index", 0)) or 0,
            url=author.get("url", f"https://www.semanticscholar.org/author/{author_id}"),
        )
