# -*- coding: utf-8 -*-
"""Pydantic models for inline citations and source navigation."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class CitationLocation(BaseModel):
    """Location information for navigating to source."""

    page: int | None = Field(default=None, description="Page number (1-indexed)")
    start_index: int | None = Field(
        default=None, description="Character start index in source"
    )
    end_index: int | None = Field(
        default=None, description="Character end index in source"
    )


class Citation(BaseModel):
    """Detailed citation with navigation information."""

    index: int = Field(..., description="Citation number [1], [2], etc.")
    source: str = Field(..., description="Source file name")
    content: str = Field(default="", description="Quoted text snippet")
    location: CitationLocation = Field(
        default_factory=CitationLocation,
        description="Location info for navigation",
    )


class CitedResponse(BaseModel):
    """Response with inline citations."""

    query: str = Field(..., description="Original query")
    response: str = Field(..., description="Response text with inline citations [1], [2]")
    response_plain: str = Field(..., description="Response text without citations")
    citations: list[Citation] = Field(
        default_factory=list,
        description="List of citations referenced in the response",
    )
    created_at: datetime = Field(default_factory=_utc_now)


class CitationRequest(BaseModel):
    """Request model for chat with citations."""

    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    include_citations: bool = Field(
        default=True,
        description="Whether to include inline citations in response",
    )


class CitationDetail(BaseModel):
    """Detailed information about a single citation for navigation."""

    index: int = Field(..., description="Citation number")
    source: str = Field(..., description="Source file name")
    content: str = Field(..., description="Full quoted text")
    context: str = Field(default="", description="Surrounding context text")
    location: CitationLocation = Field(default_factory=CitationLocation)
    highlight_text: str = Field(
        default="",
        description="Text to highlight in the source document",
    )
