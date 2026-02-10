# -*- coding: utf-8 -*-
"""Ops module DI container."""

from src.shared.kernel.contracts.ports import (
    ApiMetricsPort,
    SchedulerPort,
)


# ============================================================
# Singleton Instances
# ============================================================

_api_metrics_port: ApiMetricsPort | None = None
_scheduler_port: SchedulerPort | None = None


def create_api_metrics_port() -> ApiMetricsPort:
    global _api_metrics_port
    if _api_metrics_port is None:
        from src.infrastructure.monitoring.api_metrics import get_api_metrics
        from src.infrastructure.monitoring.adapters import ApiMetricsAdapter
        _api_metrics_port = ApiMetricsAdapter(get_api_metrics())
    return _api_metrics_port


def create_scheduler_port() -> SchedulerPort:
    global _scheduler_port
    if _scheduler_port is None:
        from src.infrastructure.scheduler.scheduler import get_scheduler
        from src.infrastructure.scheduler.adapters import SchedulerAdapter
        _scheduler_port = SchedulerAdapter(get_scheduler())
    return _scheduler_port


# ============================================================
# Service Factories
# ============================================================

def create_admin_stats_service(db):
    from src.modules.ops.application.services.admin_stats import AdminStatsService
    from src.modules.workspace.public import create_channel_repository_port
    return AdminStatsService(
        channel_repo=create_channel_repository_port(db),
        api_metrics=create_api_metrics_port(),
        scheduler=create_scheduler_port(),
    )


# ============================================================
# Scheduler Lifecycle
# ============================================================

def setup_scheduler() -> None:
    """Configure and start the background scheduler.

    Registers all periodic ops jobs (channel scan, stats update,
    trash cleanup) and starts the scheduler.
    """
    import logging
    from src.infrastructure.scheduler.scheduler import get_scheduler
    from src.modules.ops.infrastructure.scheduler.scheduler_jobs import (
        scan_inactive_channels,
        update_channel_statistics,
        cleanup_expired_trash,
    )

    logger = logging.getLogger(__name__)
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


def shutdown_scheduler(wait: bool = False) -> None:
    """Shut down the background scheduler."""
    from src.infrastructure.scheduler.scheduler import get_scheduler
    scheduler = get_scheduler()
    scheduler.shutdown(wait=wait)
