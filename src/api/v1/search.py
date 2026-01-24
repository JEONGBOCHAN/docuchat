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
from src.application.ports.persistence import (
    ChannelRepositoryPort,
    SearchHistoryRepositoryPort,
)
from src.core.database import get_db
from src.infrastructure.di.container import (
    create_channel_port,
    create_channel_repository_port,
    create_search_history_repository_port,
)

router = APIRouter(prefix="/search", tags=["search"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


def get_search_history_port(db: Session = Depends(get_db)) -> SearchHistoryRepositoryPort:
    """Get search history repository port instance."""
    return create_search_history_repository_port(db)


def _get_channel_or_404(
    channel_id: str,
    channel_port: ChannelPort,
    channel_repo: ChannelRepositoryPort,
) -> tuple:
    """Get channel or raise 404."""
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=channel.display_name or "unknown",
        )

    return channel, channel_meta


def _history_dto_to_response(history_dto, gemini_store_id: str) -> SearchHistoryItem:
    """Convert SearchHistoryDTO to SearchHistoryItem."""
    return SearchHistoryItem(
        id=history_dto.id,
        channel_id=gemini_store_id,
        query=history_dto.query,
        search_count=history_dto.search_count,
        created_at=history_dto.created_at,
        last_searched_at=history_dto.last_searched_at,
    )


@router.get(
    "/history",
    response_model=SearchHistoryList,
    summary="Get search history",
)
def get_search_history(
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    search_history_repo: Annotated[SearchHistoryRepositoryPort, Depends(get_search_history_port)],
    limit: Annotated[int, Query(description="Maximum number of entries", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of entries to skip", ge=0)] = 0,
) -> SearchHistoryList:
    """Get search history for a channel.

    Returns search queries sorted by most recent first.
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    history = search_history_repo.get_history(channel_meta.id, limit=limit, offset=offset)
    total = search_history_repo.count_history(channel_meta.id)

    return SearchHistoryList(
        history=[_history_dto_to_response(h, channel_id) for h in history],
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
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    search_history_repo: Annotated[SearchHistoryRepositoryPort, Depends(get_search_history_port)],
    q: Annotated[str, Query(description="Query prefix for suggestions")] = "",
    limit: Annotated[int, Query(description="Maximum number of suggestions", ge=1, le=20)] = 10,
) -> SearchSuggestionList:
    """Get search suggestions based on query prefix.

    If no prefix is provided, returns popular searches.
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    suggestions = search_history_repo.get_suggestions(channel_meta.id, q, limit=limit)

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
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    search_history_repo: Annotated[SearchHistoryRepositoryPort, Depends(get_search_history_port)],
    limit: Annotated[int, Query(description="Maximum number of entries", ge=1, le=20)] = 10,
) -> SearchSuggestionList:
    """Get popular searches for a channel.

    Returns searches sorted by search count (most searched first).
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    popular = search_history_repo.get_popular(channel_meta.id, limit=limit)

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
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    search_history_repo: Annotated[SearchHistoryRepositoryPort, Depends(get_search_history_port)],
):
    """Delete a specific search history entry."""
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    history = search_history_repo.get_by_id(history_id)

    if not history or history.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Search history not found: {history_id}",
        )

    search_history_repo.delete(history_id)
    return None


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all search history",
)
def clear_search_history(
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    search_history_repo: Annotated[SearchHistoryRepositoryPort, Depends(get_search_history_port)],
):
    """Clear all search history for a channel."""
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    search_history_repo.clear_channel_history(channel_meta.id)
    return None
