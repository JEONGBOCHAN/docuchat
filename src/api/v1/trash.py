# -*- coding: utf-8 -*-
"""Trash (soft delete) API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.trash import TrashList, TrashItemType, RestoreResponse, EmptyTrashResponse
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.trash_repository import TrashRepository

router = APIRouter(prefix="/trash", tags=["trash"])


@router.get(
    "",
    response_model=TrashList,
    summary="List all trashed items",
)
@limiter.limit(RateLimits.DEFAULT)
def list_trash(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TrashList:
    """List all items in the trash (soft-deleted channels and notes)."""
    trash_repo = TrashRepository(db)
    items = trash_repo.get_all_trashed_items()

    return TrashList(items=items, total=len(items))


@router.post(
    "/{item_type}/{item_id}/restore",
    response_model=RestoreResponse,
    summary="Restore a trashed item",
)
@limiter.limit(RateLimits.DEFAULT)
def restore_item(
    request: Request,
    item_type: TrashItemType,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> RestoreResponse:
    """Restore a soft-deleted item from the trash.

    Args:
        item_type: Type of item ('channel' or 'note')
        item_id: The item's database ID
    """
    trash_repo = TrashRepository(db)

    if item_type == TrashItemType.CHANNEL:
        channel = trash_repo.restore_channel(item_id)
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trashed channel not found: {item_id}",
            )
        return RestoreResponse(
            id=channel.id,
            type=TrashItemType.CHANNEL,
            message=f"Channel '{channel.name}' has been restored",
        )

    elif item_type == TrashItemType.NOTE:
        note = trash_repo.restore_note(item_id)
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trashed note not found: {item_id}",
            )
        return RestoreResponse(
            id=note.id,
            type=TrashItemType.NOTE,
            message=f"Note '{note.title}' has been restored",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid item type: {item_type}",
    )


@router.delete(
    "/{item_type}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a trashed item",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_item_permanently(
    request: Request,
    item_type: TrashItemType,
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
):
    """Permanently delete a trashed item. This cannot be undone.

    For channels, this also deletes the Gemini File Search Store and all documents.

    Args:
        item_type: Type of item ('channel' or 'note')
        item_id: The item's database ID
    """
    from src.models.db_models import ChannelMetadata

    trash_repo = TrashRepository(db)

    if item_type == TrashItemType.CHANNEL:
        # Get channel info before deleting for Gemini cleanup
        channel = db.query(ChannelMetadata).filter(
            ChannelMetadata.id == item_id,
            ChannelMetadata.deleted_at.isnot(None),
        ).first()

        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trashed channel not found: {item_id}",
            )

        # Delete from Gemini
        gemini.delete_store(channel.gemini_store_id, force=True)

        # Delete from DB
        if not trash_repo.permanent_delete_channel(item_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete channel",
            )
        return None

    elif item_type == TrashItemType.NOTE:
        if not trash_repo.permanent_delete_note(item_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trashed note not found: {item_id}",
            )
        return None

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid item type: {item_type}",
    )


@router.delete(
    "",
    response_model=EmptyTrashResponse,
    summary="Empty the trash",
)
@limiter.limit(RateLimits.DEFAULT)
def empty_trash(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    confirm: Annotated[bool, Query(description="Confirm permanent deletion")] = False,
) -> EmptyTrashResponse:
    """Permanently delete all items in the trash. This cannot be undone.

    Requires confirm=true query parameter to prevent accidental deletion.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please confirm by setting confirm=true",
        )

    trash_repo = TrashRepository(db)

    # First, delete all trashed channels from Gemini
    from src.models.db_models import ChannelMetadata
    trashed_channels = db.query(ChannelMetadata).filter(
        ChannelMetadata.deleted_at.isnot(None)
    ).all()

    for channel in trashed_channels:
        gemini.delete_store(channel.gemini_store_id, force=True)

    # Then delete from DB
    deleted_channels, deleted_notes = trash_repo.empty_trash()

    return EmptyTrashResponse(
        deleted_channels=deleted_channels,
        deleted_notes=deleted_notes,
        message=f"Permanently deleted {deleted_channels} channels and {deleted_notes} notes",
    )


@router.get(
    "/stats",
    summary="Get trash statistics",
)
@limiter.limit(RateLimits.DEFAULT)
def get_trash_stats(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Get statistics about items in the trash."""
    trash_repo = TrashRepository(db)
    return trash_repo.get_trash_stats()
