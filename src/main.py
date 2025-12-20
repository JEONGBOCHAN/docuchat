# -*- coding: utf-8 -*-
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.database import init_db
from src.middleware.metrics import MetricsMiddleware
from src.services.scheduler import get_scheduler
from src.services.scheduler_jobs import (
    scan_inactive_channels,
    update_channel_statistics,
)

settings = get_settings()
logger = logging.getLogger(__name__)


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

    scheduler.start()
    logger.info("Background scheduler configured and started")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Initialize database tables
    init_db()

    # Startup: Start background scheduler
    setup_scheduler()

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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
