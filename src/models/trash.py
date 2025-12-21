# -*- coding: utf-8 -*-
"""Trash (soft delete) related models."""

from datetime import datetime, UTC
from enum import Enum

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class TrashItemType(str, Enum):
    """Type of trashed item."""

    CHANNEL = "channel"
    NOTE = "note"


class TrashItem(BaseModel):
    """Represents a trashed item (channel or note)."""

    id: int = Field(..., description="Item ID")
    type: TrashItemType = Field(..., description="Type of item (channel or note)")
    name: str = Field(..., description="Item name")
    description: str | None = Field(None, description="Item description")
    deleted_at: datetime = Field(..., description="When the item was deleted")
    # For channels
    gemini_store_id: str | None = Field(None, description="Gemini store ID (for channels)")
    file_count: int | None = Field(None, description="Number of files (for channels)")
    # For notes
    channel_id: int | None = Field(None, description="Parent channel ID (for notes)")


class TrashList(BaseModel):
    """List of trashed items."""

    items: list[TrashItem] = Field(default_factory=list, description="List of trashed items")
    total: int = Field(..., description="Total count of trashed items")


class RestoreResponse(BaseModel):
    """Response after restoring an item."""

    id: int = Field(..., description="Restored item ID")
    type: TrashItemType = Field(..., description="Type of restored item")
    message: str = Field(..., description="Success message")
    restored_at: datetime = Field(default_factory=_utc_now, description="When the item was restored")


class EmptyTrashResponse(BaseModel):
    """Response after emptying trash."""

    deleted_channels: int = Field(..., description="Number of permanently deleted channels")
    deleted_notes: int = Field(..., description="Number of permanently deleted notes")
    message: str = Field(..., description="Success message")
