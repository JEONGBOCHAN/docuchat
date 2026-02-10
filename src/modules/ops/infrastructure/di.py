# -*- coding: utf-8 -*-
"""Ops module DI container."""

from src.application.ports import (
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
    from src.application.services.admin_stats import AdminStatsService
    from src.modules.workspace.public import create_channel_repository_port
    return AdminStatsService(
        channel_repo=create_channel_repository_port(db),
        api_metrics=create_api_metrics_port(),
        scheduler=create_scheduler_port(),
    )
