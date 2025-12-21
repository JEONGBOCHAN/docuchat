# -*- coding: utf-8 -*-
"""Favorites API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.models.favorite import (
    FavoriteCreate,
    FavoriteListResponse,
    FavoriteReorderRequest,
    FavoriteResponse,
    TargetType,
)
from src.services.favorite_repository import FavoriteRepository
from src.services.gemini import GeminiService, get_gemini_service
from src.services.channel_repository import ChannelRepository
from src.services.note_repository import NoteRepository

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _validate_target(
    target_type: TargetType,
    target_id: str,
    gemini: GeminiService,
    db: Session,
) -> None:
    """Validate that the target exists."""
    if target_type == TargetType.CHANNEL:
        store = gemini.get_store(target_id)
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel not found: {target_id}",
            )
    elif target_type == TargetType.DOCUMENT:
        # Documents are stored in Gemini, validate by checking operation status
        # For simplicity, we'll accept any document ID format
        if not target_id or not target_id.startswith("files/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid document ID format. Expected 'files/xxx'",
            )
    elif target_type == TargetType.NOTE:
        try:
            note_id = int(target_id)
            note_repo = NoteRepository(db)
            note = note_repo.get_by_id(note_id)
            if not note:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Note not found: {target_id}",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid note ID format. Expected integer.",
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> FavoriteResponse:
    """Add a channel, document, or note to favorites."""
    # Validate target exists
    _validate_target(data.target_type, data.target_id, gemini, db)

    # Add to favorites
    fav_repo = FavoriteRepository(db)
    favorite = fav_repo.add(data.target_type, data.target_id)

    return FavoriteResponse(
        id=favorite.id,
        target_type=TargetType(favorite.target_type),
        target_id=favorite.target_id,
        display_order=favorite.display_order,
        created_at=favorite.created_at,
    )


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
    db: Annotated[Session, Depends(get_db)],
):
    """Remove a channel, document, or note from favorites."""
    fav_repo = FavoriteRepository(db)

    if not fav_repo.remove(target_type, target_id):
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
    db: Annotated[Session, Depends(get_db)],
    target_type: Annotated[TargetType | None, Query(description="Filter by target type")] = None,
    limit: Annotated[int, Query(description="Maximum number of favorites", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of favorites to skip", ge=0)] = 0,
) -> FavoriteListResponse:
    """List all favorites, optionally filtered by type."""
    fav_repo = FavoriteRepository(db)

    favorites = fav_repo.list_all(target_type=target_type, limit=limit, offset=offset)
    total = fav_repo.count(target_type=target_type)

    return FavoriteListResponse(
        favorites=[
            FavoriteResponse(
                id=f.id,
                target_type=TargetType(f.target_type),
                target_id=f.target_id,
                display_order=f.display_order,
                created_at=f.created_at,
            )
            for f in favorites
        ],
        total=total,
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
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Check if a target is in favorites."""
    fav_repo = FavoriteRepository(db)
    is_favorited = fav_repo.is_favorited(target_type, target_id)

    return {"is_favorited": is_favorited}


@router.put(
    "/reorder",
    summary="Reorder favorites",
)
@limiter.limit(RateLimits.DEFAULT)
def reorder_favorites(
    request: Request,
    data: FavoriteReorderRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Reorder favorites by providing a new order of IDs."""
    fav_repo = FavoriteRepository(db)
    fav_repo.reorder(data.favorite_ids)

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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> FavoriteResponse:
    """Add a channel to favorites."""
    _validate_target(TargetType.CHANNEL, channel_id, gemini, db)

    fav_repo = FavoriteRepository(db)
    favorite = fav_repo.add(TargetType.CHANNEL, channel_id)

    return FavoriteResponse(
        id=favorite.id,
        target_type=TargetType(favorite.target_type),
        target_id=favorite.target_id,
        display_order=favorite.display_order,
        created_at=favorite.created_at,
    )


@router.delete(
    "/channels/{channel_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unfavorite a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def unfavorite_channel(
    request: Request,
    channel_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Remove a channel from favorites."""
    fav_repo = FavoriteRepository(db)

    if not fav_repo.remove(TargetType.CHANNEL, channel_id):
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> FavoriteResponse:
    """Add a note to favorites."""
    _validate_target(TargetType.NOTE, str(note_id), gemini, db)

    fav_repo = FavoriteRepository(db)
    favorite = fav_repo.add(TargetType.NOTE, str(note_id))

    return FavoriteResponse(
        id=favorite.id,
        target_type=TargetType(favorite.target_type),
        target_id=favorite.target_id,
        display_order=favorite.display_order,
        created_at=favorite.created_at,
    )


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unfavorite a note",
)
@limiter.limit(RateLimits.DEFAULT)
def unfavorite_note(
    request: Request,
    note_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Remove a note from favorites."""
    fav_repo = FavoriteRepository(db)

    if not fav_repo.remove(TargetType.NOTE, str(note_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note is not in favorites",
        )

    return None
