# -*- coding: utf-8 -*-
"""Scheduler adapters.

Adapter implementations for scheduler-related ports.
"""

from typing import Callable

from src.shared.kernel.contracts.ports.infrastructure import (
    SchedulerPort,
    ScheduledJobDTO,
    JobHistoryDTO,
)
from src.infrastructure.scheduler.scheduler import SchedulerService


class SchedulerAdapter(SchedulerPort):
    """Adapter that implements SchedulerPort using SchedulerService.

    This adapter wraps the existing SchedulerService to expose it
    through the SchedulerPort interface, following the ports and adapters pattern.
    """

    def __init__(self, scheduler_service: SchedulerService):
        """Initialize the adapter.

        Args:
            scheduler_service: The underlying scheduler service instance
        """
        self._service = scheduler_service

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        **kwargs,
    ) -> None:
        """Add a job that runs at fixed intervals."""
        self._service.add_interval_job(job_id, func, hours, minutes, seconds, **kwargs)

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: int = 0,
        minute: int = 0,
        day_of_week: str = "*",
        **kwargs,
    ) -> None:
        """Add a job that runs on a cron schedule."""
        self._service.add_cron_job(job_id, func, hour, minute, day_of_week, **kwargs)

    def remove_job(self, job_id: str) -> None:
        """Remove a scheduled job."""
        self._service.remove_job(job_id)

    def start(self) -> None:
        """Start the scheduler."""
        self._service.start()

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler."""
        self._service.shutdown(wait)

    def get_jobs(self) -> list[ScheduledJobDTO]:
        """Get all scheduled jobs."""
        jobs = self._service.get_jobs()
        return [
            ScheduledJobDTO(
                id=job["id"],
                name=job["name"],
                next_run=job["next_run"],
                trigger=job["trigger"],
            )
            for job in jobs
        ]

    def get_job_history(self, limit: int = 20) -> list[JobHistoryDTO]:
        """Get recent job execution history."""
        history = self._service.get_job_history(limit)
        return [
            JobHistoryDTO(
                job_id=entry["job_id"],
                run_time=entry["run_time"],
                status=entry["status"],
                error=entry["error"],
            )
            for entry in history
        ]

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._service.is_running()

    def run_job_now(self, job_id: str) -> None:
        """Manually trigger a job to run immediately."""
        self._service.run_job_now(job_id)
