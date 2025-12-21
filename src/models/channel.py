# -*- coding: utf-8 -*-
"""Pydantic models for Channel (File Search Store)."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class ChannelCreate(BaseModel):
    """Request model for creating a channel."""

    name: str = Field(..., min_length=1, max_length=100, description="Channel display name")
    description: str | None = Field(default=None, max_length=500, description="Channel description")


class ChannelUpdate(BaseModel):
    """Request model for updating a channel."""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="New channel name")
    description: str | None = Field(default=None, max_length=500, description="New channel description")


class ChannelResponse(BaseModel):
    """Response model for a channel."""

    id: str = Field(..., description="Channel ID (Gemini store name)")
    name: str = Field(..., description="Channel display name")
    description: str | None = Field(default=None, description="Channel description")
    created_at: datetime = Field(default_factory=_utc_now)
    file_count: int = Field(default=0, description="Number of files in channel")
    is_favorited: bool = Field(default=False, description="Whether the channel is favorited")


class ChannelList(BaseModel):
    """Response model for channel list."""

    channels: list[ChannelResponse]
    total: int
