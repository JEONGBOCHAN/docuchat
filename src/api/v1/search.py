# -*- coding: utf-8 -*-
"""Search History API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.models.search import (
    SearchHistoryItem,
    SearchHistoryList,
    SearchSuggestion,
    SearchSuggestionList,
)
from src.application.ports.channel import ChannelPort
from src.infrastructure.di.container import create_channel_port
from src.core.database import get_db
from src.services.channel_repository import ChannelRepository
from src.services.search_repository import SearchHistoryRepository

router = APIRouter(prefix="/search", tags=["search"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def _get_channel_or_404(
    channel_id: str, channel_port: ChannelPort, db: Session
) -> tuple:
    """Get channel or raise 404."""
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    channel_repo = ChannelRepository(db)
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=channel.display_name or "unknown",
        )

    return channel, channel_meta


def _history_to_response(history, gemini_store_id: str) -> SearchHistoryItem:
    """Convert SearchHistoryDB to SearchHistoryItem."""
    return SearchHistoryItem(
        id=history.id,
        channel_id=gemini_store_id,
        query=history.query,
        search_count=history.search_count,
        created_at=history.created_at,
        last_searched_at=history.last_searched_at,
    )


@router.get(
    "/history",
    response_model=SearchHistoryList,
    summary="Get search history",
)
def get_search_history(
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(description="Maximum number of entries", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of entries to skip", ge=0)] = 0,
) -> SearchHistoryList:
    """Get search history for a channel.

    Returns search queries sorted by most recent first.
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, db)

    search_repo = SearchHistoryRepository(db)
    history = search_repo.get_history(channel_meta, limit=limit, offset=offset)
    total = search_repo.count_history(channel_meta)

    return SearchHistoryList(
        history=[_history_to_response(h, channel_id) for h in history],
        total=total,
    )


@router.get(
    "/suggestions",
    response_model=SearchSuggestionList,
    summary="Get search suggestions",
)
def get_search_suggestions(
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(description="Query prefix for suggestions")] = "",
    limit: Annotated[int, Query(description="Maximum number of suggestions", ge=1, le=20)] = 10,
) -> SearchSuggestionList:
    """Get search suggestions based on query prefix.

    If no prefix is provided, returns popular searches.
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, db)

    search_repo = SearchHistoryRepository(db)
    suggestions = search_repo.get_suggestions(channel_meta, q, limit=limit)

    return SearchSuggestionList(
        suggestions=[
            SearchSuggestion(query=s.query, search_count=s.search_count)
            for s in suggestions
        ],
        query=q,
    )


@router.get(
    "/popular",
    response_model=SearchSuggestionList,
    summary="Get popular searches",
)
def get_popular_searches(
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(description="Maximum number of entries", ge=1, le=20)] = 10,
) -> SearchSuggestionList:
    """Get popular searches for a channel.

    Returns searches sorted by search count (most searched first).
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, db)

    search_repo = SearchHistoryRepository(db)
    popular = search_repo.get_popular(channel_meta, limit=limit)

    return SearchSuggestionList(
        suggestions=[
            SearchSuggestion(query=p.query, search_count=p.search_count)
            for p in popular
        ],
        query="",
    )


@router.delete(
    "/history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a search history entry",
)
def delete_search_history(
    history_id: int,
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a specific search history entry."""
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, db)

    search_repo = SearchHistoryRepository(db)
    history = search_repo.get_by_id(history_id)

    if not history or history.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Search history not found: {history_id}",
        )

    search_repo.delete(history)
    return None


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all search history",
)
def clear_search_history(
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    db: Annotated[Session, Depends(get_db)],
):
    """Clear all search history for a channel."""
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, db)

    search_repo = SearchHistoryRepository(db)
    search_repo.clear_channel_history(channel_meta)
    return None
