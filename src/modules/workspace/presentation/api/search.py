# -*- coding: utf-8 -*-
"""Search History API endpoints.

Thin controller: delegates all business logic to SearchHistoryUseCase.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.core.rate_limiter import limiter, RateLimits
from src.models.search import (
    SearchHistoryItem,
    SearchHistoryList,
    SearchSuggestion,
    SearchSuggestionList,
)
from src.modules.workspace.application.use_cases.search_history import (
    SearchHistoryUseCase,
    SearchHistoryItemDTO,
)
from src.shared.kernel.contracts.errors.use_case_errors import ChannelNotFoundError
from src.core.database import get_db

router = APIRouter(prefix="/search", tags=["search"])


def get_search_history_use_case_factory(db: Session = Depends(get_db)) -> Callable[[], SearchHistoryUseCase]:
    """Get search history use case factory with all dependencies wired."""
    from src.modules.workspace.public import create_search_history_use_case
    return lambda: create_search_history_use_case(db)


def _history_dto_to_response(dto: SearchHistoryItemDTO) -> SearchHistoryItem:
    """Convert application-layer DTO to API response model."""
    return SearchHistoryItem(
        id=dto.id,
        channel_id=dto.channel_id,
        query=dto.query,
        search_count=dto.search_count,
        created_at=dto.created_at,
        last_searched_at=dto.last_searched_at,
    )


@router.get(
    "/history",
    response_model=SearchHistoryList,
    summary="Get search history",
)
@limiter.limit(RateLimits.DEFAULT)
def get_search_history(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case_factory: Annotated[Callable[[], SearchHistoryUseCase], Depends(get_search_history_use_case_factory)],
    limit: Annotated[int, Query(description="Maximum number of entries", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of entries to skip", ge=0)] = 0,
) -> SearchHistoryList:
    """Get search history for a channel.

    Returns search queries sorted by most recent first.
    """
    use_case = use_case_factory()
    try:
        result = use_case.get_history(channel_id, limit=limit, offset=offset)
        return SearchHistoryList(
            history=[_history_dto_to_response(h) for h in result.history],
            total=result.total,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/suggestions",
    response_model=SearchSuggestionList,
    summary="Get search suggestions",
)
@limiter.limit(RateLimits.DEFAULT)
def get_search_suggestions(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case_factory: Annotated[Callable[[], SearchHistoryUseCase], Depends(get_search_history_use_case_factory)],
    q: Annotated[str, Query(description="Query prefix for suggestions")] = "",
    limit: Annotated[int, Query(description="Maximum number of suggestions", ge=1, le=20)] = 10,
) -> SearchSuggestionList:
    """Get search suggestions based on query prefix.

    If no prefix is provided, returns popular searches.
    """
    use_case = use_case_factory()
    try:
        result = use_case.get_suggestions(channel_id, prefix=q, limit=limit)
        return SearchSuggestionList(
            suggestions=[
                SearchSuggestion(query=s.query, search_count=s.search_count)
                for s in result.suggestions
            ],
            query=result.query,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/popular",
    response_model=SearchSuggestionList,
    summary="Get popular searches",
)
@limiter.limit(RateLimits.DEFAULT)
def get_popular_searches(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case_factory: Annotated[Callable[[], SearchHistoryUseCase], Depends(get_search_history_use_case_factory)],
    limit: Annotated[int, Query(description="Maximum number of entries", ge=1, le=20)] = 10,
) -> SearchSuggestionList:
    """Get popular searches for a channel.

    Returns searches sorted by search count (most searched first).
    """
    use_case = use_case_factory()
    try:
        result = use_case.get_popular(channel_id, limit=limit)
        return SearchSuggestionList(
            suggestions=[
                SearchSuggestion(query=s.query, search_count=s.search_count)
                for s in result.suggestions
            ],
            query=result.query,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete(
    "/history/{history_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a search history entry",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_search_history(
    request: Request,
    history_id: int,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case_factory: Annotated[Callable[[], SearchHistoryUseCase], Depends(get_search_history_use_case_factory)],
):
    """Delete a specific search history entry."""
    use_case = use_case_factory()
    try:
        if not use_case.delete_entry(channel_id, history_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Search history not found: {history_id}",
            )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return None


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all search history",
)
@limiter.limit(RateLimits.DEFAULT)
def clear_search_history(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case_factory: Annotated[Callable[[], SearchHistoryUseCase], Depends(get_search_history_use_case_factory)],
):
    """Clear all search history for a channel."""
    use_case = use_case_factory()
    try:
        use_case.clear_history(channel_id)
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return None
