# -*- coding: utf-8 -*-
"""Favorite/pin schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.modules.workspace.domain.value_objects import TargetType

__all__ = ["TargetType", "FavoriteCreate", "FavoriteResponse",
           "FavoriteListResponse", "FavoriteWithDetails",
           "FavoriteListWithDetailsResponse", "FavoriteReorderRequest"]


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
    details: dict[str, Any] | None = None


class FavoriteListWithDetailsResponse(BaseModel):
    """Response model for list of favorites with details."""

    favorites: list[FavoriteWithDetails]
    total: int


class FavoriteReorderRequest(BaseModel):
    """Request model for reordering favorites."""

    favorite_ids: list[int] = Field(description="Ordered list of favorite IDs")
