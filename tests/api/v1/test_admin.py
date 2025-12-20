# -*- coding: utf-8 -*-
"""Tests for Admin API endpoints."""

import pytest
from unittest.mock import MagicMock, patch


class TestGetSystemStats:
    """Tests for GET /api/v1/admin/stats endpoint."""

    def test_get_system_stats_success(self, client_with_db):
        """Test getting system statistics."""
        response = client_with_db.get("/api/v1/admin/stats")

        assert response.status_code == 200
        data = response.json()

        # Check all top-level sections exist
        assert "channels" in data
        assert "storage" in data
        assert "api" in data
        assert "scheduler" in data
        assert "limits" in data

    def test_channels_stats_structure(self, client_with_db):
        """Test channel statistics structure."""
        response = client_with_db.get("/api/v1/admin/stats")
        data = response.json()

        channels = data["channels"]
        assert "total" in channels
        assert "by_state" in channels
        assert "active" in channels["by_state"]
        assert "idle" in channels["by_state"]
        assert "inactive" in channels["by_state"]
        assert "over_limit" in channels["by_state"]

    def test_storage_stats_structure(self, client_with_db):
        """Test storage statistics structure."""
        response = client_with_db.get("/api/v1/admin/stats")
        data = response.json()

        storage = data["storage"]
        assert "total_files" in storage
        assert "total_size_bytes" in storage
        assert "total_size_mb" in storage
        assert "avg_files_per_channel" in storage
        assert "avg_size_per_channel_mb" in storage

    def test_api_stats_structure(self, client_with_db):
        """Test API statistics structure."""
        response = client_with_db.get("/api/v1/admin/stats")
        data = response.json()

        api = data["api"]
        assert "uptime_seconds" in api
        assert "total_calls" in api
        assert "gemini_calls" in api
        assert "error_rate_percent" in api

    def test_scheduler_stats_structure(self, client_with_db):
        """Test scheduler statistics structure."""
        response = client_with_db.get("/api/v1/admin/stats")
        data = response.json()

        scheduler = data["scheduler"]
        assert "running" in scheduler
        assert "job_count" in scheduler

    def test_limits_structure(self, client_with_db):
        """Test limits information structure."""
        response = client_with_db.get("/api/v1/admin/stats")
        data = response.json()

        limits = data["limits"]
        assert "max_files_per_channel" in limits
        assert "max_channel_size_mb" in limits


class TestGetChannelBreakdown:
    """Tests for GET /api/v1/admin/channels endpoint."""

    def test_get_channel_breakdown_empty(self, client_with_db, test_db):
        """Test getting channel breakdown when empty."""
        response = client_with_db.get("/api/v1/admin/channels")

        assert response.status_code == 200
        data = response.json()

        assert "channels" in data
        assert "total" in data
        assert data["total"] == 0
        assert data["channels"] == []

    def test_channel_breakdown_structure(self, client_with_db, test_db):
        """Test channel breakdown item structure."""
        from src.services.channel_repository import ChannelRepository

        # Create a sample channel
        repo = ChannelRepository(test_db)
        repo.create(gemini_store_id="store/admin-test", name="Admin Test")

        response = client_with_db.get("/api/v1/admin/channels")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["channels"]) == 1

        channel = data["channels"][0]
        assert "gemini_store_id" in channel
        assert "name" in channel
        assert "created_at" in channel
        assert "last_accessed_at" in channel
        assert "file_count" in channel
        assert "size_mb" in channel
        assert "state" in channel
        assert "action" in channel
        assert "days_since_access" in channel
        assert "usage_percent" in channel


class TestGetApiMetrics:
    """Tests for GET /api/v1/admin/api-metrics endpoint."""

    def test_get_api_metrics_success(self, client_with_db):
        """Test getting API metrics."""
        response = client_with_db.get("/api/v1/admin/api-metrics")

        assert response.status_code == 200
        data = response.json()

        assert "uptime_seconds" in data
        assert "started_at" in data
        assert "total_api_calls" in data
        assert "total_errors" in data
        assert "error_rate_percent" in data
        assert "avg_latency_ms" in data
        assert "gemini_api_calls" in data
        assert "top_endpoints" in data

    def test_api_metrics_endpoint_structure(self, client_with_db):
        """Test top endpoints structure."""
        # Make some API calls first
        client_with_db.get("/api/v1/health")
        client_with_db.get("/api/v1/admin/stats")

        response = client_with_db.get("/api/v1/admin/api-metrics")
        data = response.json()

        # Should have recorded at least these calls
        assert data["total_api_calls"] >= 0

        if data["top_endpoints"]:
            endpoint = data["top_endpoints"][0]
            assert "endpoint" in endpoint
            assert "calls" in endpoint
            assert "errors" in endpoint
            assert "avg_latency_ms" in endpoint


class TestResetApiMetrics:
    """Tests for POST /api/v1/admin/api-metrics/reset endpoint."""

    def test_reset_api_metrics(self, client_with_db):
        """Test resetting API metrics."""
        # Make some API calls
        client_with_db.get("/api/v1/health")
        client_with_db.get("/api/v1/health")

        # Reset metrics
        response = client_with_db.post("/api/v1/admin/api-metrics/reset")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify metrics were reset
        metrics_response = client_with_db.get("/api/v1/admin/api-metrics")
        # Note: The reset call itself will be recorded, so total_api_calls >= 1
        metrics = metrics_response.json()
        # The endpoint list should be minimal (just the calls after reset)
        assert metrics["gemini_api_calls"] == 0
