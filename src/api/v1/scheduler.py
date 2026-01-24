# -*- coding: utf-8 -*-
"""Scheduler monitoring API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.application.ports.infrastructure import SchedulerPort
from src.infrastructure.di.container import create_scheduler_port
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def get_scheduler_port() -> SchedulerPort:
    """Get scheduler port instance."""
    return create_scheduler_port()


class JobInfo(BaseModel):
    """Information about a scheduled job."""

    id: str
    name: str | None
    next_run: str | None
    trigger: str


class JobHistoryEntry(BaseModel):
    """Record of a job execution."""

    job_id: str
    run_time: str
    status: str
    error: str | None


class SchedulerStatus(BaseModel):
    """Overall scheduler status."""

    running: bool
    job_count: int
    jobs: list[JobInfo]


class SchedulerHistoryResponse(BaseModel):
    """Response for job history endpoint."""

    entries: list[JobHistoryEntry]
    total: int


@router.get(
    "/status",
    response_model=SchedulerStatus,
    summary="Get scheduler status",
)
@limiter.limit(RateLimits.DEFAULT)
def get_scheduler_status(
    request: Request,
    scheduler_port: Annotated[SchedulerPort, Depends(get_scheduler_port)],
) -> SchedulerStatus:
    """Get the current status of the background scheduler.

    Returns job list and running state.
    """
    jobs = scheduler_port.get_jobs()

    return SchedulerStatus(
        running=scheduler_port.is_running(),
        job_count=len(jobs),
        jobs=[
            JobInfo(
                id=j.id,
                name=j.name,
                next_run=j.next_run,
                trigger=j.trigger,
            )
            for j in jobs
        ],
    )


@router.get(
    "/history",
    response_model=SchedulerHistoryResponse,
    summary="Get job execution history",
)
@limiter.limit(RateLimits.DEFAULT)
def get_job_history(
    request: Request,
    scheduler_port: Annotated[SchedulerPort, Depends(get_scheduler_port)],
    limit: int = 20,
) -> SchedulerHistoryResponse:
    """Get recent job execution history.

    Args:
        limit: Maximum number of entries to return (default 20)
    """
    history = scheduler_port.get_job_history(limit)

    return SchedulerHistoryResponse(
        entries=[
            JobHistoryEntry(
                job_id=h.job_id,
                run_time=h.run_time,
                status=h.status,
                error=h.error,
            )
            for h in history
        ],
        total=len(history),
    )


@router.post(
    "/jobs/{job_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger a job",
)
@limiter.limit(RateLimits.DEFAULT)
def run_job_manually(
    request: Request,
    job_id: str,
    scheduler_port: Annotated[SchedulerPort, Depends(get_scheduler_port)],
) -> dict:
    """Manually trigger a scheduled job to run immediately.

    Args:
        job_id: The ID of the job to run
    """
    try:
        scheduler_port.run_job_now(job_id)
        return {"message": f"Job {job_id} triggered successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run job: {str(e)}",
        )
