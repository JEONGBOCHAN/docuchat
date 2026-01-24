# -*- coding: utf-8 -*-
"""Background scheduler for periodic tasks.

This module provides a centralized scheduler for running background jobs
like inactive channel cleanup, statistics updates, etc.
"""

import logging
from datetime import datetime, UTC
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing background scheduled tasks.

    Provides a centralized way to schedule and manage periodic jobs.

    Example:
        ```python
        scheduler = SchedulerService()
        scheduler.add_job(
            job_id="cleanup",
            func=cleanup_inactive_channels,
            trigger="interval",
            hours=24
        )
        scheduler.start()
        ```
    """

    def __init__(self):
        """Initialize the scheduler service."""
        self._scheduler = BackgroundScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,  # Combine missed runs into one
                "max_instances": 1,  # Only one instance of each job at a time
                "misfire_grace_time": 3600,  # 1 hour grace time for misfired jobs
            }
        )
        self._scheduler.add_listener(
            self._job_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        self._job_history: list[dict] = []

    def _job_listener(self, event: JobExecutionEvent):
        """Listen for job events and log them."""
        job_id = event.job_id
        run_time = datetime.now(UTC)

        if event.exception:
            logger.error(f"Job {job_id} failed: {event.exception}")
            status = "failed"
            error = str(event.exception)
        else:
            logger.info(f"Job {job_id} executed successfully")
            status = "success"
            error = None

        # Keep last 100 job executions
        self._job_history.append({
            "job_id": job_id,
            "run_time": run_time.isoformat(),
            "status": status,
            "error": error,
        })
        if len(self._job_history) > 100:
            self._job_history.pop(0)

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        **kwargs
    ):
        """Add a job that runs at fixed intervals.

        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            hours: Interval in hours
            minutes: Interval in minutes
            seconds: Interval in seconds
            **kwargs: Additional arguments passed to the function
        """
        trigger = IntervalTrigger(hours=hours, minutes=minutes, seconds=seconds)
        self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        logger.info(f"Added interval job: {job_id} (every {hours}h {minutes}m {seconds}s)")

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: int = 0,
        minute: int = 0,
        day_of_week: str = "*",
        **kwargs
    ):
        """Add a job that runs on a cron schedule.

        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
            day_of_week: Days to run ("mon-fri", "*", etc.)
            **kwargs: Additional arguments passed to the function
        """
        trigger = CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week)
        self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        logger.info(f"Added cron job: {job_id} (at {hour}:{minute:02d}, days: {day_of_week})")

    def remove_job(self, job_id: str):
        """Remove a scheduled job.

        Args:
            job_id: The job to remove
        """
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            logger.warning(f"Could not remove job {job_id}: {e}")

    def start(self):
        """Start the scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("Scheduler shutdown")

    def get_jobs(self) -> list[dict]:
        """Get all scheduled jobs.

        Returns:
            List of job information dictionaries
        """
        jobs = []
        for job in self._scheduler.get_jobs():
            # Use getattr for compatibility with different APScheduler versions
            next_run = getattr(job, "next_run_time", None)
            jobs.append({
                "id": job.id,
                "name": getattr(job, "name", job.id),
                "next_run": next_run.isoformat() if next_run else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def get_job_history(self, limit: int = 20) -> list[dict]:
        """Get recent job execution history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of job execution records
        """
        return self._job_history[-limit:]

    def is_running(self) -> bool:
        """Check if the scheduler is running.

        Returns:
            True if running
        """
        return self._scheduler.running

    def run_job_now(self, job_id: str):
        """Manually trigger a job to run immediately.

        Args:
            job_id: The job to run
        """
        job = self._scheduler.get_job(job_id)
        if job:
            job.func(**job.kwargs)
            logger.info(f"Manually triggered job: {job_id}")
        else:
            raise ValueError(f"Job not found: {job_id}")


# Singleton instance
_scheduler_instance: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """Get the global scheduler instance.

    Returns:
        The singleton SchedulerService
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    return _scheduler_instance
