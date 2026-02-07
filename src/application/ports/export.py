# -*- coding: utf-8 -*-
"""
Export ports and DTOs.

Defines the ExportFormat enum and data transfer objects used by
the ExportService in the application layer. These replace direct
dependency on presentation-layer Pydantic models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any


class ExportFormat(str, Enum):
    """Supported export formats."""

    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"


@dataclass
class GroundingSourceDTO:
    """Source information for grounded response (application-layer DTO)."""

    source: str = ""
    page: int | None = None
    content: str = ""
    url: str | None = None
    source_type: str = "document"


@dataclass
class NoteExportDTO:
    """Export data for a single note."""

    id: int
    title: str
    content: str
    sources: list[GroundingSourceDTO] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ChatMessageExportDTO:
    """A single chat message for export."""

    role: str
    content: str
    sources: list[GroundingSourceDTO] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ChatExportDTO:
    """Export data for chat history."""

    channel_id: str
    messages: list[ChatMessageExportDTO] = field(default_factory=list)
    exported_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ChannelExportMetadataDTO:
    """Channel metadata for export."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    file_count: int = 0
    total_size_bytes: int = 0


@dataclass
class ChannelFullExportDTO:
    """Full channel export including notes and chat history."""

    metadata: ChannelExportMetadataDTO
    notes: list[NoteExportDTO] = field(default_factory=list)
    chat_history: list[ChatMessageExportDTO] = field(default_factory=list)
    exported_at: datetime = field(default_factory=lambda: datetime.now(UTC))
