# -*- coding: utf-8 -*-
"""
Gemini Document Search Adapter.

Implements DocumentSearchPort using Google Gemini Semantic Retrieval API.
This adapter wraps the existing GeminiService to conform to the port interface.
"""

from src.application.ports.document_search import DocumentSearchPort, SearchResult
from src.services.gemini import GeminiService


class GeminiDocumentSearchAdapter(DocumentSearchPort):
    """DocumentSearchPort implementation using Google Gemini.

    This adapter wraps the existing GeminiService and exposes it through
    the clean architecture port interface. This allows the application
    layer to use document search without coupling to Gemini specifics.

    Example:
        gemini_service = GeminiService()
        adapter = GeminiDocumentSearchAdapter(gemini_service)

        results = adapter.search("What is AI?", "channel-123")
    """

    def __init__(self, gemini_service: GeminiService | None = None):
        """Initialize adapter with GeminiService.

        Args:
            gemini_service: Optional GeminiService instance.
                           Creates one if not provided.
        """
        self._service = gemini_service or GeminiService()

    def search(
        self,
        query: str,
        channel_id: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search for relevant documents using Gemini.

        Args:
            query: The search query
            channel_id: The channel (corpus) to search in
            top_k: Maximum number of results

        Returns:
            List of SearchResult objects
        """
        try:
            # Use Gemini's semantic retrieval
            raw_results = self._service.query_corpus(
                channel_id,
                query,
                results_count=top_k,
            )

            # Convert to SearchResult format
            results = []
            for chunk in raw_results.get("relevant_chunks", []):
                results.append(SearchResult(
                    content=chunk.get("text", ""),
                    source=chunk.get("source", {}).get("name", "unknown"),
                    score=chunk.get("score", 0.0),
                    metadata={
                        "chunk_id": chunk.get("chunk_id"),
                        "document_id": chunk.get("source", {}).get("document_id"),
                    },
                ))

            return results

        except Exception as e:
            # Log error and return empty results
            print(f"Gemini search error: {e}")
            return []

    def search_with_answer(
        self,
        query: str,
        channel_id: str,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Search and generate an answer using Gemini.

        This uses Gemini's grounded generation feature to search
        documents and generate an answer in one call.

        Args:
            query: The user's question
            channel_id: The channel to search in
            conversation_history: Previous conversation for context

        Returns:
            Dictionary with 'response', 'sources', and optional 'error'
        """
        try:
            result = self._service.search_and_answer(
                channel_id,
                query,
                conversation_history=conversation_history,
            )

            return {
                "response": result.get("response", ""),
                "sources": result.get("sources", []),
                "error": result.get("error"),
            }

        except Exception as e:
            return {
                "response": f"Error: {str(e)}",
                "sources": [],
                "error": str(e),
            }
