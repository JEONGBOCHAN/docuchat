# -*- coding: utf-8 -*-
"""Infrastructure ports.

These ports define abstract interfaces for infrastructure services
like API metrics, scheduler, and other cross-cutting concerns.
They allow the application layer to interact with infrastructure
without direct coupling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


# =============================================================================
# Data Transfer Objects (DTOs)
# =============================================================================

@dataclass
class EndpointMetricsDTO:
    """DTO for endpoint metrics."""

    endpoint: str
    total_calls: int
    success_count: int
    error_count: int
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    methods: dict[str, int]


@dataclass
class ApiStatsDTO:
    """DTO for aggregated API statistics."""

    uptime_seconds: int
    started_at: str
    total_api_calls: int
    total_errors: int
    error_rate_percent: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    gemini_api_calls: int
    top_endpoints: list[dict]


@dataclass
class ScheduledJobDTO:
    """DTO for scheduled job information."""

    id: str
    name: str
    next_run: str | None
    trigger: str


@dataclass
class JobHistoryDTO:
    """DTO for job execution history."""

    job_id: str
    run_time: str
    status: str
    error: str | None


# =============================================================================
# Port Interfaces
# =============================================================================

class ApiMetricsPort(ABC):
    """Port for API metrics tracking.

    Provides an abstraction for tracking API call counts, latencies,
    and other metrics without exposing implementation details.
    """

    @abstractmethod
    def record_call(
        self,
        endpoint: str,
        success: bool = True,
        latency_ms: float = 0.0,
        method: str = "GET",
    ) -> None:
        """Record an API call.

        Args:
            endpoint: The endpoint path (e.g., "/api/v1/channels")
            success: Whether the call was successful
            latency_ms: Latency in milliseconds
            method: HTTP method (GET, POST, etc.)
        """
        ...

    @abstractmethod
    def record_gemini_call(self) -> None:
        """Record a Gemini API call."""
        ...

    @abstractmethod
    def get_endpoint_metrics(self, endpoint: str) -> EndpointMetricsDTO:
        """Get metrics for a specific endpoint.

        Args:
            endpoint: The endpoint path

        Returns:
            EndpointMetricsDTO for the specified endpoint
        """
        ...

    @abstractmethod
    def get_stats(self) -> ApiStatsDTO:
        """Get aggregated API statistics.

        Returns:
            ApiStatsDTO with overall statistics
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset all metrics."""
        ...


class SchedulerPort(ABC):
    """Port for background task scheduling.

    Provides an abstraction for scheduling and managing periodic jobs
    without exposing the underlying scheduler implementation.
    """

    @abstractmethod
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        **kwargs,
    ) -> None:
        """Add a job that runs at fixed intervals.

        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            hours: Interval in hours
            minutes: Interval in minutes
            seconds: Interval in seconds
            **kwargs: Additional arguments passed to the function
        """
        ...

    @abstractmethod
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: int = 0,
        minute: int = 0,
        day_of_week: str = "*",
        **kwargs,
    ) -> None:
        """Add a job that runs on a cron schedule.

        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
            day_of_week: Days to run ("mon-fri", "*", etc.)
            **kwargs: Additional arguments passed to the function
        """
        ...

    @abstractmethod
    def remove_job(self, job_id: str) -> None:
        """Remove a scheduled job.

        Args:
            job_id: The job to remove
        """
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the scheduler."""
        ...

    @abstractmethod
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        ...

    @abstractmethod
    def get_jobs(self) -> list[ScheduledJobDTO]:
        """Get all scheduled jobs.

        Returns:
            List of scheduled job information
        """
        ...

    @abstractmethod
    def get_job_history(self, limit: int = 20) -> list[JobHistoryDTO]:
        """Get recent job execution history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of job execution records
        """
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the scheduler is running.

        Returns:
            True if running
        """
        ...

    @abstractmethod
    def run_job_now(self, job_id: str) -> None:
        """Manually trigger a job to run immediately.

        Args:
            job_id: The job to run

        Raises:
            ValueError: If job not found
        """
        ...


class AudioJobDispatcherPort(ABC):
    """Port for dispatching audio generation jobs to a background executor.

    Abstracts the threading/executor mechanism so that presentation
    code does not depend on runtime infrastructure directly.
    """

    @abstractmethod
    def submit(self, fn: Callable, *args) -> None:
        """Submit a job for background execution.

        Args:
            fn: The callable to execute.
            *args: Positional arguments passed to *fn*.
        """
        ...

    @abstractmethod
    def shutdown(self, wait: bool = False) -> None:
        """Shut down the background executor.

        Args:
            wait: Whether to wait for running jobs to complete.
        """
        ...


class AudioGenerationTaskPort(ABC):
    """Port for enqueuing audio generation tasks.

    Encapsulates the background execution details (session management,
    event loop, use case wiring) so the application layer only needs
    to submit a request.
    """

    @abstractmethod
    def enqueue(self, request) -> None:
        """Enqueue an audio generation request for background processing.

        Args:
            request: AudioGenerationRequest to process.
        """
        ...
