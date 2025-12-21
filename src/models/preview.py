# -*- coding: utf-8 -*-
"""Pydantic models for Document Preview."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class TextHighlight(BaseModel):
    """Represents a highlighted text segment."""

    start: int = Field(..., description="Start position in text")
    end: int = Field(..., description="End position in text")
    text: str = Field(..., description="The matched text")


class DocumentPreviewPage(BaseModel):
    """A single page/chunk of document preview."""

    page_number: int = Field(..., description="Page number (1-based)")
    content: str = Field(..., description="Text content of the page")
    highlights: list[TextHighlight] = Field(
        default_factory=list,
        description="Highlighted segments if search term provided",
    )


class DocumentPreviewResponse(BaseModel):
    """Response model for document preview."""

    document_id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    total_pages: int = Field(..., description="Total number of pages")
    total_characters: int = Field(..., description="Total character count")
    current_page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Characters per page")
    content: str = Field(..., description="Text content of current page")
    highlights: list[TextHighlight] = Field(
        default_factory=list,
        description="Highlighted segments if search term provided",
    )
    has_next: bool = Field(..., description="Whether next page exists")
    has_previous: bool = Field(..., description="Whether previous page exists")
    cached_at: datetime | None = Field(
        default=None,
        description="When the preview was cached",
    )


class DocumentPreviewRequest(BaseModel):
    """Request model for document preview."""

    search_term: str | None = Field(
        default=None,
        description="Optional search term to highlight",
    )


class SourceLocation(BaseModel):
    """Location of a source citation in document."""

    document_id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Document filename")
    page_number: int = Field(..., description="Page number (1-based)")
    position: int = Field(..., description="Character position in full text")
    context: str = Field(..., description="Surrounding text context")
    highlights: list[TextHighlight] = Field(
        default_factory=list,
        description="Highlighted matching text",
    )


class SourceLocationResponse(BaseModel):
    """Response for source location lookup."""

    found: bool = Field(..., description="Whether the source was found")
    location: SourceLocation | None = Field(
        default=None,
        description="Location details if found",
    )
