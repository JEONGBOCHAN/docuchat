# -*- coding: utf-8 -*-
"""Capacity API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.capacity import CapacityUsageResponse
from src.services.gemini import GeminiService, get_gemini_service
from src.services.capacity_service import CapacityService
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/capacity", tags=["capacity"])


@router.get(
    "",
    response_model=CapacityUsageResponse,
    summary="Get capacity usage for a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def get_capacity_usage(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID to check capacity")],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> CapacityUsageResponse:
    """Get the current capacity usage for a channel.

    Returns file count, size usage, and whether additional uploads are allowed.
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    capacity_service = CapacityService(db)
    usage = capacity_service.get_usage(channel_id)

    if not usage:
        # Channel exists in Gemini but not in local DB - return empty usage
        from src.core.config import get_settings
        settings = get_settings()
        return CapacityUsageResponse(
            channel_id=channel_id,
            file_count=0,
            max_files=settings.max_files_per_channel,
            file_usage_percent=0.0,
            size_bytes=0,
            size_mb=0.0,
            max_size_bytes=settings.max_channel_size_mb * 1024 * 1024,
            max_size_mb=float(settings.max_channel_size_mb),
            size_usage_percent=0.0,
            can_upload=True,
            remaining_files=settings.max_files_per_channel,
            remaining_mb=float(settings.max_channel_size_mb),
        )

    return CapacityUsageResponse(
        channel_id=channel_id,
        file_count=usage.file_count,
        max_files=usage.max_files,
        file_usage_percent=usage.file_usage_percent,
        size_bytes=usage.size_bytes,
        size_mb=round(usage.size_bytes / (1024 * 1024), 2),
        max_size_bytes=usage.max_size_bytes,
        max_size_mb=round(usage.max_size_bytes / (1024 * 1024), 0),
        size_usage_percent=usage.size_usage_percent,
        can_upload=usage.can_upload,
        remaining_files=usage.remaining_files,
        remaining_mb=round(usage.remaining_bytes / (1024 * 1024), 2),
    )
