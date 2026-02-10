# -*- coding: utf-8 -*-
"""Scheduler infrastructure layer.

This module provides background job scheduling functionality.

Job functions are accessed via:
    src.modules.ops.infrastructure.scheduler.scheduler_jobs
or via the ops module's public API / DI container.
"""

from src.infrastructure.scheduler.scheduler import (
    SchedulerService,
    get_scheduler,
)

__all__ = ["SchedulerService", "get_scheduler"]
