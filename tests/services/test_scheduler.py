# -*- coding: utf-8 -*-
"""Tests for Scheduler service."""

import pytest
from unittest.mock import MagicMock, patch
import time

from src.infrastructure.scheduler.scheduler import SchedulerService, get_scheduler
from src.main import app
from src.shared.kernel.presentation.dependencies.admin_auth import require_admin_key


class TestSchedulerService:
    """Tests for SchedulerService."""

    def test_scheduler_init(self):
        """Test scheduler initialization."""
        scheduler = SchedulerService()
        assert scheduler is not None
        assert not scheduler.is_running()

    def test_add_interval_job(self):
        """Test adding an interval job."""
        scheduler = SchedulerService()

        mock_func = MagicMock()
        scheduler.add_interval_job(
            job_id="test_job",
            func=mock_func,
            seconds=60,
        )

        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0]["id"] == "test_job"

    def test_add_cron_job(self):
        """Test adding a cron job."""
        scheduler = SchedulerService()

        mock_func = MagicMock()
        scheduler.add_cron_job(
            job_id="test_cron",
            func=mock_func,
            hour=2,
            minute=30,
        )

        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0]["id"] == "test_cron"

    def test_remove_job(self):
        """Test removing a job."""
        scheduler = SchedulerService()

        mock_func = MagicMock()
        scheduler.add_interval_job(
            job_id="to_remove",
            func=mock_func,
            seconds=60,
        )

        assert len(scheduler.get_jobs()) == 1

        scheduler.remove_job("to_remove")
        assert len(scheduler.get_jobs()) == 0

    def test_start_and_shutdown(self):
        """Test starting and shutting down the scheduler."""
        scheduler = SchedulerService()

        assert not scheduler.is_running()

        scheduler.start()
        assert scheduler.is_running()

        scheduler.shutdown(wait=False)
        assert not scheduler.is_running()

    def test_get_job_history_empty(self):
        """Test getting empty job history."""
        scheduler = SchedulerService()
        history = scheduler.get_job_history()
        assert history == []

    def test_run_job_now(self):
        """Test manually running a job."""
        scheduler = SchedulerService()

        mock_func = MagicMock()
        scheduler.add_interval_job(
            job_id="manual_job",
            func=mock_func,
            hours=24,  # Won't run automatically
        )

        scheduler.run_job_now("manual_job")
        mock_func.assert_called_once()

    def test_run_job_now_not_found(self):
        """Test running a non-existent job raises error."""
        scheduler = SchedulerService()

        with pytest.raises(ValueError, match="Job not found"):
            scheduler.run_job_now("nonexistent")

    def test_get_scheduler_singleton(self):
        """Test that get_scheduler returns singleton."""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()
        assert scheduler1 is scheduler2


class TestSchedulerAPI:
    """Tests for Scheduler API endpoints."""

    @pytest.fixture(autouse=True)
    def bypass_admin_key(self):
        """Bypass admin key check in tests."""
        app.dependency_overrides[require_admin_key] = lambda: "test-key"
        yield
        app.dependency_overrides.pop(require_admin_key, None)

    def test_get_scheduler_status(self, client):
        """Test getting scheduler status."""
        response = client.get("/api/v1/scheduler/status")

        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "job_count" in data
        assert "jobs" in data

    def test_get_job_history(self, client):
        """Test getting job history."""
        response = client.get("/api/v1/scheduler/history")

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data

    def test_run_job_not_found(self, client):
        """Test running non-existent job."""
        response = client.post("/api/v1/scheduler/jobs/nonexistent/run")

        assert response.status_code == 404
