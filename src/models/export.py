# -*- coding: utf-8 -*-
"""Pydantic models for Export functionality."""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

from src.models.chat import ChatMessage, GroundingSource
from src.models.note import NoteResponse


class ExportFormat(str, Enum):
    """Supported export formats."""

    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"


class NoteExportData(BaseModel):
    """Export data for a single note."""

    id: int
    title: str
    content: str
    sources: list[GroundingSource] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ChatExportData(BaseModel):
    """Export data for chat history."""

    channel_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    exported_at: datetime


class ChannelExportMetadata(BaseModel):
    """Channel metadata for export."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime
    file_count: int
    total_size_bytes: int


class ChannelFullExport(BaseModel):
    """Full channel export including notes and chat history."""

    metadata: ChannelExportMetadata
    notes: list[NoteExportData] = Field(default_factory=list)
    chat_history: list[ChatMessage] = Field(default_factory=list)
    exported_at: datetime


class ExportResponse(BaseModel):
    """Response for export request with file content."""

    filename: str
    content_type: str
    data: str = Field(..., description="Base64 encoded content for binary, raw content for text")
