# -*- coding: utf-8 -*-
"""Pydantic models for Chat."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class GroundingSource(BaseModel):
    """Source information for grounded response."""

    source: str = Field(..., description="Source file name")
    page: int | None = Field(default=None, description="Page number if available")
    content: str = Field(default="", description="Relevant content snippet")


class ChatRequest(BaseModel):
    """Request model for chat query."""

    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: str | None = Field(default=None, description="Session ID for multi-turn conversation")


class ChatResponse(BaseModel):
    """Response model for chat."""

    query: str = Field(..., description="Original query")
    response: str = Field(..., description="Generated response")
    sources: list[GroundingSource] = Field(default_factory=list, description="Grounding sources")
    session_id: str | None = Field(default=None, description="Session ID for multi-turn conversation")
    created_at: datetime = Field(default_factory=_utc_now)


class ChatMessage(BaseModel):
    """A single chat message in history."""

    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    sources: list[GroundingSource] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)


class ChatHistory(BaseModel):
    """Chat history for a channel."""

    channel_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    total: int = Field(default=0)


class ChatSession(BaseModel):
    """Chat session for multi-turn conversation."""

    session_id: str = Field(..., description="Unique session identifier")
    channel_id: str = Field(..., description="Channel ID")
    created_at: datetime = Field(default_factory=_utc_now)
    last_activity_at: datetime = Field(default_factory=_utc_now)
    context_window: int = Field(default=10, description="Number of messages to include as context")


class SessionHistoryRequest(BaseModel):
    """Request model for session history."""

    session_id: str = Field(..., description="Session ID")


class CreateSessionRequest(BaseModel):
    """Request model for creating a new session."""

    context_window: int = Field(default=10, ge=1, le=50, description="Number of messages to include as context")
