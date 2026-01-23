# -*- coding: utf-8 -*-
"""
Gemini Document Search Adapter.

Implements DocumentSearchPort using Google Gemini Semantic Retrieval API.
This adapter wraps the existing GeminiService to conform to the port interface.
"""

from google.genai import types

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

    def _build_conversation_contents(
        self,
        query: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> list[types.Content] | str:
        """Build conversation contents for multi-turn.

        Args:
            query: Current user query
            conversation_history: Previous messages with 'role' and 'content'

        Returns:
            List of Content objects or just the query string
        """
        if not conversation_history:
            return query

        contents = []

        # Add conversation history
        for msg in conversation_history:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg.get("content", ""))]
                )
            )

        # Add current query
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=query)]
            )
        )

        return contents

    def search_with_answer(
        self,
        query: str,
        channel_id: str,
        conversation_history: list[dict] | None = None,
        model: str = "gemini-3-flash-preview",
    ) -> dict:
        """Search and generate an answer using Gemini.

        This uses Gemini's grounded generation feature to search
        documents and generate an answer in one call.

        Args:
            query: The user's question
            channel_id: The channel to search in
            conversation_history: Previous conversation for context
            model: The model to use for generation

        Returns:
            Dictionary with 'response', 'sources', and optional 'error'
        """
        try:
            # Build contents with conversation history for multi-turn
            contents = self._build_conversation_contents(query, conversation_history)

            # Use Gemini client directly for grounded generation
            client = self._service.client
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[channel_id]
                            )
                        )
                    ]
                ),
            )

            # Extract grounding sources from response
            sources = []
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "grounding_metadata"):
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, "grounding_chunks"):
                        for chunk in metadata.grounding_chunks:
                            # Extract source from retrieved_context
                            ctx = getattr(chunk, "retrieved_context", None)
                            source_name = "unknown"
                            content = ""
                            if ctx:
                                source_name = getattr(ctx, "title", None) or getattr(ctx, "uri", None) or "unknown"
                                content = getattr(ctx, "text", "") or ""
                            sources.append({
                                "source": source_name,
                                "content": content,
                            })

            return {
                "response": response.text if response.text else "",
                "sources": sources,
                "error": None,
            }

        except Exception as e:
            return {
                "response": "",
                "sources": [],
                "error": str(e),
            }
