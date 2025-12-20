# -*- coding: utf-8 -*-
"""Channel CRUD API endpoints."""

from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.models.channel import ChannelCreate, ChannelResponse, ChannelList
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.services.channel_repository import ChannelRepository

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post(
    "",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new channel",
)
def create_channel(
    data: ChannelCreate,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
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
def list_channels(
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int | None, Query(description="Maximum number of channels", ge=1, le=100)] = None,
    offset: Annotated[int, Query(description="Number of channels to skip", ge=0)] = 0,
) -> ChannelList:
    """List all channels (File Search Stores)."""
    try:
        stores = gemini.list_stores()
        repo = ChannelRepository(db)

        channels = []
        for store in stores:
            store_id = store["name"]
            # Get local metadata if exists
            local_meta = repo.get_by_gemini_id(store_id)
            channels.append(
                ChannelResponse(
                    id=store_id,
                    name=store.get("display_name", ""),
                    description=local_meta.description if local_meta else None,
                    created_at=local_meta.created_at if local_meta else datetime.now(UTC),
                    file_count=local_meta.file_count if local_meta else 0,
                )
            )

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
def get_channel(
    channel_id: str,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ChannelResponse:
    """Get a specific channel by its ID.

    Note: channel_id should be the full store name (e.g., "fileSearchStores/xxx")
    """
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time in local DB
    repo = ChannelRepository(db)
    local_meta = repo.touch(channel_id)

    return ChannelResponse(
        id=store["name"],
        name=store.get("display_name", ""),
        description=local_meta.description if local_meta else None,
        created_at=local_meta.created_at if local_meta else datetime.now(UTC),
        file_count=local_meta.file_count if local_meta else 0,
    )


@router.delete(
    "/{channel_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a channel",
)
def delete_channel(
    channel_id: str,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a channel and all its documents.

    Note: This operation cannot be undone.
    """
    # First check if channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    success = gemini.delete_store(channel_id, force=True)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete channel",
        )

    # Delete from local DB (also cascades to chat history)
    repo = ChannelRepository(db)
    repo.delete(channel_id)

    return None
