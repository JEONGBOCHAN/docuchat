# -*- coding: utf-8 -*-
"""
Gemini Document Search Adapter.

Implements DocumentSearchPort using Google Gemini Semantic Retrieval API.
This adapter uses the Gemini API directly without depending on legacy services.
"""

from google import genai
from google.genai import types

from src.application.ports.document_search import DocumentSearchPort, SearchResult
from src.core.config import get_settings, GeminiModels


class GeminiDocumentSearchAdapter(DocumentSearchPort):
    """DocumentSearchPort implementation using Google Gemini.

    This adapter uses the Gemini API directly through the clean architecture
    port interface. This allows the application layer to use document search
    without coupling to Gemini specifics.

    Example:
        adapter = GeminiDocumentSearchAdapter()
        results = adapter.search("What is AI?", "channel-123")
    """

    def __init__(self, client: genai.Client | None = None):
        """Initialize adapter with Gemini client.

        Args:
            client: Optional Gemini client. Creates one if not provided.
        """
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is None:
            settings = get_settings()
            self._client = genai.Client(api_key=settings.google_api_key)
        return self._client

    def search(
        self,
        query: str,
        channel_id: str,
        top_k: int = 5,
        model: str = GeminiModels.DEFAULT,
    ) -> list[SearchResult]:
        """Search for relevant documents using Gemini.

        Uses Gemini's file_search grounding to find relevant content.

        Args:
            query: The search query
            channel_id: The channel (FileSearchStore) to search in
            top_k: Maximum number of results (used for limiting output)
            model: The Gemini model to use

        Returns:
            List of SearchResult objects
        """
        try:
            # Use Gemini's grounded generation with file_search
            search_prompt = f"Find information about: {query}\n\nReturn the relevant content from the documents."

            response = self._get_client().models.generate_content(
                model=model,
                contents=search_prompt,
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
            results = []
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "grounding_metadata"):
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, "grounding_chunks"):
                        for i, chunk in enumerate(metadata.grounding_chunks):
                            if i >= top_k:
                                break
                            ctx = getattr(chunk, "retrieved_context", None)
                            source_name = "unknown"
                            content = ""
                            if ctx:
                                source_name = getattr(ctx, "title", None) or getattr(ctx, "uri", None) or "unknown"
                                content = getattr(ctx, "text", "") or ""
                            results.append(SearchResult(
                                content=content,
                                source=source_name,
                                score=1.0 - (i * 0.1),  # Approximate score based on order
                                metadata={"chunk_index": i},
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
        model: str = GeminiModels.DEFAULT,
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

            # Use Gemini client for grounded generation
            response = self._get_client().models.generate_content(
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
