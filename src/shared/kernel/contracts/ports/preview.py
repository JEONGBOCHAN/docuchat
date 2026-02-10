# -*- coding: utf-8 -*-
"""
Preview ports and DTOs.

Defines data transfer objects for the PreviewService in the application layer.
These replace direct dependency on presentation-layer Pydantic models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TextHighlightDTO:
    """Represents a highlighted text segment."""

    start: int
    end: int
    text: str


@dataclass
class DocumentPreviewDTO:
    """Result of document preview request."""

    document_id: str
    filename: str
    total_pages: int
    total_characters: int
    current_page: int
    page_size: int
    content: str
    highlights: list[TextHighlightDTO] = field(default_factory=list)
    has_next: bool = False
    has_previous: bool = False
    cached_at: datetime | None = None


@dataclass
class SourceLocationDTO:
    """Location of a source citation in document."""

    document_id: str
    filename: str
    page_number: int
    position: int
    context: str
    highlights: list[TextHighlightDTO] = field(default_factory=list)


@dataclass
class SourceLocationResultDTO:
    """Result of source location lookup."""

    found: bool
    location: SourceLocationDTO | None = None
