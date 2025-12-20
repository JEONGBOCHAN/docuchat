# -*- coding: utf-8 -*-
"""Admin monitoring API endpoints.

Provides system-wide statistics and monitoring data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.admin_stats import AdminStatsService
from src.services.api_metrics import get_api_metrics

router = APIRouter(prefix="/admin", tags=["admin"])


class ChannelStats(BaseModel):
    """Channel statistics."""

    total: int
    by_state: dict[str, int]


class StorageStats(BaseModel):
    """Storage usage statistics."""

    total_files: int
    total_size_bytes: int
    total_size_mb: float
    avg_files_per_channel: float
    avg_size_per_channel_mb: float


class ApiStats(BaseModel):
    """API usage statistics."""

    uptime_seconds: int
    total_calls: int
    gemini_calls: int
    error_rate_percent: float


class SchedulerStats(BaseModel):
    """Scheduler statistics."""

    running: bool
    job_count: int


class LimitsInfo(BaseModel):
    """System limits information."""

    max_files_per_channel: int
    max_channel_size_mb: int


class SystemStatsResponse(BaseModel):
    """Complete system statistics response."""

    channels: ChannelStats
    storage: StorageStats
    api: ApiStats
    scheduler: SchedulerStats
    limits: LimitsInfo


class ChannelBreakdownItem(BaseModel):
    """Individual channel breakdown item."""

    gemini_store_id: str
    name: str
    created_at: str
    last_accessed_at: str
    file_count: int
    size_mb: float
    state: str
    action: str
    days_since_access: int
    usage_percent: float


class ChannelBreakdownResponse(BaseModel):
    """Response containing all channel breakdowns."""

    channels: list[ChannelBreakdownItem]
    total: int


class EndpointMetric(BaseModel):
    """Metrics for a single endpoint."""

    endpoint: str
    calls: int
    errors: int
    avg_latency_ms: float


class ApiMetricsResponse(BaseModel):
    """Detailed API metrics response."""

    uptime_seconds: int
    started_at: str
    total_api_calls: int
    total_errors: int
    error_rate_percent: float
    avg_latency_ms: float
    gemini_api_calls: int
    top_endpoints: list[EndpointMetric]


@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="Get system statistics",
)
@limiter.limit(RateLimits.DEFAULT)
def get_system_stats(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> SystemStatsResponse:
    """Get comprehensive system statistics for monitoring.

    Returns channel counts, storage usage, API metrics, and scheduler status.
    """
    stats_service = AdminStatsService(db)
    stats = stats_service.get_system_stats()
    stats_dict = stats.to_dict()

    return SystemStatsResponse(
        channels=ChannelStats(**stats_dict["channels"]),
        storage=StorageStats(**stats_dict["storage"]),
        api=ApiStats(**stats_dict["api"]),
        scheduler=SchedulerStats(**stats_dict["scheduler"]),
        limits=LimitsInfo(**stats_dict["limits"]),
    )


@router.get(
    "/channels",
    response_model=ChannelBreakdownResponse,
    summary="Get channel breakdown",
)
@limiter.limit(RateLimits.DEFAULT)
def get_channel_breakdown(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> ChannelBreakdownResponse:
    """Get detailed breakdown of all channels.

    Returns each channel's status, usage, and lifecycle state.
    """
    stats_service = AdminStatsService(db)
    breakdown = stats_service.get_channel_breakdown()

    return ChannelBreakdownResponse(
        channels=[ChannelBreakdownItem(**ch) for ch in breakdown],
        total=len(breakdown),
    )


@router.get(
    "/api-metrics",
    response_model=ApiMetricsResponse,
    summary="Get detailed API metrics",
)
@limiter.limit(RateLimits.DEFAULT)
def get_api_metrics_endpoint(request: Request) -> ApiMetricsResponse:
    """Get detailed API call metrics.

    Returns call counts, error rates, and latencies per endpoint.
    """
    metrics = get_api_metrics()
    stats = metrics.get_stats()

    return ApiMetricsResponse(
        uptime_seconds=stats["uptime_seconds"],
        started_at=stats["started_at"],
        total_api_calls=stats["total_api_calls"],
        total_errors=stats["total_errors"],
        error_rate_percent=stats["error_rate_percent"],
        avg_latency_ms=stats["avg_latency_ms"],
        gemini_api_calls=stats["gemini_api_calls"],
        top_endpoints=[EndpointMetric(**ep) for ep in stats["top_endpoints"]],
    )


@router.post(
    "/api-metrics/reset",
    summary="Reset API metrics",
)
@limiter.limit(RateLimits.DEFAULT)
def reset_api_metrics(request: Request) -> dict:
    """Reset all API metrics counters.

    Use this to start fresh metrics collection.
    """
    metrics = get_api_metrics()
    metrics.reset()
    return {"message": "API metrics have been reset"}
