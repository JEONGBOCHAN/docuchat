# -*- coding: utf-8 -*-
"""Scheduler monitoring API endpoints."""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from src.services.scheduler import get_scheduler
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


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
def get_scheduler_status(request: Request) -> SchedulerStatus:
    """Get the current status of the background scheduler.

    Returns job list and running state.
    """
    scheduler = get_scheduler()
    jobs = scheduler.get_jobs()

    return SchedulerStatus(
        running=scheduler.is_running(),
        job_count=len(jobs),
        jobs=[
            JobInfo(
                id=j["id"],
                name=j["name"],
                next_run=j["next_run"],
                trigger=j["trigger"],
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
def get_job_history(request: Request, limit: int = 20) -> SchedulerHistoryResponse:
    """Get recent job execution history.

    Args:
        limit: Maximum number of entries to return (default 20)
    """
    scheduler = get_scheduler()
    history = scheduler.get_job_history(limit)

    return SchedulerHistoryResponse(
        entries=[
            JobHistoryEntry(
                job_id=h["job_id"],
                run_time=h["run_time"],
                status=h["status"],
                error=h["error"],
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
def run_job_manually(request: Request, job_id: str) -> dict:
    """Manually trigger a scheduled job to run immediately.

    Args:
        job_id: The ID of the job to run
    """
    scheduler = get_scheduler()

    try:
        scheduler.run_job_now(job_id)
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
