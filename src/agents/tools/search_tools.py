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
