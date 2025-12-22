# -*- coding: utf-8 -*-
"""Channel CRUD API endpoints."""

from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.channel import ChannelCreate, ChannelUpdate, ChannelResponse, ChannelList
from src.models.favorite import TargetType
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.channel_repository import ChannelRepository
from src.services.favorite_repository import FavoriteRepository
from src.services.trash_repository import TrashRepository
from src.services.cache_service import CacheService, get_cache_service

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post(
    "",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new channel",
)
@limiter.limit(RateLimits.DEFAULT)
def create_channel(
    request: Request,
    data: ChannelCreate,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> ChannelResponse:
    """Create a new channel (Gemini File Search Store).

    A channel is a container for documents that can be searched together.
    """
    try:
        store = gemini.create_store(data.name)
        store_id = store["name"]

        # Save to local metadata DB
        repo = ChannelRepository(db)
        channel = repo.create(
            gemini_store_id=store_id,
            name=data.name,
            description=data.description,
        )

        # Invalidate store list cache
        cache.invalidate_store_cache()

        return ChannelResponse(
            id=store_id,
            name=data.name,
            description=channel.description,
            created_at=channel.created_at,
            file_count=0,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create channel: {str(e)}",
        )


@router.get(
    "",
    response_model=ChannelList,
    summary="List all channels",
)
@limiter.limit(RateLimits.DEFAULT)
def list_channels(
    request: Request,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
    limit: Annotated[int | None, Query(description="Maximum number of channels", ge=1, le=100)] = None,
    offset: Annotated[int, Query(description="Number of channels to skip", ge=0)] = 0,
) -> ChannelList:
    """List all channels (File Search Stores)."""
    try:
        # Try to get from cache first
        stores = cache.get_store_list()
        if stores is None:
            stores = gemini.list_stores()
            cache.set_store_list(stores)

        repo = ChannelRepository(db)
        fav_repo = FavoriteRepository(db)
        favorited_ids = fav_repo.get_favorited_ids(TargetType.CHANNEL)

        channels = []
        for store in stores:
            store_id = store["name"]
            # Get local metadata if exists
            local_meta = repo.get_by_gemini_id(store_id)
            # Skip if channel is soft-deleted
            if local_meta and local_meta.is_deleted:
                continue
            channels.append(
                ChannelResponse(
                    id=store_id,
                    name=store.get("display_name", ""),
                    description=local_meta.description if local_meta else None,
                    created_at=local_meta.created_at if local_meta else datetime.now(UTC),
                    file_count=local_meta.file_count if local_meta else 0,
                    is_favorited=store_id in favorited_ids,
                )
            )

        # Sort: favorited channels first, then by created_at
        # Handle timezone-naive/aware datetime comparison (SQLite doesn't preserve timezone)
        def get_naive_ts(c):
            ts = c.created_at
            if ts and ts.tzinfo is not None:
                return ts.replace(tzinfo=None)
            return ts if ts else datetime.min
        channels.sort(key=lambda c: (not c.is_favorited, get_naive_ts(c)))

        # Apply pagination
        total = len(channels)
        if offset:
            channels = channels[offset:]
        if limit:
            channels = channels[:limit]

        return ChannelList(channels=channels, total=total)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list channels: {str(e)}",
        )


@router.get(
    "/{channel_id:path}",
    response_model=ChannelResponse,
    summary="Get a channel by ID",
)
@limiter.limit(RateLimits.DEFAULT)
def get_channel(
    request: Request,
    channel_id: str,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> ChannelResponse:
    """Get a specific channel by its ID.

    Note: channel_id should be the full store name (e.g., "fileSearchStores/xxx")
    """
    repo = ChannelRepository(db)
    fav_repo = FavoriteRepository(db)

    # Check if channel is soft-deleted
    local_meta = repo.get_by_gemini_id(channel_id)
    if local_meta and local_meta.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Check if favorited (not cached as it can change frequently)
    is_favorited = fav_repo.is_favorited(TargetType.CHANNEL, channel_id)

    # Try to get from cache first
    cached_info = cache.get_channel_info(channel_id)
    if cached_info:
        # Update last accessed time in local DB
        repo.touch(channel_id)
        cached_info["is_favorited"] = is_favorited
        return ChannelResponse(**cached_info)

    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time in local DB
    local_meta = repo.touch(channel_id)

    response = ChannelResponse(
        id=store["name"],
        name=store.get("display_name", ""),
        description=local_meta.description if local_meta else None,
        created_at=local_meta.created_at if local_meta else datetime.now(UTC),
        file_count=local_meta.file_count if local_meta else 0,
        is_favorited=is_favorited,
    )

    # Cache the response
    cache.set_channel_info(channel_id, response.model_dump(mode="json"))

    return response


@router.put(
    "/{channel_id:path}",
    response_model=ChannelResponse,
    summary="Update a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def update_channel(
    request: Request,
    channel_id: str,
    data: ChannelUpdate,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> ChannelResponse:
    """Update a channel's name and/or description.

    Note: channel_id should be the full store name (e.g., "fileSearchStores/xxx")
    """
    # Check if channel exists in Gemini
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Check if at least one field is provided
    if data.name is None and data.description is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of 'name' or 'description' must be provided",
        )

    # Update local metadata
    repo = ChannelRepository(db)
    local_meta = repo.get_by_gemini_id(channel_id)

    if not local_meta:
        # Create local metadata if not exists
        local_meta = repo.create(
            gemini_store_id=channel_id,
            name=data.name or store.get("display_name", ""),
            description=data.description,
        )
    else:
        # Update existing metadata
        local_meta = repo.update(
            gemini_store_id=channel_id,
            name=data.name,
            description=data.description,
        )

    # Invalidate channel and store caches
    cache.invalidate_channel_cache(channel_id)
    cache.invalidate_store_cache()

    return ChannelResponse(
        id=channel_id,
        name=local_meta.name,
        description=local_meta.description,
        created_at=local_meta.created_at,
        file_count=local_meta.file_count,
    )


@router.delete(
    "/{channel_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_channel(
    request: Request,
    channel_id: str,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
):
    """Delete a channel (moves to trash).

    The channel can be restored from the trash within 30 days.
    Use DELETE /trash/channel/{id} for permanent deletion.
    """
    # First check if channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Soft delete (move to trash)
    trash_repo = TrashRepository(db)
    channel = trash_repo.soft_delete_channel(channel_id)

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel metadata not found: {channel_id}",
        )

    # Invalidate all caches related to this channel
    cache.invalidate_channel(channel_id)

    return None
