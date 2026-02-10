# -*- coding: utf-8 -*-
"""Trash (soft delete) API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.trash import TrashList, TrashItemType, RestoreResponse, EmptyTrashResponse
from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import TrashRepositoryPort
from src.core.database import get_db
from src.modules.workspace.public import (
    create_channel_port,
    create_trash_repository_port,
)
from src.core.rate_limiter import limiter, RateLimits
from src.shared.kernel.presentation.dependencies.admin_auth import require_admin_key

router = APIRouter(prefix="/trash", tags=["trash"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_trash_repo_port(db: Session = Depends(get_db)) -> TrashRepositoryPort:
    """Get trash repository port instance."""
    return create_trash_repository_port(db)


@router.get(
    "",
    response_model=TrashList,
    summary="List all trashed items",
)
@limiter.limit(RateLimits.DEFAULT)
def list_trash(
    request: Request,
    trash_repo: Annotated[TrashRepositoryPort, Depends(get_trash_repo_port)],
) -> TrashList:
    """List all items in the trash (soft-deleted channels and notes)."""
    from src.models.trash import TrashItem
    items_dto = trash_repo.get_all_trashed_items()

    # Convert DTOs to Pydantic models
    items = [
        TrashItem(
            id=dto.id,
            type=TrashItemType(dto.type),
            name=dto.name,
            deleted_at=dto.deleted_at,
        )
        for dto in items_dto
    ]

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
    trash_repo: Annotated[TrashRepositoryPort, Depends(get_trash_repo_port)],
) -> RestoreResponse:
    """Restore a soft-deleted item from the trash.

    Args:
        item_type: Type of item ('channel' or 'note')
        item_id: The item's database ID
    """
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
    trash_repo: Annotated[TrashRepositoryPort, Depends(get_trash_repo_port)],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    _admin: Annotated[str, Depends(require_admin_key)],
):
    """Permanently delete a trashed item. This cannot be undone.

    For channels, this also deletes the Gemini File Search Store and all documents.

    Args:
        item_type: Type of item ('channel' or 'note')
        item_id: The item's database ID
    """
    if item_type == TrashItemType.CHANNEL:
        # Get channel info before deleting for Gemini cleanup
        channel_dto = trash_repo.get_trashed_channel_by_db_id(item_id)

        if not channel_dto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trashed channel not found: {item_id}",
            )

        # Delete from Gemini — only proceed with DB delete if successful
        gemini_success = channel_port.delete_channel(channel_dto.gemini_store_id, force=True)
        if not gemini_success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to delete channel from external storage. Channel remains in trash for retry.",
            )

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
    trash_repo: Annotated[TrashRepositoryPort, Depends(get_trash_repo_port)],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    _admin: Annotated[str, Depends(require_admin_key)],
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

    # Delete trashed channels — only DB-delete those that succeed in Gemini
    trashed_channel_dtos = trash_repo.get_all_trashed_channels()
    deleted_channels = 0
    failed_channels = 0

    for channel_dto in trashed_channel_dtos:
        success = channel_port.delete_channel(channel_dto.gemini_store_id, force=True)
        if success:
            trash_repo.permanent_delete_channel(channel_dto.id)
            deleted_channels += 1
        else:
            failed_channels += 1

    # Delete trashed notes (no external resources, safe to delete directly)
    all_items = trash_repo.get_all_trashed_items()
    deleted_notes = 0
    for item in all_items:
        if item.type == "note":
            if trash_repo.permanent_delete_note(item.id):
                deleted_notes += 1

    message = f"Permanently deleted {deleted_channels} channels and {deleted_notes} notes"
    if failed_channels > 0:
        message += f" ({failed_channels} channels failed external deletion and remain in trash)"

    return EmptyTrashResponse(
        deleted_channels=deleted_channels,
        deleted_notes=deleted_notes,
        failed_channels=failed_channels,
        message=message,
    )


@router.get(
    "/stats",
    summary="Get trash statistics",
)
@limiter.limit(RateLimits.DEFAULT)
def get_trash_stats(
    request: Request,
    trash_repo: Annotated[TrashRepositoryPort, Depends(get_trash_repo_port)],
) -> dict:
    """Get statistics about items in the trash."""
    return trash_repo.get_trash_stats()
