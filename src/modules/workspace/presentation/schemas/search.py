# -*- coding: utf-8 -*-
"""Search history schemas."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class SearchHistoryItem(BaseModel):
    """A single search history entry."""

    id: int = Field(..., description="Search history ID")
    channel_id: str = Field(..., description="Channel ID (Gemini store ID)")
    query: str = Field(..., description="Search query")
    search_count: int = Field(default=1, description="Number of times this query was searched")
    created_at: datetime = Field(..., description="First search time")
    last_searched_at: datetime = Field(..., description="Last search time")


class SearchHistoryList(BaseModel):
    """Response model for search history list."""

    history: list[SearchHistoryItem] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of history entries")


class SearchSuggestion(BaseModel):
    """A search suggestion."""

    query: str = Field(..., description="Suggested query")
    search_count: int = Field(default=1, description="Popularity score")


class SearchSuggestionList(BaseModel):
    """Response model for search suggestions."""

    suggestions: list[SearchSuggestion] = Field(default_factory=list)
    query: str = Field(..., description="Original query prefix")
