# -*- coding: utf-8 -*-
"""Pydantic models for document/channel summarization."""

from datetime import datetime, UTC
from enum import Enum
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class SummaryType(str, Enum):
    """Summary length/format options."""

    SHORT = "short"  # 2-3 sentences
    DETAILED = "detailed"  # Comprehensive summary with sections


class SummarizeRequest(BaseModel):
    """Request model for summarization."""

    summary_type: SummaryType = Field(
        default=SummaryType.SHORT,
        description="Summary length/format: 'short' (2-3 sentences) or 'detailed' (comprehensive)",
    )


class SummarizeResponse(BaseModel):
    """Response model for summarization."""

    channel_id: str = Field(..., description="Channel ID")
    document_id: str | None = Field(default=None, description="Document ID (if single document summary)")
    summary_type: SummaryType = Field(..., description="Type of summary generated")
    summary: str = Field(..., description="Generated summary text")
    generated_at: datetime = Field(default_factory=_utc_now)
