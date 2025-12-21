# -*- coding: utf-8 -*-
"""Performance monitoring utilities.

This module provides tools for measuring and logging function execution times,
including decorators and context managers for performance tracking.
"""

import functools
import inspect
import time
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Callable, TypeVar

from src.core.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def timed(
    name: str | None = None,
    log_args: bool = False,
    threshold_ms: float | None = None,
):
    """Decorator to measure and log function execution time.

    Args:
        name: Custom name for the operation (defaults to function name)
        log_args: Whether to include function arguments in the log
        threshold_ms: Only log if execution time exceeds this threshold

    Example:
        @timed("database_query")
        def fetch_users():
            ...

        @timed(threshold_ms=100)
        async def slow_operation():
            ...
    """

    def decorator(func: F) -> F:
        operation_name = name or func.__name__
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                result = await func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                # Skip logging if below threshold
                if threshold_ms is None or elapsed_ms >= threshold_ms:
                    log_data = {
                        "operation": operation_name,
                        "duration_ms": round(elapsed_ms, 2),
                    }

                    if log_args:
                        log_data["args"] = str(args)[:200]
                        log_data["kwargs"] = str(kwargs)[:200]

                    logger.debug("Performance measurement", **log_data)

                return result

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                # Skip logging if below threshold
                if threshold_ms is None or elapsed_ms >= threshold_ms:
                    log_data = {
                        "operation": operation_name,
                        "duration_ms": round(elapsed_ms, 2),
                    }

                    if log_args:
                        log_data["args"] = str(args)[:200]
                        log_data["kwargs"] = str(kwargs)[:200]

                    logger.debug("Performance measurement", **log_data)

                return result

            return sync_wrapper  # type: ignore

    return decorator


@contextmanager
def measure_time(operation: str, **extra_context):
    """Context manager for measuring execution time of a code block.

    Args:
        operation: Name of the operation being measured
        **extra_context: Additional context to include in the log

    Example:
        with measure_time("data_processing", record_count=1000):
            process_data(records)
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "Performance measurement",
            operation=operation,
            duration_ms=round(elapsed_ms, 2),
            **extra_context,
        )


@asynccontextmanager
async def measure_time_async(operation: str, **extra_context):
    """Async context manager for measuring execution time.

    Args:
        operation: Name of the operation being measured
        **extra_context: Additional context to include in the log

    Example:
        async with measure_time_async("api_call", endpoint="/users"):
            response = await client.get("/users")
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "Performance measurement",
            operation=operation,
            duration_ms=round(elapsed_ms, 2),
            **extra_context,
        )


class PerformanceTracker:
    """Track performance metrics for a series of operations.

    Useful for batch operations where you want aggregate statistics.

    Example:
        tracker = PerformanceTracker("batch_processing")

        for item in items:
            with tracker.track():
                process(item)

        tracker.log_summary()
    """

    def __init__(self, name: str):
        """Initialize the tracker.

        Args:
            name: Name of the operation being tracked
        """
        self.name = name
        self.measurements: list[float] = []
        self._start_time: float | None = None

    @contextmanager
    def track(self):
        """Context manager to track a single operation."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.measurements.append(elapsed_ms)

    @asynccontextmanager
    async def track_async(self):
        """Async context manager to track a single operation."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.measurements.append(elapsed_ms)

    @property
    def count(self) -> int:
        """Number of measurements recorded."""
        return len(self.measurements)

    @property
    def total_ms(self) -> float:
        """Total time in milliseconds."""
        return sum(self.measurements)

    @property
    def avg_ms(self) -> float:
        """Average time in milliseconds."""
        if not self.measurements:
            return 0.0
        return self.total_ms / self.count

    @property
    def min_ms(self) -> float:
        """Minimum time in milliseconds."""
        if not self.measurements:
            return 0.0
        return min(self.measurements)

    @property
    def max_ms(self) -> float:
        """Maximum time in milliseconds."""
        if not self.measurements:
            return 0.0
        return max(self.measurements)

    def get_percentile(self, percentile: float) -> float:
        """Get a percentile value.

        Args:
            percentile: The percentile to calculate (0-100)

        Returns:
            The time at the given percentile
        """
        if not self.measurements:
            return 0.0

        sorted_measurements = sorted(self.measurements)
        index = int(len(sorted_measurements) * percentile / 100)
        index = min(index, len(sorted_measurements) - 1)
        return sorted_measurements[index]

    def log_summary(self):
        """Log a summary of all tracked measurements."""
        if not self.measurements:
            logger.info("Performance summary", operation=self.name, count=0)
            return

        logger.info(
            "Performance summary",
            operation=self.name,
            count=self.count,
            total_ms=round(self.total_ms, 2),
            avg_ms=round(self.avg_ms, 2),
            min_ms=round(self.min_ms, 2),
            max_ms=round(self.max_ms, 2),
            p50_ms=round(self.get_percentile(50), 2),
            p95_ms=round(self.get_percentile(95), 2),
            p99_ms=round(self.get_percentile(99), 2),
        )

    def reset(self):
        """Reset all measurements."""
        self.measurements.clear()
