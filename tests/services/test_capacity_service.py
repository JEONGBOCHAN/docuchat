# -*- coding: utf-8 -*-
"""Tests for capacity service."""

import pytest

from src.services.capacity_service import (
    CapacityService,
    CapacityExceededError,
    CapacityUsage,
)
from src.infrastructure.persistence.channel_repository import ChannelRepository


class TestCapacityService:
    """Tests for CapacityService."""

    @pytest.fixture
    def service(self, test_db):
        """Create a capacity service."""
        return CapacityService(test_db)

    @pytest.fixture
    def channel(self, test_db):
        """Create a test channel."""
        repo = ChannelRepository(test_db)
        return repo.create(gemini_store_id="store/capacity-test", name="Capacity Test")

    def test_get_usage_empty_channel(self, service, channel):
        """Test getting usage for an empty channel."""
        usage = service.get_usage("store/capacity-test")

        assert usage is not None
        assert usage.file_count == 0
        assert usage.size_bytes == 0
        assert usage.file_usage_percent == 0.0
        assert usage.size_usage_percent == 0.0
        assert usage.can_upload is True
        assert usage.remaining_files == 100  # Default max
        assert usage.remaining_bytes > 0

    def test_get_usage_nonexistent_channel(self, service):
        """Test getting usage for nonexistent channel."""
        usage = service.get_usage("store/nonexistent")
        assert usage is None

    def test_validate_upload_success(self, service, channel):
        """Test validating a valid upload."""
        result = service.validate_upload("store/capacity-test", file_size=1024)
        assert result is True

    def test_validate_upload_file_count_exceeded(self, service, channel, test_db):
        """Test validation fails when file count exceeded."""
        # Set file count to max
        channel.file_count = 100
        test_db.commit()

        with pytest.raises(CapacityExceededError) as exc_info:
            service.validate_upload("store/capacity-test", file_size=1024)

        assert exc_info.value.limit_type == "file_count"
        assert "File count limit exceeded" in str(exc_info.value)

    def test_validate_upload_size_exceeded(self, service, channel, test_db):
        """Test validation fails when size exceeded."""
        # Set size close to max (500MB - 1KB)
        channel.total_size_bytes = 500 * 1024 * 1024 - 1024
        test_db.commit()

        # Try to upload 2KB (would exceed)
        with pytest.raises(CapacityExceededError) as exc_info:
            service.validate_upload("store/capacity-test", file_size=2048)

        assert exc_info.value.limit_type == "size"
        assert "Size limit exceeded" in str(exc_info.value)

    def test_validate_upload_nonexistent_channel(self, service):
        """Test validation passes for nonexistent channel (new channels)."""
        result = service.validate_upload("store/new-channel", file_size=1024)
        assert result is True

    def test_update_after_upload(self, service, channel):
        """Test updating capacity after upload."""
        # Initial state
        assert channel.file_count == 0
        assert channel.total_size_bytes == 0

        # Simulate upload
        usage = service.update_after_upload("store/capacity-test", file_size=1024 * 1024)

        assert usage is not None
        assert usage.file_count == 1
        assert usage.size_bytes == 1024 * 1024

    def test_update_after_multiple_uploads(self, service, channel):
        """Test capacity tracking after multiple uploads."""
        service.update_after_upload("store/capacity-test", file_size=1000)
        service.update_after_upload("store/capacity-test", file_size=2000)
        service.update_after_upload("store/capacity-test", file_size=3000)

        usage = service.get_usage("store/capacity-test")
        assert usage.file_count == 3
        assert usage.size_bytes == 6000

    def test_update_after_delete(self, service, channel, test_db):
        """Test updating capacity after file deletion."""
        # Setup: channel has some files
        channel.file_count = 5
        channel.total_size_bytes = 5000
        test_db.commit()

        # Delete one file
        usage = service.update_after_delete("store/capacity-test", file_size=1000)

        assert usage.file_count == 4
        assert usage.size_bytes == 4000

    def test_update_after_delete_no_negative(self, service, channel):
        """Test deletion doesn't go below zero."""
        # Try to delete from empty channel
        usage = service.update_after_delete("store/capacity-test", file_size=1000)

        assert usage.file_count == 0
        assert usage.size_bytes == 0

    def test_can_upload_false_when_at_limit(self, service, channel, test_db):
        """Test can_upload is False when at limits."""
        channel.file_count = 100  # At file limit
        test_db.commit()

        usage = service.get_usage("store/capacity-test")
        assert usage.can_upload is False

    def test_usage_percent_calculation(self, service, channel, test_db):
        """Test percentage calculations."""
        channel.file_count = 25  # 25% of 100
        channel.total_size_bytes = 250 * 1024 * 1024  # 50% of 500MB
        test_db.commit()

        usage = service.get_usage("store/capacity-test")
        assert usage.file_usage_percent == 25.0
        assert usage.size_usage_percent == 50.0

    def test_remaining_calculation(self, service, channel, test_db):
        """Test remaining capacity calculations."""
        channel.file_count = 30
        channel.total_size_bytes = 100 * 1024 * 1024  # 100MB
        test_db.commit()

        usage = service.get_usage("store/capacity-test")
        assert usage.remaining_files == 70
        assert usage.remaining_bytes == 400 * 1024 * 1024  # 400MB


class TestCapacityExceededError:
    """Tests for CapacityExceededError."""

    def test_error_attributes(self):
        """Test error has correct attributes."""
        error = CapacityExceededError(
            message="Test error",
            limit_type="file_count",
            current=100,
            limit=100,
        )

        assert str(error) == "Test error"
        assert error.limit_type == "file_count"
        assert error.current == 100
        assert error.limit == 100
