# -*- coding: utf-8 -*-
"""API metrics tracking service.

This module provides a service for tracking API call counts and latencies.
"""

import heapq
from collections import defaultdict
from datetime import datetime, UTC
from dataclasses import dataclass, field
from threading import Lock

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EndpointMetrics:
    """Metrics for a single endpoint."""

    total_calls: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    latencies: list = field(default_factory=list)  # For percentile calculation

    # HTTP method breakdown
    method_counts: dict = field(default_factory=lambda: defaultdict(int))

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.error_count / self.total_calls) * 100

    def add_latency(self, latency_ms: float) -> None:
        """Add a latency measurement for percentile calculation.

        Keeps only the last 1000 measurements to bound memory usage.
        """
        self.latencies.append(latency_ms)
        if len(self.latencies) > 1000:
            self.latencies.pop(0)

        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    def get_percentile(self, percentile: float) -> float:
        """Get a percentile latency value.

        Args:
            percentile: The percentile to calculate (0-100)

        Returns:
            The latency at the given percentile
        """
        if not self.latencies:
            return 0.0

        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * percentile / 100)
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]

    @property
    def p50_latency_ms(self) -> float:
        """Get median (p50) latency."""
        return self.get_percentile(50)

    @property
    def p95_latency_ms(self) -> float:
        """Get p95 latency."""
        return self.get_percentile(95)

    @property
    def p99_latency_ms(self) -> float:
        """Get p99 latency."""
        return self.get_percentile(99)


class ApiMetricsService:
    """Service for tracking API metrics.

    Thread-safe metrics tracking for API calls including:
    - Call counts per endpoint
    - Success/error rates
    - Average latencies

    Example:
        ```python
        metrics = ApiMetricsService()

        start = time.time()
        # ... perform API call ...
        latency = (time.time() - start) * 1000

        metrics.record_call("/api/v1/channels", success=True, latency_ms=latency)

        stats = metrics.get_stats()
        ```
    """

    def __init__(self):
        """Initialize the metrics service."""
        self._lock = Lock()
        self._endpoints: dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)
        self._started_at = datetime.now(UTC)
        self._gemini_api_calls = 0

    def record_call(
        self,
        endpoint: str,
        success: bool = True,
        latency_ms: float = 0.0,
        method: str = "GET",
    ):
        """Record an API call.

        Args:
            endpoint: The endpoint path (e.g., "/api/v1/channels")
            success: Whether the call was successful
            latency_ms: Latency in milliseconds
            method: HTTP method (GET, POST, etc.)
        """
        with self._lock:
            metrics = self._endpoints[endpoint]
            metrics.total_calls += 1
            metrics.total_latency_ms += latency_ms
            metrics.add_latency(latency_ms)
            metrics.method_counts[method] += 1

            if success:
                metrics.success_count += 1
            else:
                metrics.error_count += 1

    def record_gemini_call(self):
        """Record a Gemini API call."""
        with self._lock:
            self._gemini_api_calls += 1

    def get_endpoint_metrics(self, endpoint: str) -> EndpointMetrics:
        """Get metrics for a specific endpoint.

        Args:
            endpoint: The endpoint path

        Returns:
            EndpointMetrics for the specified endpoint
        """
        with self._lock:
            return self._endpoints.get(endpoint, EndpointMetrics())

    def get_stats(self) -> dict:
        """Get aggregated statistics.

        Returns:
            Dictionary with overall API statistics
        """
        with self._lock:
            total_calls = sum(m.total_calls for m in self._endpoints.values())
            total_errors = sum(m.error_count for m in self._endpoints.values())
            total_latency = sum(m.total_latency_ms for m in self._endpoints.values())

            # Get top endpoints by call count
            sorted_endpoints = sorted(
                self._endpoints.items(),
                key=lambda x: x[1].total_calls,
                reverse=True,
            )

            top_endpoints = [
                {
                    "endpoint": endpoint,
                    "calls": metrics.total_calls,
                    "errors": metrics.error_count,
                    "avg_latency_ms": round(metrics.avg_latency_ms, 2),
                    "p50_latency_ms": round(metrics.p50_latency_ms, 2),
                    "p95_latency_ms": round(metrics.p95_latency_ms, 2),
                    "p99_latency_ms": round(metrics.p99_latency_ms, 2),
                    "min_latency_ms": round(metrics.min_latency_ms, 2) if metrics.min_latency_ms != float("inf") else 0,
                    "max_latency_ms": round(metrics.max_latency_ms, 2),
                    "methods": dict(metrics.method_counts),
                }
                for endpoint, metrics in sorted_endpoints[:10]
            ]

            # Calculate overall percentiles
            all_latencies = []
            for m in self._endpoints.values():
                all_latencies.extend(m.latencies)
            all_latencies.sort()

            def get_percentile(percentile: float) -> float:
                if not all_latencies:
                    return 0.0
                index = int(len(all_latencies) * percentile / 100)
                index = min(index, len(all_latencies) - 1)
                return all_latencies[index]

            return {
                "uptime_seconds": int((datetime.now(UTC) - self._started_at).total_seconds()),
                "started_at": self._started_at.isoformat(),
                "total_api_calls": total_calls,
                "total_errors": total_errors,
                "error_rate_percent": round((total_errors / total_calls * 100) if total_calls > 0 else 0, 2),
                "avg_latency_ms": round(total_latency / total_calls if total_calls > 0 else 0, 2),
                "p50_latency_ms": round(get_percentile(50), 2),
                "p95_latency_ms": round(get_percentile(95), 2),
                "p99_latency_ms": round(get_percentile(99), 2),
                "gemini_api_calls": self._gemini_api_calls,
                "top_endpoints": top_endpoints,
            }

    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._endpoints.clear()
            self._gemini_api_calls = 0
            self._started_at = datetime.now(UTC)


# Singleton instance
_metrics_instance: ApiMetricsService | None = None


def get_api_metrics() -> ApiMetricsService:
    """Get the global API metrics instance.

    Returns:
        The singleton ApiMetricsService
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = ApiMetricsService()
    return _metrics_instance
