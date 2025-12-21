# -*- coding: utf-8 -*-
"""Favorite/pin models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TargetType(str, Enum):
    """Favorite target types."""

    CHANNEL = "channel"
    DOCUMENT = "document"
    NOTE = "note"


class FavoriteCreate(BaseModel):
    """Request model for creating a favorite."""

    target_type: TargetType = Field(description="Type of the target (channel, document, note)")
    target_id: str = Field(description="ID of the target")


class FavoriteResponse(BaseModel):
    """Response model for a favorite."""

    id: int
    target_type: TargetType
    target_id: str
    display_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteListResponse(BaseModel):
    """Response model for list of favorites."""

    favorites: list[FavoriteResponse]
    total: int


class FavoriteWithDetails(BaseModel):
    """Favorite with target details."""

    id: int
    target_type: TargetType
    target_id: str
    display_order: int
    created_at: datetime
    details: dict[str, Any] | None = None  # Channel/Document/Note details


class FavoriteListWithDetailsResponse(BaseModel):
    """Response model for list of favorites with details."""

    favorites: list[FavoriteWithDetails]
    total: int


class FavoriteReorderRequest(BaseModel):
    """Request model for reordering favorites."""

    favorite_ids: list[int] = Field(description="Ordered list of favorite IDs")
