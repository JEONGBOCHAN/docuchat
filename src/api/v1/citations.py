# -*- coding: utf-8 -*-
"""Citation API endpoints for inline citations and source navigation."""

import json
from datetime import datetime, UTC
from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models.citation import (
    Citation,
    CitationLocation,
    CitedResponse,
    CitationRequest,
    CitationDetail,
)
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.channel_repository import ChannelRepository

router = APIRouter(prefix="/citations", tags=["citations"])


def _format_sse_event(data: dict) -> str:
    """Format data as SSE event."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _convert_to_citation(source: dict, idx: int) -> Citation:
    """Convert raw source dict to Citation model."""
    return Citation(
        index=source.get("index", idx),
        source=source.get("source") or "unknown",
        content=source.get("content") or "",
        location=CitationLocation(
            page=source.get("page"),
            start_index=source.get("start_index"),
            end_index=source.get("end_index"),
        ),
    )


@router.post(
    "",
    response_model=CitedResponse,
    summary="Query with inline citations",
)
@limiter.limit(RateLimits.CHAT)
def query_with_citations(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID to query")],
    body: CitationRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> CitedResponse:
    """Send a question and get an AI-generated answer with inline citations.

    The response includes:
    - response: Text with inline citation markers [1], [2], etc.
    - response_plain: Text without citation markers
    - citations: Detailed list of citations with source info and navigation data
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Search with citations
    result = gemini.search_with_citations(channel_id, body.query)

    if "error" in result and result["error"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {result['error']}",
        )

    # Convert citations to models
    citations = [
        _convert_to_citation(src, idx)
        for idx, src in enumerate(result.get("citations", []), start=1)
    ]

    return CitedResponse(
        query=body.query,
        response=result.get("response", ""),
        response_plain=result.get("response_plain", ""),
        citations=citations,
        created_at=datetime.now(UTC),
    )


@router.post(
    "/stream",
    summary="Query with inline citations (streaming)",
)
@limiter.limit(RateLimits.CHAT)
def query_with_citations_stream(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID to query")],
    body: CitationRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """Send a question and get a streaming response with inline citations.

    Returns Server-Sent Events (SSE) with the following event types:
    - content: Text chunks of the response
    - citations: Final response with inline citations and source details
    - done: Signals completion
    - error: Error information if something went wrong
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    def generate_stream() -> Generator[str, None, None]:
        """Generate SSE events from Gemini streaming response."""
        for event in gemini.search_with_citations_stream(channel_id, body.query):
            event_type = event.get("type")

            if event_type == "content":
                yield _format_sse_event(event)

            elif event_type == "citations":
                # Convert citations to serializable format
                citations = [
                    {
                        "index": src.get("index", idx),
                        "source": src.get("source", "unknown"),
                        "content": src.get("content", ""),
                        "location": {
                            "page": src.get("page"),
                            "start_index": src.get("start_index"),
                            "end_index": src.get("end_index"),
                        },
                    }
                    for idx, src in enumerate(event.get("citations", []), start=1)
                ]
                yield _format_sse_event({
                    "type": "citations",
                    "response_with_citations": event.get("response_with_citations", ""),
                    "citations": citations,
                })

            elif event_type == "done":
                yield _format_sse_event(event)

            elif event_type == "error":
                yield _format_sse_event(event)

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{citation_index}",
    response_model=CitationDetail,
    summary="Get citation details for navigation",
)
@limiter.limit(RateLimits.DEFAULT)
def get_citation_detail(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    citation_index: int,
    source: Annotated[str, Query(description="Source file name")],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> CitationDetail:
    """Get detailed information about a citation for navigation.

    Returns information needed to navigate to and highlight the source in the
    original document, including:
    - Full quoted text
    - Surrounding context
    - Page/location information
    - Text to highlight
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # For now, return a basic response
    # In a full implementation, this would query the document store
    # to get the actual context around the citation
    return CitationDetail(
        index=citation_index,
        source=source,
        content="",
        context="",
        location=CitationLocation(),
        highlight_text="",
    )
