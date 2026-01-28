# -*- coding: utf-8 -*-
"""
Search tools for RAG agent.

Provides tools for searching documents, web search, and completing tasks.
Uses Clean Architecture ports for document search and web search.
"""

from typing import Callable

from langchain_core.tools import tool

from src.application.ports.document_search import DocumentSearchPort
from src.application.ports.web_search import WebSearchPort
from src.application.ports.arxiv_search import ArxivSearchPort
from src.application.ports.semantic_scholar import SemanticScholarSearchPort
from src.application.ports.crossref import CrossrefSearchPort


def create_search_documents_tool(
    channel_id: str,
    document_search: DocumentSearchPort,
) -> Callable[[str], str]:
    """Create a search_documents tool bound to a specific channel.

    Args:
        channel_id: The channel (FileSearchStore) ID to search in.
        document_search: DocumentSearchPort for searching documents.

    Returns:
        A tool function that searches documents in the specified channel.
    """

    @tool
    def search_documents(query: str) -> str:
        """Search for information in the uploaded documents.

        Use this to find relevant content that can help answer the user's question.

        Args:
            query: The search query to find relevant information in documents.

        Returns:
            Search results with relevant document excerpts and sources.
        """
        results = document_search.search(
            query=query,
            channel_id=channel_id,
        )

        if results:
            formatted_parts = []
            for i, result in enumerate(results, 1):
                formatted_parts.append(f"[Source {i}: {result.source}]\n{result.content}")

            return f"Found {len(results)} relevant sections:\n\n" + "\n\n---\n\n".join(formatted_parts)
        else:
            return "No relevant documents found for this query."

    return search_documents


def create_web_search_tool(
    web_search_port: WebSearchPort,
) -> Callable[[str], str]:
    """Create a web_search tool for searching the internet.

    Args:
        web_search_port: WebSearchPort for web searching (Tavily, etc.).

    Returns:
        A tool function that searches the web.
    """
    from src.core.config import get_settings
    settings = get_settings()

    @tool
    def web_search(query: str) -> str:
        """Search the internet for current information.

        Use this when the user asks about:
        - Current events, news, or recent information
        - Real-world facts not found in uploaded documents
        - Restaurants, places, weather, or location-based queries
        - Any information that requires up-to-date web data

        Args:
            query: The search query to find information on the web.

        Returns:
            Search results from the web with titles, snippets, and URLs.
        """
        # Check if API key is configured
        if not settings.tavily_api_key:
            return "Web search is not available: TAVILY_API_KEY is not configured. Please add your Tavily API key to the .env file."

        results = web_search_port.search(query=query, max_results=5)

        if results:
            formatted_parts = []
            for i, result in enumerate(results, 1):
                formatted_parts.append(
                    f"[Web {i}] {result.title}\n"
                    f"URL: {result.url}\n"
                    f"{result.snippet}"
                )
            return f"Found {len(results)} web results:\n\n" + "\n\n---\n\n".join(formatted_parts)
        else:
            return "No web results found for this query."

    return web_search


def create_finish_tool() -> Callable[[str], str]:
    """Create a finish tool that returns the final answer.

    Returns:
        A tool function that marks the task as complete.
    """

    @tool(return_direct=True)
    def finish(answer: str) -> str:
        """Complete the task and provide the final answer.

        Call this when you have gathered enough information and are ready
        to provide the final answer to the user's question.

        Args:
            answer: The complete final answer to the user's question with citations.

        Returns:
            The final answer.
        """
        return answer

    return finish


def create_arxiv_search_tool(
    arxiv_search_port: ArxivSearchPort,
) -> Callable[[str], str]:
    """Create an arxiv_search tool for searching academic papers.

    Args:
        arxiv_search_port: ArxivSearchPort for arXiv paper search.

    Returns:
        A tool function that searches arXiv.
    """

    @tool
    def arxiv_search(query: str) -> str:
        """Search arXiv for academic papers and research.

        Use this when the user asks about:
        - Academic papers, research, or scientific studies
        - Latest research on a specific topic
        - Technical papers in AI, ML, physics, math, etc.
        - Specific papers by title or author
        - State-of-the-art methods or algorithms

        Args:
            query: The search query to find papers on arXiv.

        Returns:
            Search results with paper titles, authors, summaries, and links.
        """
        results = arxiv_search_port.search(query=query, max_results=5)

        if results:
            formatted_parts = []
            for i, paper in enumerate(results, 1):
                # Truncate summary to first 300 chars for readability
                summary = paper.summary[:300] + "..." if len(paper.summary) > 300 else paper.summary
                authors = ", ".join(paper.authors[:3])
                if len(paper.authors) > 3:
                    authors += f" et al. ({len(paper.authors)} authors)"

                formatted_parts.append(
                    f"[Paper {i}] {paper.title}\n"
                    f"Authors: {authors}\n"
                    f"arXiv ID: {paper.arxiv_id}\n"
                    f"Category: {paper.primary_category}\n"
                    f"Published: {paper.published[:10]}\n"
                    f"PDF: {paper.pdf_url}\n"
                    f"Summary: {summary}"
                )
            return f"Found {len(results)} papers on arXiv:\n\n" + "\n\n---\n\n".join(formatted_parts)
        else:
            return "No papers found on arXiv for this query."

    return arxiv_search


def create_semantic_scholar_search_tool(
    semantic_scholar_port: SemanticScholarSearchPort,
) -> Callable[[str], str]:
    """Create a semantic_scholar_search tool for academic paper search.

    Args:
        semantic_scholar_port: SemanticScholarSearchPort for paper search.

    Returns:
        A tool function that searches Semantic Scholar.
    """

    @tool
    def semantic_scholar_search(query: str) -> str:
        """Search Semantic Scholar for academic papers with citation analysis.

        Use this when the user asks about:
        - Citation counts or impact of specific papers
        - Highly cited papers on a topic
        - Author profiles, h-index, or publication history
        - Papers that cite or are cited by a specific paper
        - Academic influence or impact analysis

        Args:
            query: The search query to find papers on Semantic Scholar.

        Returns:
            Search results with citation metrics and paper details.
        """
        results = semantic_scholar_port.search(query=query, max_results=5)

        if results:
            formatted_parts = []
            for i, paper in enumerate(results, 1):
                abstract = paper.abstract[:250] + "..." if paper.abstract and len(paper.abstract) > 250 else (paper.abstract or "No abstract available")
                authors = ", ".join(paper.authors[:3])
                if len(paper.authors) > 3:
                    authors += f" et al. ({len(paper.authors)} authors)"

                formatted_parts.append(
                    f"[Scholar {i}] {paper.title}\n"
                    f"Authors: {authors}\n"
                    f"Year: {paper.year or 'N/A'}\n"
                    f"Citations: {paper.citation_count}\n"
                    f"Venue: {paper.venue or 'N/A'}\n"
                    f"URL: {paper.url}\n"
                    f"Abstract: {abstract}"
                )
            return f"Found {len(results)} papers on Semantic Scholar:\n\n" + "\n\n---\n\n".join(formatted_parts)
        else:
            return "No papers found on Semantic Scholar for this query. Note: Rate limits may apply without an API key."

    return semantic_scholar_search


def create_crossref_search_tool(
    crossref_port: CrossrefSearchPort,
) -> Callable[[str], str]:
    """Create a crossref_search tool for publication metadata lookup.

    Args:
        crossref_port: CrossrefSearchPort for metadata lookup.

    Returns:
        A tool function that searches Crossref.
    """

    @tool
    def crossref_search(query: str) -> str:
        """Search Crossref for publication metadata and DOI information.

        Use this when the user asks about:
        - DOI lookup or verification
        - Publication metadata (publisher, journal, volume, issue)
        - Journal information or ISSN lookup
        - Finding the official publication record of a paper
        - Publisher or funding organization information

        Args:
            query: The search query or DOI to look up.

        Returns:
            Publication metadata from Crossref.
        """
        # Check if query looks like a DOI
        if query.startswith("10.") or "doi.org" in query.lower():
            work = crossref_port.get_work_by_doi(query)
            if work:
                authors = ", ".join(work.authors[:3])
                if len(work.authors) > 3:
                    authors += f" et al."
                return (
                    f"DOI: {work.doi}\n"
                    f"Title: {work.title}\n"
                    f"Authors: {authors}\n"
                    f"Type: {work.type}\n"
                    f"Published: {work.published_date}\n"
                    f"Journal: {work.container_title}\n"
                    f"Publisher: {work.publisher}\n"
                    f"Volume: {work.volume}, Issue: {work.issue}, Page: {work.page}\n"
                    f"Citations: {work.is_referenced_by_count}\n"
                    f"URL: {work.url}"
                )
            else:
                return f"No publication found for DOI: {query}"

        results = crossref_port.search(query=query, max_results=5)

        if results:
            formatted_parts = []
            for i, work in enumerate(results, 1):
                authors = ", ".join(work.authors[:3])
                if len(work.authors) > 3:
                    authors += f" et al."

                formatted_parts.append(
                    f"[Crossref {i}] {work.title}\n"
                    f"DOI: {work.doi}\n"
                    f"Authors: {authors}\n"
                    f"Published: {work.published_date}\n"
                    f"Journal: {work.container_title}\n"
                    f"Publisher: {work.publisher}\n"
                    f"Citations: {work.is_referenced_by_count}"
                )
            return f"Found {len(results)} publications on Crossref:\n\n" + "\n\n---\n\n".join(formatted_parts)
        else:
            return "No publications found on Crossref for this query."

    return crossref_search
