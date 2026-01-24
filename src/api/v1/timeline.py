# -*- coding: utf-8 -*-
"""Timeline and Briefing API endpoints."""

from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.models.timeline import (
    TimelineEvent,
    TimelineResponse,
    BriefingSection,
    BriefingResponse,
    GenerateTimelineRequest,
    GenerateBriefingRequest,
)
from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import ChannelRepositoryPort
from src.core.database import get_db
from src.infrastructure.di.container import (
    create_channel_port,
    create_generate_timeline_use_case,
    create_generate_briefing_use_case,
    create_channel_repository_port,
)
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/channels", tags=["timeline"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


@router.post(
    "/{channel_id:path}/generate-timeline",
    response_model=TimelineResponse,
    summary="Generate timeline from documents",
)
@limiter.limit(RateLimits.CHAT)
def generate_timeline(
    request: Request,
    channel_id: str,
    body: GenerateTimelineRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
) -> TimelineResponse:
    """Generate a chronological timeline of events from documents.

    Analyzes all documents in the channel to extract date-based events
    and organizes them in chronological order.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Generate timeline using Clean Architecture use case
    use_case = create_generate_timeline_use_case()
    result = use_case.execute(
        channel_id=channel_id,
        max_events=body.max_events,
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate timeline: {result.error}",
        )

    # Convert to response model
    events = [
        TimelineEvent(
            date=event.date,
            title=event.title,
            description=event.description,
            source=event.source,
        )
        for event in result.events
    ]

    return TimelineResponse(
        channel_id=channel_id,
        events=events,
        total=len(events),
        generated_at=datetime.now(UTC),
    )


@router.post(
    "/{channel_id:path}/generate-briefing",
    response_model=BriefingResponse,
    summary="Generate briefing document",
)
@limiter.limit(RateLimits.CHAT)
def generate_briefing(
    request: Request,
    channel_id: str,
    body: GenerateBriefingRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
) -> BriefingResponse:
    """Generate a structured briefing document from channel content.

    Creates a professional briefing with executive summary, sections,
    and key takeaways based on all documents in the channel.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Validate style
    if body.style not in ("executive", "detailed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Style must be 'executive' or 'detailed'",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Generate briefing using Clean Architecture use case
    use_case = create_generate_briefing_use_case()
    result = use_case.execute(
        channel_id=channel_id,
        style=body.style,
        max_sections=body.max_sections,
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate briefing: {result.error}",
        )

    # Convert to response model
    sections = [
        BriefingSection(
            title=section.title,
            content=section.content,
        )
        for section in result.sections
    ]

    return BriefingResponse(
        channel_id=channel_id,
        title=result.title,
        executive_summary=result.executive_summary,
        sections=sections,
        key_points=result.key_points,
        generated_at=datetime.now(UTC),
    )
