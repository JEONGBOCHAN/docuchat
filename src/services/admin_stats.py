# -*- coding: utf-8 -*-
"""Admin statistics service.

This module provides aggregated system statistics for monitoring.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, UTC

from sqlalchemy.orm import Session

from src.infrastructure.persistence.channel_repository import ChannelRepository
from src.application.services.lifecycle_policy import LifecyclePolicy, ChannelState
from src.infrastructure.monitoring.api_metrics import get_api_metrics
from src.infrastructure.scheduler.scheduler import get_scheduler
from src.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SystemStats:
    """System-wide statistics."""

    # Channel stats
    total_channels: int
    active_channels: int
    idle_channels: int
    inactive_channels: int
    over_limit_channels: int

    # File stats
    total_files: int
    total_size_bytes: int
    total_size_mb: float
    avg_files_per_channel: float
    avg_size_per_channel_mb: float

    # API stats
    uptime_seconds: int
    total_api_calls: int
    gemini_api_calls: int
    api_error_rate: float

    # Scheduler stats
    scheduler_running: bool
    scheduled_jobs: int

    # Capacity stats
    max_files_per_channel: int
    max_channel_size_mb: int

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "channels": {
                "total": self.total_channels,
                "by_state": {
                    "active": self.active_channels,
                    "idle": self.idle_channels,
                    "inactive": self.inactive_channels,
                    "over_limit": self.over_limit_channels,
                },
            },
            "storage": {
                "total_files": self.total_files,
                "total_size_bytes": self.total_size_bytes,
                "total_size_mb": round(self.total_size_mb, 2),
                "avg_files_per_channel": round(self.avg_files_per_channel, 2),
                "avg_size_per_channel_mb": round(self.avg_size_per_channel_mb, 2),
            },
            "api": {
                "uptime_seconds": self.uptime_seconds,
                "total_calls": self.total_api_calls,
                "gemini_calls": self.gemini_api_calls,
                "error_rate_percent": round(self.api_error_rate, 2),
            },
            "scheduler": {
                "running": self.scheduler_running,
                "job_count": self.scheduled_jobs,
            },
            "limits": {
                "max_files_per_channel": self.max_files_per_channel,
                "max_channel_size_mb": self.max_channel_size_mb,
            },
        }


class AdminStatsService:
    """Service for gathering admin statistics.

    Aggregates data from various services to provide a complete
    system overview for monitoring and dashboards.

    Example:
        ```python
        stats_service = AdminStatsService(db)
        stats = stats_service.get_system_stats()
        print(f"Total channels: {stats.total_channels}")
        ```
    """

    def __init__(self, db: Session):
        """Initialize the admin stats service.

        Args:
            db: Database session
        """
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.lifecycle_policy = LifecyclePolicy()
        self.settings = get_settings()

    def get_system_stats(self) -> SystemStats:
        """Get comprehensive system statistics.

        Returns:
            SystemStats with all aggregated metrics
        """
        # Get all channels
        channels = self.channel_repo.get_all()

        # Calculate channel state distribution
        state_counts = {
            ChannelState.ACTIVE: 0,
            ChannelState.IDLE: 0,
            ChannelState.INACTIVE: 0,
            ChannelState.OVER_LIMIT: 0,
        }

        total_files = 0
        total_size = 0

        for channel in channels:
            status = self.lifecycle_policy.get_status(channel)
            state_counts[status.state] += 1
            total_files += channel.file_count
            total_size += channel.total_size_bytes

        total_channels = len(channels)
        total_size_mb = total_size / (1024 * 1024)

        # Calculate averages
        avg_files = total_files / total_channels if total_channels > 0 else 0
        avg_size_mb = total_size_mb / total_channels if total_channels > 0 else 0

        # Get API metrics
        api_metrics = get_api_metrics()
        api_stats = api_metrics.get_stats()

        # Get scheduler info
        scheduler = get_scheduler()
        scheduler_jobs = scheduler.get_jobs()

        return SystemStats(
            # Channel stats
            total_channels=total_channels,
            active_channels=state_counts[ChannelState.ACTIVE],
            idle_channels=state_counts[ChannelState.IDLE],
            inactive_channels=state_counts[ChannelState.INACTIVE],
            over_limit_channels=state_counts[ChannelState.OVER_LIMIT],
            # File stats
            total_files=total_files,
            total_size_bytes=total_size,
            total_size_mb=total_size_mb,
            avg_files_per_channel=avg_files,
            avg_size_per_channel_mb=avg_size_mb,
            # API stats
            uptime_seconds=api_stats["uptime_seconds"],
            total_api_calls=api_stats["total_api_calls"],
            gemini_api_calls=api_stats["gemini_api_calls"],
            api_error_rate=api_stats["error_rate_percent"],
            # Scheduler stats
            scheduler_running=scheduler.is_running(),
            scheduled_jobs=len(scheduler_jobs),
            # Capacity limits
            max_files_per_channel=self.settings.max_files_per_channel,
            max_channel_size_mb=self.settings.max_channel_size_mb,
        )

    def get_channel_breakdown(self) -> list[dict]:
        """Get detailed breakdown of all channels.

        Returns:
            List of channel details with lifecycle status
        """
        channels = self.channel_repo.get_all()
        breakdown = []

        for channel in channels:
            status = self.lifecycle_policy.get_status(channel)
            breakdown.append({
                "gemini_store_id": channel.gemini_store_id,
                "name": channel.name,
                "created_at": channel.created_at.isoformat(),
                "last_accessed_at": channel.last_accessed_at.isoformat(),
                "file_count": channel.file_count,
                "size_mb": round(channel.total_size_bytes / (1024 * 1024), 2),
                "state": status.state.value,
                "action": status.action.value,
                "days_since_access": status.days_since_access,
                "usage_percent": status.usage_percent,
            })

        return sorted(breakdown, key=lambda x: x["last_accessed_at"], reverse=True)
