# -*- coding: utf-8 -*-
"""
Search tools for RAG agent.

Provides tools for searching documents and completing tasks.
"""

from typing import Any, Callable

from langchain_core.tools import tool


def create_search_documents_tool(
    channel_id: str,
    gemini_service: Any,
) -> Callable[[str], str]:
    """Create a search_documents tool bound to a specific channel.

    Args:
        channel_id: The channel (FileSearchStore) ID to search in.
        gemini_service: GeminiService instance for document search.

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
        search_result = gemini_service.search_documents(
            store_name=channel_id,
            query=query,
        )

        sources = search_result.get("sources", [])
        if sources:
            formatted_parts = []
            for i, source in enumerate(sources, 1):
                source_name = source.get("source", "unknown")
                content = source.get("content", "")
                formatted_parts.append(f"[Source {i}: {source_name}]\n{content}")

            return f"Found {len(sources)} relevant sections:\n\n" + "\n\n---\n\n".join(formatted_parts)
        else:
            return "No relevant documents found for this query."

    return search_documents


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
