# -*- coding: utf-8 -*-
"""
Gemini Citation Search Adapter.

Implements CitationSearchPort using Google Gemini Semantic Retrieval API.
This adapter wraps the existing GeminiService to conform to the port interface.
"""

from typing import Generator, Any

from src.application.ports.citation_search import (
    CitationSearchPort,
    CitationDTO,
    CitationResultDTO,
)
from src.services.gemini import GeminiService


class GeminiCitationAdapter(CitationSearchPort):
    """CitationSearchPort implementation using Google Gemini.

    This adapter wraps the existing GeminiService search_with_citations
    and search_with_citations_stream methods and exposes them through
    the clean architecture port interface.

    Example:
        adapter = GeminiCitationAdapter()
        result = adapter.search_with_citations("store-123", "What is AI?")
    """

    def __init__(self, gemini_service: GeminiService | None = None):
        """Initialize adapter with GeminiService.

        Args:
            gemini_service: Optional GeminiService instance.
                           Creates one if not provided.
        """
        self._service = gemini_service or GeminiService()

    def _convert_to_citation_dto(self, source: dict, index: int) -> CitationDTO:
        """Convert raw source dict to CitationDTO.

        Args:
            source: Raw source dictionary from GeminiService
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
    ) -> CitationResultDTO:
        """Search documents and generate answer with citations.

        Args:
            store_name: The document store to search
            query: The user's question

        Returns:
            CitationResultDTO with response and citations
        """
        result = self._service.search_with_citations(store_name, query)

        # Convert citations to DTOs
        citations = [
            self._convert_to_citation_dto(src, idx)
            for idx, src in enumerate(result.get("citations", []), start=1)
        ]

        return CitationResultDTO(
            response=result.get("response", ""),
            response_plain=result.get("response_plain", ""),
            citations=citations,
            error=result.get("error"),
        )

    def search_with_citations_stream(
        self,
        store_name: str,
        query: str,
    ) -> Generator[dict[str, Any], None, None]:
        """Search documents with streaming response.

        Args:
            store_name: The document store to search
            query: The user's question

        Yields:
            Event dicts with 'type' (content, citations, done, error)
        """
        for event in self._service.search_with_citations_stream(store_name, query):
            event_type = event.get("type")

            if event_type == "content":
                # Pass through content events
                yield event

            elif event_type == "citations":
                # Convert citations to DTO format for consistency
                raw_citations = event.get("citations", [])
                citations = [
                    {
                        "index": src.get("index", idx),
                        "source": src.get("source") or "unknown",
                        "content": src.get("content") or "",
                        "page": src.get("page"),
                        "start_index": src.get("start_index"),
                        "end_index": src.get("end_index"),
                    }
                    for idx, src in enumerate(raw_citations, start=1)
                ]
                yield {
                    "type": "citations",
                    "response_with_citations": event.get("response_with_citations", ""),
                    "citations": citations,
                }

            elif event_type == "done":
                yield event

            elif event_type == "error":
                yield event
