# -*- coding: utf-8 -*-
"""Pydantic models for Document."""

from datetime import datetime, UTC
from enum import Enum
from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class UploadStatus(str, Enum):
    """Status of document upload."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentResponse(BaseModel):
    """Response model for a document."""

    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    status: UploadStatus = Field(default=UploadStatus.PENDING)
    channel_id: str = Field(..., description="Parent channel ID")
    created_at: datetime = Field(default_factory=_utc_now)
    error_message: str | None = Field(default=None)


class DocumentList(BaseModel):
    """Response model for document list."""

    documents: list[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response model for document upload initiation."""

    id: str = Field(..., description="Document/operation ID")
    filename: str
    status: UploadStatus = Field(default=UploadStatus.PROCESSING)
    message: str = Field(default="Upload in progress")


class UrlUploadRequest(BaseModel):
    """Request model for URL upload."""

    url: str = Field(..., description="URL to crawl and upload", min_length=1)
