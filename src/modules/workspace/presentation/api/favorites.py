# -*- coding: utf-8 -*-
"""Favorites API endpoints.

Thin controller: delegates all business logic to FavoriteCrudUseCase.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.core.rate_limiter import limiter, RateLimits
from src.core.database import get_db
from src.models.favorite import (
    FavoriteCreate,
    FavoriteListResponse,
    FavoriteReorderRequest,
    FavoriteResponse,
    TargetType,
)
from src.application.use_cases.favorite_crud import FavoriteCrudUseCase, FavoriteDetailDTO
from src.application.use_cases.exceptions import (
    ChannelNotFoundError,
    TargetNotFoundError,
    InvalidTargetError,
)

router = APIRouter(prefix="/favorites", tags=["favorites"])


def get_favorite_crud_use_case_factory(db: Session = Depends(get_db)) -> Callable[[], FavoriteCrudUseCase]:
    """Get favorite CRUD use case factory with all dependencies wired."""
    from src.modules.workspace.public import create_favorite_crud_use_case
    return lambda: create_favorite_crud_use_case(db)


def _dto_to_response(dto: FavoriteDetailDTO) -> FavoriteResponse:
    """Convert application-layer DTO to API response model."""
    return FavoriteResponse(
        id=dto.id,
        target_type=TargetType(dto.target_type),
        target_id=dto.target_id,
        display_order=dto.display_order,
        created_at=dto.created_at,
    )


def _handle_validation_error(e: Exception):
    """Convert use case exceptions to HTTP exceptions."""
    if isinstance(e, (ChannelNotFoundError, TargetNotFoundError)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    if isinstance(e, InvalidTargetError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add to favorites",
)
@limiter.limit(RateLimits.DEFAULT)
def add_favorite(
    request: Request,
    data: FavoriteCreate,
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
) -> FavoriteResponse:
    """Add a channel, document, or note to favorites."""
    use_case = use_case_factory()
    try:
        dto = use_case.add(data.target_type.value, data.target_id)
        return _dto_to_response(dto)
    except (ChannelNotFoundError, TargetNotFoundError, InvalidTargetError) as e:
        _handle_validation_error(e)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove from favorites",
)
@limiter.limit(RateLimits.DEFAULT)
def remove_favorite(
    request: Request,
    target_type: Annotated[TargetType, Query(description="Type of the target")],
    target_id: Annotated[str, Query(description="ID of the target")],
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
):
    """Remove a channel, document, or note from favorites."""
    use_case = use_case_factory()
    if not use_case.remove(target_type.value, target_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite not found",
        )
    return None


@router.get(
    "",
    response_model=FavoriteListResponse,
    summary="List favorites",
)
@limiter.limit(RateLimits.DEFAULT)
def list_favorites(
    request: Request,
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
    target_type: Annotated[TargetType | None, Query(description="Filter by target type")] = None,
    limit: Annotated[int, Query(description="Maximum number of favorites", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of favorites to skip", ge=0)] = 0,
) -> FavoriteListResponse:
    """List all favorites, optionally filtered by type."""
    use_case = use_case_factory()
    type_value = target_type.value if target_type else None
    result = use_case.list(target_type=type_value, limit=limit, offset=offset)

    return FavoriteListResponse(
        favorites=[_dto_to_response(f) for f in result.favorites],
        total=result.total,
    )


@router.get(
    "/check",
    summary="Check if target is favorited",
)
@limiter.limit(RateLimits.DEFAULT)
def check_favorite(
    request: Request,
    target_type: Annotated[TargetType, Query(description="Type of the target")],
    target_id: Annotated[str, Query(description="ID of the target")],
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
) -> dict:
    """Check if a target is in favorites."""
    use_case = use_case_factory()
    is_favorited = use_case.check(target_type.value, target_id)
    return {"is_favorited": is_favorited}


@router.put(
    "/reorder",
    summary="Reorder favorites",
)
@limiter.limit(RateLimits.DEFAULT)
def reorder_favorites(
    request: Request,
    data: FavoriteReorderRequest,
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
) -> dict:
    """Reorder favorites by providing a new order of IDs."""
    use_case = use_case_factory()
    use_case.reorder(data.favorite_ids)
    return {"message": "Favorites reordered successfully"}


# Convenience endpoints for specific types
@router.post(
    "/channels/{channel_id:path}",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Favorite a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def favorite_channel(
    request: Request,
    channel_id: str,
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
) -> FavoriteResponse:
    """Add a channel to favorites."""
    use_case = use_case_factory()
    try:
        dto = use_case.add("channel", channel_id)
        return _dto_to_response(dto)
    except (ChannelNotFoundError, TargetNotFoundError, InvalidTargetError) as e:
        _handle_validation_error(e)


@router.delete(
    "/channels/{channel_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unfavorite a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def unfavorite_channel(
    request: Request,
    channel_id: str,
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
):
    """Remove a channel from favorites."""
    use_case = use_case_factory()
    if not use_case.remove("channel", channel_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel is not in favorites",
        )
    return None


@router.post(
    "/notes/{note_id}",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Favorite a note",
)
@limiter.limit(RateLimits.DEFAULT)
def favorite_note(
    request: Request,
    note_id: int,
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
) -> FavoriteResponse:
    """Add a note to favorites."""
    use_case = use_case_factory()
    try:
        dto = use_case.add("note", str(note_id))
        return _dto_to_response(dto)
    except (ChannelNotFoundError, TargetNotFoundError, InvalidTargetError) as e:
        _handle_validation_error(e)


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unfavorite a note",
)
@limiter.limit(RateLimits.DEFAULT)
def unfavorite_note(
    request: Request,
    note_id: int,
    use_case_factory: Annotated[Callable[[], FavoriteCrudUseCase], Depends(get_favorite_crud_use_case_factory)],
):
    """Remove a note from favorites."""
    use_case = use_case_factory()
    if not use_case.remove("note", str(note_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note is not in favorites",
        )
    return None
