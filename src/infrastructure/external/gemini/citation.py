# -*- coding: utf-8 -*-
"""
Gemini Citation Search Adapter.

Implements CitationSearchPort using Google Gemini Semantic Retrieval API.
"""

import re
from typing import Generator, Any

from google import genai
from google.genai import types

from src.application.ports.citation_search import (
    CitationSearchPort,
    CitationDTO,
    CitationResultDTO,
)
from src.core.config import get_settings, GeminiModels


class GeminiCitationAdapter(CitationSearchPort):
    """CitationSearchPort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to search documents
    with inline citations.

    Example:
        adapter = GeminiCitationAdapter()
        result = adapter.search_with_citations("store-123", "What is AI?")
    """

    def __init__(self, client: genai.Client | None = None):
        """Initialize adapter with Gemini client.

        Args:
            client: Optional Gemini client instance.
                   Creates one if not provided.
        """
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is None:
            settings = get_settings()
            self._client = genai.Client(api_key=settings.google_api_key)
        return self._client

    def _extract_detailed_sources(
        self,
        grounding_metadata: Any,
    ) -> list[dict[str, Any]]:
        """Extract detailed source information from grounding metadata.

        Args:
            grounding_metadata: Grounding metadata from Gemini response

        Returns:
            List of detailed source information with location data
        """
        sources = []

        if not hasattr(grounding_metadata, "grounding_chunks"):
            return sources

        for idx, chunk in enumerate(grounding_metadata.grounding_chunks, start=1):
            ctx = getattr(chunk, "retrieved_context", None)
            source_name = "unknown"
            content = ""
            if ctx:
                source_name = getattr(ctx, "title", None) or getattr(ctx, "uri", None) or "unknown"
                content = getattr(ctx, "text", "") or ""
            source_info = {
                "index": idx,
                "source": source_name,
                "content": content,
                "page": None,
                "start_index": None,
                "end_index": None,
            }

            if hasattr(chunk, "page"):
                source_info["page"] = chunk.page
            if hasattr(chunk, "start_index"):
                source_info["start_index"] = chunk.start_index
            if hasattr(chunk, "end_index"):
                source_info["end_index"] = chunk.end_index

            if hasattr(chunk, "retrieved_context"):
                ctx = chunk.retrieved_context
                if hasattr(ctx, "uri"):
                    source_info["source"] = ctx.uri
                if hasattr(ctx, "title"):
                    source_info["title"] = ctx.title

            sources.append(source_info)

        return sources

    def _insert_inline_citations(
        self,
        response_text: str,
        sources: list[dict[str, Any]],
    ) -> str:
        """Insert inline citation markers into response text.

        Args:
            response_text: The original response text
            sources: List of source information with content

        Returns:
            Response text with inline citation markers
        """
        if not sources:
            return response_text

        cited_text = response_text
        citations_added = set()

        for source in sources:
            idx = source.get("index", 0)
            content = source.get("content", "")

            if not content or idx in citations_added:
                continue

            words = content.split()
            if len(words) >= 3:
                phrase_len = min(5, len(words))
                search_phrase = " ".join(words[:phrase_len]).lower()

                response_lower = cited_text.lower()
                pos = response_lower.find(search_phrase)

                if pos != -1:
                    sentence_end = pos
                    for end_char in [".", "!", "?", "\n"]:
                        end_pos = cited_text.find(end_char, pos)
                        if end_pos != -1:
                            sentence_end = max(sentence_end, end_pos)
                            break
                    else:
                        sentence_end = min(pos + len(search_phrase) + 50, len(cited_text))

                    citation_marker = f" [{idx}]"
                    if citation_marker not in cited_text[pos:sentence_end + 10]:
                        cited_text = (
                            cited_text[:sentence_end + 1]
                            + citation_marker
                            + cited_text[sentence_end + 1:]
                        )
                        citations_added.add(idx)

        if not citations_added and sources:
            all_citations = " ".join([f"[{s.get('index', i+1)}]" for i, s in enumerate(sources)])
            cited_text = cited_text.rstrip() + " " + all_citations

        return cited_text

    def _convert_to_citation_dto(self, source: dict, index: int) -> CitationDTO:
        """Convert raw source dict to CitationDTO.

        Args:
            source: Raw source dictionary
            index: Citation index (1-based)

        Returns:
            CitationDTO with extracted fields
        """
        return CitationDTO(
            index=source.get("index", index),
            source=source.get("source") or "unknown",
            content=source.get("content") or "",
            page=source.get("page"),
            start_index=source.get("start_index"),
            end_index=source.get("end_index"),
        )

    def search_with_citations(
        self,
        store_name: str,
        query: str,
        model: str = GeminiModels.DEFAULT,
    ) -> CitationResultDTO:
        """Search documents and generate answer with citations.

        Args:
            store_name: The document store to search
            query: The user's question
            model: The model to use for generation

        Returns:
            CitationResultDTO with response and citations
        """
        try:
            response = self._get_client().models.generate_content(
                model=model,
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name]
                            )
                        )
                    ]
                ),
            )

            response_text = response.text if response.text else ""
            sources = []

            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "grounding_metadata"):
                    sources = self._extract_detailed_sources(
                        candidate.grounding_metadata
                    )

            cited_response = self._insert_inline_citations(response_text, sources)

            citations = [
                self._convert_to_citation_dto(src, idx)
                for idx, src in enumerate(sources, start=1)
            ]

            return CitationResultDTO(
                response=cited_response,
                response_plain=response_text,
                citations=citations,
                error=None,
            )

        except Exception as e:
            return CitationResultDTO(
                response="",
                response_plain="",
                citations=[],
                error=str(e),
            )

    def search_with_citations_stream(
        self,
        store_name: str,
        query: str,
        model: str = GeminiModels.DEFAULT,
    ) -> Generator[dict[str, Any], None, None]:
        """Search documents with streaming response.

        Args:
            store_name: The document store to search
            query: The user's question
            model: The model to use for generation

        Yields:
            Event dicts with 'type' (content, citations, done, error)
        """
        try:
            response_stream = self._get_client().models.generate_content_stream(
                model=model,
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name]
                            )
                        )
                    ]
                ),
            )

            full_response = ""
            sources = []

            for chunk in response_stream:
                if chunk.text:
                    full_response += chunk.text
                    yield {
                        "type": "content",
                        "text": chunk.text,
                    }

                if hasattr(chunk, "candidates") and chunk.candidates:
                    candidate = chunk.candidates[0]
                    if hasattr(candidate, "grounding_metadata"):
                        new_sources = self._extract_detailed_sources(
                            candidate.grounding_metadata
                        )
                        for src in new_sources:
                            if src not in sources:
                                sources.append(src)

            if sources:
                cited_response = self._insert_inline_citations(full_response, sources)
                citations = [
                    {
                        "index": src.get("index", idx),
                        "source": src.get("source") or "unknown",
                        "content": src.get("content") or "",
                        "page": src.get("page"),
                        "start_index": src.get("start_index"),
                        "end_index": src.get("end_index"),
                    }
                    for idx, src in enumerate(sources, start=1)
                ]
                yield {
                    "type": "citations",
                    "response_with_citations": cited_response,
                    "citations": citations,
                }

            yield {"type": "done"}

        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
            }
