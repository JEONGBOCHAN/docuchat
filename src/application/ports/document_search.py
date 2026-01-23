# -*- coding: utf-8 -*-
"""
Document Search Port.

Defines the interface for document retrieval (RAG).
This abstracts the actual search implementation (Google Semantic Retrieval, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single document search result.

    Attributes:
        content: The relevant text snippet from the document
        source: Source file name or identifier
        score: Relevance score (higher is more relevant)
        metadata: Additional metadata about the result
    """

    content: str
    source: str
    score: float = 0.0
    metadata: dict | None = None


class DocumentSearchPort(ABC):
    """Abstract interface for document search operations.

    Implementations of this port handle searching through uploaded documents
    in a channel. This allows the application layer to search documents
    without knowing the underlying implementation (Google, Pinecone, etc.).

    Example:
        # Using Google Semantic Retrieval
        search = GeminiDocumentSearchAdapter(gemini_service)
        results = search.search("What is the main topic?", "channel-123")

        # Can be replaced with different implementation
        search = PineconeDocumentSearchAdapter(pinecone_client)
        results = search.search("What is the main topic?", "channel-123")
    """

    @abstractmethod
    def search(
        self,
        query: str,
        channel_id: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search for relevant documents.

        Args:
            query: The search query
            channel_id: The channel (document store) to search in
            top_k: Maximum number of results to return

        Returns:
            List of SearchResult objects, sorted by relevance
        """
        pass

    @abstractmethod
    def search_with_answer(
        self,
        query: str,
        channel_id: str,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Search and generate an answer based on results.

        This combines retrieval with answer generation for RAG.

        Args:
            query: The user's question
            channel_id: The channel to search in
            conversation_history: Previous conversation for context

        Returns:
            Dictionary with 'response', 'sources', and optional 'error'
        """
        pass
