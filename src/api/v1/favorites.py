# -*- coding: utf-8 -*-
"""Favorites API endpoints."""

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
from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import (
    FavoriteRepositoryPort,
    NoteRepositoryPort,
)
from src.infrastructure.di.container import (
    create_channel_port,
    create_favorite_repository_port,
    create_note_repository_port,
)

router = APIRouter(prefix="/favorites", tags=["favorites"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_favorite_repo_port(db: Session = Depends(get_db)) -> FavoriteRepositoryPort:
    """Get favorite repository port instance."""
    return create_favorite_repository_port(db)


def get_note_repo_port(db: Session = Depends(get_db)) -> NoteRepositoryPort:
    """Get note repository port instance."""
    return create_note_repository_port(db)


def _validate_target(
    target_type: TargetType,
    target_id: str,
    channel_port: ChannelPort,
    note_repo: NoteRepositoryPort,
) -> None:
    """Validate that the target exists."""
    if target_type == TargetType.CHANNEL:
        channel = channel_port.get_channel(target_id)
        if not channel:
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
) -> FavoriteResponse:
    """Add a channel, document, or note to favorites."""
    # Validate target exists
    _validate_target(data.target_type, data.target_id, channel_port, note_repo)

    # Add to favorites
    favorite = fav_repo.add(data.target_type.value, data.target_id)

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
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
):
    """Remove a channel, document, or note from favorites."""
    if not fav_repo.remove(target_type.value, target_id):
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
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
    target_type: Annotated[TargetType | None, Query(description="Filter by target type")] = None,
    limit: Annotated[int, Query(description="Maximum number of favorites", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of favorites to skip", ge=0)] = 0,
) -> FavoriteListResponse:
    """List all favorites, optionally filtered by type."""
    type_value = target_type.value if target_type else None
    favorites = fav_repo.list_all(target_type=type_value, limit=limit, offset=offset)
    total = fav_repo.count(target_type=type_value)

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
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
) -> dict:
    """Check if a target is in favorites."""
    is_favorited = fav_repo.is_favorited(target_type.value, target_id)

    return {"is_favorited": is_favorited}


@router.put(
    "/reorder",
    summary="Reorder favorites",
)
@limiter.limit(RateLimits.DEFAULT)
def reorder_favorites(
    request: Request,
    data: FavoriteReorderRequest,
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
) -> dict:
    """Reorder favorites by providing a new order of IDs."""
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
) -> FavoriteResponse:
    """Add a channel to favorites."""
    _validate_target(TargetType.CHANNEL, channel_id, channel_port, note_repo)

    favorite = fav_repo.add(TargetType.CHANNEL.value, channel_id)

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
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
):
    """Remove a channel from favorites."""
    if not fav_repo.remove(TargetType.CHANNEL.value, channel_id):
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
) -> FavoriteResponse:
    """Add a note to favorites."""
    _validate_target(TargetType.NOTE, str(note_id), channel_port, note_repo)

    favorite = fav_repo.add(TargetType.NOTE.value, str(note_id))

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
    fav_repo: Annotated[FavoriteRepositoryPort, Depends(get_favorite_repo_port)],
):
    """Remove a note from favorites."""
    if not fav_repo.remove(TargetType.NOTE.value, str(note_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note is not in favorites",
        )

    return None
