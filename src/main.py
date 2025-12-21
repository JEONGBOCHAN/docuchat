# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.database import init_db
from src.core.logging import get_logger, setup_logging
from src.core.rate_limiter import limiter
from src.core.sentry import setup_sentry
from src.middleware.metrics import MetricsMiddleware
from src.middleware.request_logging import RequestLoggingMiddleware
from src.services.scheduler import get_scheduler
from src.services.scheduler_jobs import (
    scan_inactive_channels,
    update_channel_statistics,
    cleanup_expired_trash,
)

# Initialize structured logging first
setup_logging()

settings = get_settings()
logger = get_logger(__name__)


def setup_scheduler():
    """Configure and start the background scheduler."""
    scheduler = get_scheduler()

    # Scan for inactive channels daily at 2 AM UTC
    scheduler.add_cron_job(
        job_id="scan_inactive_channels",
        func=scan_inactive_channels,
        hour=2,
        minute=0,
    )

    # Update channel statistics every 6 hours
    scheduler.add_interval_job(
        job_id="update_channel_statistics",
        func=update_channel_statistics,
        hours=6,
    )

    # Clean up expired trash daily at 3 AM UTC
    scheduler.add_cron_job(
        job_id="cleanup_expired_trash",
        func=cleanup_expired_trash,
        hour=3,
        minute=0,
    )

    scheduler.start()
    logger.info("Background scheduler configured and started")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize Sentry error tracking
    setup_sentry()

    # Startup: Initialize database tables
    init_db()

    # Startup: Start background scheduler
    setup_scheduler()

    logger.info(
        "Application started",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env.value,
    )

    yield

    # Shutdown: Stop scheduler
    scheduler = get_scheduler()
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="NotebookLM Clone - Document-based RAG Chat Application",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting setup
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exceeded handler with proper headers."""
    # Parse rate limit info from exception
    limit_value = getattr(exc, "detail", "Rate limit exceeded")

    response = JSONResponse(
        status_code=429,
        content={
            "detail": "Too Many Requests",
            "message": limit_value,
        },
    )

    # Add rate limit headers
    if hasattr(request.state, "view_rate_limit"):
        rate_info = request.state.view_rate_limit
        # rate_info can be a string ("10 per 1 minute") or tuple
        if isinstance(rate_info, str):
            limit_parts = rate_info.split(" per ")
            if len(limit_parts) == 2:
                response.headers["X-RateLimit-Limit"] = limit_parts[0]
        elif isinstance(rate_info, tuple) and len(rate_info) > 0:
            # Handle tuple format from slowapi
            response.headers["X-RateLimit-Limit"] = str(rate_info[0])

    # Retry-After header (seconds until reset)
    response.headers["Retry-After"] = str(getattr(exc, "retry_after", 60))

    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware (should be outermost for accurate timing)
app.add_middleware(RequestLoggingMiddleware)

# Metrics tracking middleware
app.add_middleware(MetricsMiddleware)

# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }
