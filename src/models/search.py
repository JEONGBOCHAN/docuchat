# -*- coding: utf-8 -*-
"""Pydantic models for Multi-Channel Search."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class SearchGroundingSource(BaseModel):
    """Source information for grounded search response."""

    source: str = Field(..., description="Source file name")
    channel_id: str = Field(..., description="Channel ID where this source is from")
    channel_name: str = Field(default="", description="Channel name for display")
    page: int | None = Field(default=None, description="Page number if available")
    content: str = Field(default="", description="Relevant content snippet")


class SearchRequest(BaseModel):
    """Request model for multi-channel search."""

    channel_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of channel IDs to search (max 5)",
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Search query",
    )


class SearchResponse(BaseModel):
    """Response model for multi-channel search."""

    query: str = Field(..., description="Original query")
    response: str = Field(..., description="Generated response")
    sources: list[SearchGroundingSource] = Field(
        default_factory=list,
        description="Grounding sources with channel info",
    )
    searched_channels: list[str] = Field(
        default_factory=list,
        description="List of channel IDs that were searched",
    )
    created_at: datetime = Field(default_factory=_utc_now)
