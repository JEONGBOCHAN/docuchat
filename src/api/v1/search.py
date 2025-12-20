# -*- coding: utf-8 -*-
"""Multi-channel Search API endpoints."""

import json
from datetime import datetime, UTC
from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models.search import (
    SearchRequest,
    SearchResponse,
    SearchGroundingSource,
)
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.channel_repository import ChannelRepository

router = APIRouter(prefix="/search", tags=["search"])


def _format_sse_event(data: dict) -> str:
    """Format data as SSE event."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_channel_name_map(
    channel_ids: list[str],
    gemini: GeminiService,
    db: Session,
) -> dict[str, str]:
    """Get a mapping of channel_id to channel name."""
    channel_repo = ChannelRepository(db)
    name_map = {}

    for channel_id in channel_ids:
        # Try to get from local DB first
        channel_meta = channel_repo.get_by_gemini_id(channel_id)
        if channel_meta:
            name_map[channel_id] = channel_meta.name
        else:
            # Fall back to Gemini store info
            store = gemini.get_store(channel_id)
            if store:
                name_map[channel_id] = store.get("display_name", channel_id)
            else:
                name_map[channel_id] = channel_id

    return name_map


def _infer_channel_from_source(
    source: str,
    store_name: str | None,
    channel_ids: list[str],
) -> str:
    """Infer which channel a source belongs to.

    Args:
        source: The source file name
        store_name: The store name if available from grounding metadata
        channel_ids: List of searched channel IDs

    Returns:
        The channel ID that likely contains this source
    """
    # If we have store_name from grounding metadata, use it
    if store_name:
        for channel_id in channel_ids:
            if channel_id in store_name or store_name in channel_id:
                return channel_id

    # Default to first channel if we can't determine
    return channel_ids[0] if channel_ids else ""


@router.post(
    "",
    response_model=SearchResponse,
    summary="Search across multiple channels",
)
@limiter.limit(RateLimits.CHAT)
def multi_channel_search(
    request: Request,
    body: SearchRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchResponse:
    """Search across multiple channels simultaneously.

    Searches up to 5 channels at once and returns unified results.
    Each source in the response includes the channel it came from.
    """
    # Validate all channels exist
    valid_channel_ids = []
    for channel_id in body.channel_ids:
        store = gemini.get_store(channel_id)
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel not found: {channel_id}",
            )
        valid_channel_ids.append(channel_id)

    if not valid_channel_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid channels provided",
        )

    # Get channel name mapping for display
    channel_name_map = _get_channel_name_map(valid_channel_ids, gemini, db)

    # Update last accessed time for all channels
    channel_repo = ChannelRepository(db)
    for channel_id in valid_channel_ids:
        channel_repo.touch(channel_id)

    # Perform multi-store search
    result = gemini.multi_store_search(valid_channel_ids, body.query)

    if "error" in result and result["error"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {result['error']}",
        )

    # Convert sources to SearchGroundingSource with channel info
    sources = []
    for s in result.get("sources", []):
        store_name = s.get("store_name")
        channel_id = _infer_channel_from_source(
            s.get("source", "unknown"),
            store_name,
            valid_channel_ids,
        )
        sources.append(
            SearchGroundingSource(
                source=s.get("source", "unknown"),
                channel_id=channel_id,
                channel_name=channel_name_map.get(channel_id, channel_id),
                content=s.get("content", ""),
            )
        )

    return SearchResponse(
        query=body.query,
        response=result.get("response", ""),
        sources=sources,
        searched_channels=valid_channel_ids,
        created_at=datetime.now(UTC),
    )


@router.post(
    "/stream",
    summary="Search across multiple channels with streaming response",
)
@limiter.limit(RateLimits.CHAT)
def multi_channel_search_stream(
    request: Request,
    body: SearchRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """Search across multiple channels with streaming response.

    Returns Server-Sent Events (SSE) with the following event types:
    - content: Text chunks of the response
    - sources: Grounding sources from documents with channel info
    - done: Signals completion
    - error: Error information if something went wrong
    """
    # Validate all channels exist
    valid_channel_ids = []
    for channel_id in body.channel_ids:
        store = gemini.get_store(channel_id)
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel not found: {channel_id}",
            )
        valid_channel_ids.append(channel_id)

    if not valid_channel_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid channels provided",
        )

    # Get channel name mapping for display
    channel_name_map = _get_channel_name_map(valid_channel_ids, gemini, db)

    # Update last accessed time for all channels
    channel_repo = ChannelRepository(db)
    for channel_id in valid_channel_ids:
        channel_repo.touch(channel_id)

    def generate_stream() -> Generator[str, None, None]:
        """Generate SSE events from Gemini streaming response."""
        for event in gemini.multi_store_search_stream(
            valid_channel_ids, body.query
        ):
            event_type = event.get("type")

            if event_type == "content":
                yield _format_sse_event(event)

            elif event_type == "sources":
                # Enrich sources with channel info
                enriched_sources = []
                for s in event.get("sources", []):
                    store_name = s.get("store_name")
                    channel_id = _infer_channel_from_source(
                        s.get("source", "unknown"),
                        store_name,
                        valid_channel_ids,
                    )
                    enriched_sources.append({
                        "source": s.get("source", "unknown"),
                        "channel_id": channel_id,
                        "channel_name": channel_name_map.get(channel_id, channel_id),
                        "content": s.get("content", ""),
                    })
                yield _format_sse_event({
                    "type": "sources",
                    "sources": enriched_sources,
                    "searched_channels": valid_channel_ids,
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
