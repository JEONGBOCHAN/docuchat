# -*- coding: utf-8 -*-
"""Timeline and Briefing schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    """A single event in a timeline."""

    date: str = Field(description="Date or time period of the event")
    title: str = Field(description="Short title of the event")
    description: str = Field(description="Detailed description of the event")
    source: str | None = Field(default=None, description="Source document name")


class TimelineResponse(BaseModel):
    """Response for timeline generation."""

    channel_id: str = Field(description="Channel ID")
    events: list[TimelineEvent] = Field(description="List of timeline events")
    total: int = Field(description="Total number of events")
    generated_at: datetime = Field(description="When the timeline was generated")


class BriefingSection(BaseModel):
    """A section in a briefing document."""

    title: str = Field(description="Section title")
    content: str = Field(description="Section content")


class BriefingResponse(BaseModel):
    """Response for briefing generation."""

    channel_id: str = Field(description="Channel ID")
    title: str = Field(description="Briefing title")
    executive_summary: str = Field(description="Executive summary")
    sections: list[BriefingSection] = Field(description="Briefing sections")
    key_points: list[str] = Field(description="Key takeaways")
    generated_at: datetime = Field(description="When the briefing was generated")


class GenerateTimelineRequest(BaseModel):
    """Request to generate a timeline."""

    max_events: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of events to extract",
    )


class GenerateBriefingRequest(BaseModel):
    """Request to generate a briefing."""

    style: str = Field(
        default="executive",
        description="Briefing style: 'executive' (concise) or 'detailed' (comprehensive)",
    )
    max_sections: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of sections",
    )
