# -*- coding: utf-8 -*-
"""Audio Overview (Podcast) schemas."""

from datetime import datetime
from pydantic import BaseModel, Field

from src.shared.kernel.contracts.dto.enums import AudioStatus, VoiceType  # noqa: F401


class DialogueLine(BaseModel):
    """A single line of dialogue in the podcast script."""

    speaker: str = Field(description="Speaker name (Host A or Host B)")
    text: str = Field(description="The dialogue text")
    voice: VoiceType = Field(description="Voice type to use")


class PodcastScript(BaseModel):
    """Generated podcast script."""

    title: str = Field(description="Podcast episode title")
    introduction: str = Field(description="Brief introduction text")
    dialogue: list[DialogueLine] = Field(description="List of dialogue lines")
    conclusion: str = Field(description="Closing remarks")
    estimated_duration_seconds: int = Field(description="Estimated audio duration")


class GenerateAudioRequest(BaseModel):
    """Request to generate audio overview."""

    duration_minutes: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Target duration in minutes (1-15)",
    )
    style: str = Field(
        default="conversational",
        description="Style: 'conversational' (casual) or 'professional' (formal)",
    )
    host_a_voice: VoiceType = Field(
        default=VoiceType.MALE_1,
        description="Voice for Host A",
    )
    host_b_voice: VoiceType = Field(
        default=VoiceType.FEMALE_1,
        description="Voice for Host B",
    )
    language: str = Field(
        default="ko",
        description="Language code (ko, en, etc.)",
    )


class AudioOverviewResponse(BaseModel):
    """Response for audio overview generation."""

    id: str = Field(description="Audio overview ID")
    channel_id: str = Field(description="Channel ID")
    status: AudioStatus = Field(description="Current status")
    title: str | None = Field(default=None, description="Episode title")
    duration_seconds: int | None = Field(default=None, description="Audio duration")
    audio_url: str | None = Field(default=None, description="URL to audio file")
    script: PodcastScript | None = Field(default=None, description="Generated script")
    created_at: datetime = Field(description="Creation timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    error: str | None = Field(default=None, description="Error message if failed")


class AudioOverviewListResponse(BaseModel):
    """Response for listing audio overviews."""

    items: list[AudioOverviewResponse] = Field(description="List of audio overviews")
    total: int = Field(description="Total count")


class ScriptOnlyResponse(BaseModel):
    """Response containing only the script (for preview)."""

    channel_id: str = Field(description="Channel ID")
    script: PodcastScript = Field(description="Generated script")
    generated_at: datetime = Field(description="Generation timestamp")
