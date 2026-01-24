# -*- coding: utf-8 -*-
"""Monitoring adapters.

Adapter implementations for monitoring-related ports.
"""

from src.application.ports.infrastructure import (
    ApiMetricsPort,
    ApiStatsDTO,
    EndpointMetricsDTO,
)
from src.infrastructure.monitoring.api_metrics import ApiMetricsService


class ApiMetricsAdapter(ApiMetricsPort):
    """Adapter that implements ApiMetricsPort using ApiMetricsService.

    This adapter wraps the existing ApiMetricsService to expose it
    through the ApiMetricsPort interface, following the ports and adapters pattern.
    """

    def __init__(self, metrics_service: ApiMetricsService):
        """Initialize the adapter.

        Args:
            metrics_service: The underlying metrics service instance
        """
        self._service = metrics_service

    def record_call(
        self,
        endpoint: str,
        success: bool = True,
        latency_ms: float = 0.0,
        method: str = "GET",
    ) -> None:
        """Record an API call."""
        self._service.record_call(endpoint, success, latency_ms, method)

    def record_gemini_call(self) -> None:
        """Record a Gemini API call."""
        self._service.record_gemini_call()

    def get_endpoint_metrics(self, endpoint: str) -> EndpointMetricsDTO:
        """Get metrics for a specific endpoint."""
        metrics = self._service.get_endpoint_metrics(endpoint)
        return EndpointMetricsDTO(
            endpoint=endpoint,
            total_calls=metrics.total_calls,
            success_count=metrics.success_count,
            error_count=metrics.error_count,
            avg_latency_ms=metrics.avg_latency_ms,
            min_latency_ms=metrics.min_latency_ms if metrics.min_latency_ms != float("inf") else 0.0,
            max_latency_ms=metrics.max_latency_ms,
            p50_latency_ms=metrics.p50_latency_ms,
            p95_latency_ms=metrics.p95_latency_ms,
            p99_latency_ms=metrics.p99_latency_ms,
            methods=dict(metrics.method_counts),
        )

    def get_stats(self) -> ApiStatsDTO:
        """Get aggregated API statistics."""
        stats = self._service.get_stats()
        return ApiStatsDTO(
            uptime_seconds=stats["uptime_seconds"],
            started_at=stats["started_at"],
            total_api_calls=stats["total_api_calls"],
            total_errors=stats["total_errors"],
            error_rate_percent=stats["error_rate_percent"],
            avg_latency_ms=stats["avg_latency_ms"],
            p50_latency_ms=stats["p50_latency_ms"],
            p95_latency_ms=stats["p95_latency_ms"],
            p99_latency_ms=stats["p99_latency_ms"],
            gemini_api_calls=stats["gemini_api_calls"],
            top_endpoints=stats["top_endpoints"],
        )

    def reset(self) -> None:
        """Reset all metrics."""
        self._service.reset()
