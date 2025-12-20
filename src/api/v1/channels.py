# -*- coding: utf-8 -*-
"""Channel CRUD API endpoints."""

from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.channel import ChannelCreate, ChannelResponse, ChannelList
from src.services.gemini import GeminiService, get_gemini_service

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
) -> ChannelResponse:
    """Create a new channel (Gemini File Search Store).

    A channel is a container for documents that can be searched together.
    """
    try:
        store = gemini.create_store(data.name)
        return ChannelResponse(
            id=store["name"],
            name=data.name,
            created_at=datetime.now(UTC),
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
) -> ChannelList:
    """List all channels (File Search Stores)."""
    try:
        stores = gemini.list_stores()
        channels = [
            ChannelResponse(
                id=store["name"],
                name=store.get("display_name", ""),
                created_at=datetime.now(UTC),  # API doesn't return created_at
                file_count=0,  # Would need separate API call
            )
            for store in stores
        ]
        return ChannelList(channels=channels, total=len(channels))
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
    return ChannelResponse(
        id=store["name"],
        name=store.get("display_name", ""),
        created_at=datetime.now(UTC),
        file_count=0,
    )


@router.delete(
    "/{channel_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a channel",
)
def delete_channel(
    channel_id: str,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
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
    return None
