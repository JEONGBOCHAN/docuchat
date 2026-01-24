# -*- coding: utf-8 -*-
"""Scheduler infrastructure layer.

This module provides background job scheduling functionality.
"""

from src.infrastructure.scheduler.scheduler import (
    SchedulerService,
    get_scheduler,
)
from src.infrastructure.scheduler.scheduler_jobs import (
    scan_inactive_channels,
    cleanup_inactive_channels,
    update_channel_statistics,
    cleanup_expired_trash,
)

__all__ = [
    "SchedulerService",
    "get_scheduler",
    "scan_inactive_channels",
    "cleanup_inactive_channels",
    "update_channel_statistics",
    "cleanup_expired_trash",
]
