# -*- coding: utf-8 -*-
"""Note schemas."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field

from src.modules.workspace.presentation.schemas.chat import GroundingSource


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class NoteCreate(BaseModel):
    """Request model for creating a note."""

    title: str = Field(..., min_length=1, max_length=200, description="Note title")
    content: str = Field(..., min_length=1, description="Note content (Markdown supported)")
    sources: list[GroundingSource] = Field(default_factory=list, description="Sources if from AI response")


class NoteUpdate(BaseModel):
    """Request model for updating a note."""

    title: str | None = Field(default=None, min_length=1, max_length=200, description="New title")
    content: str | None = Field(default=None, min_length=1, description="New content")


class NoteResponse(BaseModel):
    """Response model for a note."""

    id: int = Field(..., description="Note ID")
    channel_id: str = Field(..., description="Channel ID (Gemini store ID)")
    title: str = Field(..., description="Note title")
    content: str = Field(..., description="Note content")
    sources: list[GroundingSource] = Field(default_factory=list, description="Grounding sources")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class NoteList(BaseModel):
    """Response model for list of notes."""

    notes: list[NoteResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of notes")
