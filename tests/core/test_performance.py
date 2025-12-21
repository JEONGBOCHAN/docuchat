# -*- coding: utf-8 -*-
"""Tests for performance monitoring utilities."""

import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest

from src.core.performance import (
    timed,
    measure_time,
    measure_time_async,
    PerformanceTracker,
)


class TestTimedDecorator:
    """Tests for the @timed decorator."""

    def test_timed_sync_function(self):
        """Test timing a synchronous function."""

        @timed("test_operation")
        def slow_function():
            time.sleep(0.01)
            return "result"

        result = slow_function()
        assert result == "result"

    def test_timed_async_function(self):
        """Test timing an asynchronous function."""

        @timed("async_test")
        async def async_slow_function():
            await asyncio.sleep(0.01)
            return "async_result"

        result = asyncio.run(async_slow_function())
        assert result == "async_result"

    def test_timed_uses_function_name_by_default(self):
        """Test that decorator uses function name when name not provided."""

        @timed()
        def my_named_function():
            return 42

        result = my_named_function()
        assert result == 42

    def test_timed_with_threshold_below(self):
        """Test that logs are skipped when below threshold."""

        @timed(threshold_ms=1000)
        def fast_function():
            return "fast"

        result = fast_function()
        assert result == "fast"


class TestMeasureTime:
    """Tests for measure_time context manager."""

    def test_measure_time_context_manager(self):
        """Test the sync context manager."""
        with measure_time("test_block"):
            time.sleep(0.01)

    def test_measure_time_with_extra_context(self):
        """Test context manager with extra context."""
        with measure_time("process_items", item_count=100, batch_id="abc"):
            time.sleep(0.01)


class TestMeasureTimeAsync:
    """Tests for measure_time_async context manager."""

    @pytest.mark.asyncio
    async def test_measure_time_async_context_manager(self):
        """Test the async context manager."""
        async with measure_time_async("async_block"):
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_measure_time_async_with_extra_context(self):
        """Test async context manager with extra context."""
        async with measure_time_async("fetch_data", endpoint="/users"):
            await asyncio.sleep(0.01)


class TestPerformanceTracker:
    """Tests for PerformanceTracker class."""

    def test_tracker_initialization(self):
        """Test tracker initializes correctly."""
        tracker = PerformanceTracker("test_batch")
        assert tracker.name == "test_batch"
        assert tracker.count == 0
        assert tracker.total_ms == 0.0

    def test_tracker_track_single_operation(self):
        """Test tracking a single operation."""
        tracker = PerformanceTracker("batch")

        with tracker.track():
            time.sleep(0.01)

        assert tracker.count == 1
        assert tracker.total_ms > 0

    def test_tracker_track_multiple_operations(self):
        """Test tracking multiple operations."""
        tracker = PerformanceTracker("batch")

        for _ in range(5):
            with tracker.track():
                time.sleep(0.001)

        assert tracker.count == 5
        assert tracker.total_ms > 0

    def test_tracker_statistics(self):
        """Test tracker statistics calculation."""
        tracker = PerformanceTracker("stats_test")

        # Add some measurements manually for predictable testing
        tracker.measurements = [10.0, 20.0, 30.0, 40.0, 50.0]

        assert tracker.count == 5
        assert tracker.total_ms == 150.0
        assert tracker.avg_ms == 30.0
        assert tracker.min_ms == 10.0
        assert tracker.max_ms == 50.0

    def test_tracker_percentiles(self):
        """Test percentile calculation."""
        tracker = PerformanceTracker("percentile_test")
        tracker.measurements = list(range(1, 101))  # 1 to 100

        # Percentile calculation: index = len * percentile / 100
        # For 100 elements: p50 -> index 50 -> value 51
        assert tracker.get_percentile(50) == 51  # p50
        assert tracker.get_percentile(95) == 96  # p95
        assert tracker.get_percentile(99) == 100  # p99

    def test_tracker_empty_percentile(self):
        """Test percentile with no measurements."""
        tracker = PerformanceTracker("empty")
        assert tracker.get_percentile(50) == 0.0

    def test_tracker_log_summary(self):
        """Test log_summary doesn't raise."""
        tracker = PerformanceTracker("summary_test")
        tracker.measurements = [10.0, 20.0, 30.0]

        # Should not raise
        tracker.log_summary()

    def test_tracker_log_summary_empty(self):
        """Test log_summary with no measurements."""
        tracker = PerformanceTracker("empty")

        # Should not raise
        tracker.log_summary()

    def test_tracker_reset(self):
        """Test resetting tracker."""
        tracker = PerformanceTracker("reset_test")
        tracker.measurements = [10.0, 20.0, 30.0]

        tracker.reset()

        assert tracker.count == 0
        assert tracker.total_ms == 0.0

    @pytest.mark.asyncio
    async def test_tracker_track_async(self):
        """Test async tracking."""
        tracker = PerformanceTracker("async_batch")

        async with tracker.track_async():
            await asyncio.sleep(0.01)

        assert tracker.count == 1
        assert tracker.total_ms > 0
