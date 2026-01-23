# -*- coding: utf-8 -*-
"""
Search tools for RAG agent.

Provides tools for searching documents and completing tasks.
Uses Clean Architecture ports for document search.
"""

from typing import Callable

from langchain_core.tools import tool

from src.application.ports.document_search import DocumentSearchPort


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
