# -*- coding: utf-8 -*-
"""Pydantic models for YouTube source."""

from datetime import datetime, UTC
from pydantic import BaseModel, Field, field_validator
import re


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class YouTubeSourceRequest(BaseModel):
    """Request model for adding YouTube source."""

    url: str = Field(..., description="YouTube video URL", min_length=1)

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the URL is a valid YouTube URL."""
        youtube_patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in youtube_patterns:
            if re.match(pattern, v):
                return v

        raise ValueError("Invalid YouTube URL format")


class YouTubeMetadata(BaseModel):
    """YouTube video metadata."""

    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(default="", description="Video title")
    channel_name: str = Field(default="", description="Channel name")
    duration_seconds: int | None = Field(default=None, description="Video duration in seconds")
    language: str = Field(default="", description="Transcript language")


class YouTubeSourceResponse(BaseModel):
    """Response model for YouTube source addition."""

    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    document_id: str = Field(..., description="Created document ID in channel")
    transcript_length: int = Field(..., description="Transcript character count")
    language: str = Field(default="", description="Transcript language")
    message: str = Field(default="YouTube source added successfully")
    created_at: datetime = Field(default_factory=_utc_now)


class YouTubeTranscriptSegment(BaseModel):
    """A segment of YouTube transcript."""

    text: str = Field(..., description="Transcript text")
    start: float = Field(..., description="Start time in seconds")
    duration: float = Field(..., description="Duration in seconds")


class YouTubeTranscript(BaseModel):
    """Complete YouTube transcript."""

    video_id: str = Field(..., description="YouTube video ID")
    language: str = Field(..., description="Transcript language code")
    segments: list[YouTubeTranscriptSegment] = Field(
        default_factory=list,
        description="Transcript segments with timing",
    )

    @property
    def full_text(self) -> str:
        """Get full transcript text without timing."""
        return " ".join(segment.text for segment in self.segments)

    @property
    def formatted_text(self) -> str:
        """Get formatted transcript with timestamps."""
        lines = []
        for segment in self.segments:
            minutes = int(segment.start // 60)
            seconds = int(segment.start % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            lines.append(f"{timestamp} {segment.text}")
        return "\n".join(lines)
