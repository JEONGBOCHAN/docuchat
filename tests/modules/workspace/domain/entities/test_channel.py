# -*- coding: utf-8 -*-
"""Tests for Channel domain entity."""

import pytest
from datetime import datetime, timedelta

from src.modules.workspace.domain.entities.channel import (
    Channel,
    MAX_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_DOCUMENTS_PER_CHANNEL,
    MAX_SIZE_BYTES,
)
from src.modules.workspace.domain.exceptions import ChannelNameError


class TestChannelValidation:
    """Tests for Channel validation."""

    def test_valid_channel_creation(self):
        """Test creating a valid channel."""
        channel = Channel(id="channel-123", name="Test Channel")
        assert channel.id == "channel-123"
        assert channel.name == "Test Channel"

    def test_empty_name_raises_error(self):
        """Test that empty name raises ChannelNameError."""
        with pytest.raises(ChannelNameError, match="cannot be empty"):
            Channel(id="channel-123", name="")

    def test_whitespace_name_raises_error(self):
        """Test that whitespace-only name raises ChannelNameError."""
        with pytest.raises(ChannelNameError, match="cannot be empty"):
            Channel(id="channel-123", name="   ")

    def test_name_too_long_raises_error(self):
        """Test that name exceeding max length raises ChannelNameError."""
        long_name = "x" * (MAX_NAME_LENGTH + 1)
        with pytest.raises(ChannelNameError, match="cannot exceed"):
            Channel(id="channel-123", name=long_name)

    def test_name_at_max_length_is_valid(self):
        """Test that name at max length is valid."""
        max_name = "x" * MAX_NAME_LENGTH
        channel = Channel(id="channel-123", name=max_name)
        assert len(channel.name) == MAX_NAME_LENGTH

    def test_description_too_long_raises_error(self):
        """Test that description exceeding max length raises error."""
        long_desc = "x" * (MAX_DESCRIPTION_LENGTH + 1)
        with pytest.raises(ChannelNameError, match="cannot exceed"):
            Channel(id="channel-123", name="Test", description=long_desc)


class TestChannelBusinessMethods:
    """Tests for Channel business methods."""

    def test_update_name(self):
        """Test updating channel name."""
        channel = Channel(id="channel-123", name="Old Name")
        channel.update_name("New Name")
        assert channel.name == "New Name"
        assert channel.updated_at is not None

    def test_update_name_invalid_raises_error(self):
        """Test that updating with invalid name raises error."""
        channel = Channel(id="channel-123", name="Name")
        with pytest.raises(ChannelNameError):
            channel.update_name("")

    def test_update_description(self):
        """Test updating channel description."""
        channel = Channel(id="channel-123", name="Name")
        channel.update_description("New description")
        assert channel.description == "New description"

    def test_record_access(self):
        """Test recording channel access."""
        channel = Channel(id="channel-123", name="Name")
        old_access = channel.last_accessed_at
        channel.record_access()
        assert channel.last_accessed_at >= old_access

    def test_update_stats(self):
        """Test updating channel stats."""
        channel = Channel(id="channel-123", name="Name")
        channel.update_stats(document_count=10, total_size_bytes=1000)
        assert channel.document_count == 10
        assert channel.total_size_bytes == 1000

    def test_update_stats_partial(self):
        """Test updating only one stat."""
        channel = Channel(
            id="channel-123",
            name="Name",
            document_count=5,
            total_size_bytes=500,
        )
        channel.update_stats(document_count=10)
        assert channel.document_count == 10
        assert channel.total_size_bytes == 500

    def test_update_stats_prevents_negative(self):
        """Test that update_stats prevents negative values."""
        channel = Channel(id="channel-123", name="Name")
        channel.update_stats(document_count=-5, total_size_bytes=-100)
        assert channel.document_count == 0
        assert channel.total_size_bytes == 0

    def test_increment_document_count(self):
        """Test incrementing document count."""
        channel = Channel(id="channel-123", name="Name")
        channel.increment_document_count(size_bytes=1000)
        assert channel.document_count == 1
        assert channel.total_size_bytes == 1000

    def test_decrement_document_count(self):
        """Test decrementing document count."""
        channel = Channel(
            id="channel-123",
            name="Name",
            document_count=5,
            total_size_bytes=5000,
        )
        channel.decrement_document_count(size_bytes=1000)
        assert channel.document_count == 4
        assert channel.total_size_bytes == 4000

    def test_decrement_document_count_prevents_negative(self):
        """Test that decrement doesn't go below zero."""
        channel = Channel(id="channel-123", name="Name")
        channel.decrement_document_count(size_bytes=1000)
        assert channel.document_count == 0
        assert channel.total_size_bytes == 0

    def test_soft_delete(self):
        """Test soft deleting a channel."""
        channel = Channel(id="channel-123", name="Name")
        channel.soft_delete()
        assert channel.is_deleted is True
        assert channel.deleted_at is not None

    def test_soft_delete_idempotent(self):
        """Test that soft delete is idempotent."""
        channel = Channel(id="channel-123", name="Name")
        channel.soft_delete()
        first_deleted_at = channel.deleted_at
        channel.soft_delete()
        assert channel.deleted_at == first_deleted_at

    def test_restore(self):
        """Test restoring a soft-deleted channel."""
        channel = Channel(id="channel-123", name="Name")
        channel.soft_delete()
        channel.restore()
        assert channel.is_deleted is False
        assert channel.deleted_at is None


class TestChannelCapacityMethods:
    """Tests for Channel capacity methods."""

    def test_can_add_document_true(self):
        """Test can_add_document returns True when under limits."""
        channel = Channel(id="channel-123", name="Name")
        assert channel.can_add_document(size_bytes=1000) is True

    def test_can_add_document_false_doc_limit(self):
        """Test can_add_document returns False when at document limit."""
        channel = Channel(
            id="channel-123",
            name="Name",
            document_count=MAX_DOCUMENTS_PER_CHANNEL,
        )
        assert channel.can_add_document() is False

    def test_can_add_document_false_size_limit(self):
        """Test can_add_document returns False when size would exceed limit."""
        channel = Channel(
            id="channel-123",
            name="Name",
            total_size_bytes=MAX_SIZE_BYTES - 100,
        )
        assert channel.can_add_document(size_bytes=200) is False

    def test_get_capacity_usage(self):
        """Test get_capacity_usage returns correct percentages."""
        channel = Channel(
            id="channel-123",
            name="Name",
            document_count=50,
            total_size_bytes=MAX_SIZE_BYTES // 2,
        )
        usage = channel.get_capacity_usage()
        assert usage["documents"] == 50.0
        assert usage["size"] == 50.0

    def test_is_at_capacity_true(self):
        """Test is_at_capacity returns True when at limit."""
        channel = Channel(
            id="channel-123",
            name="Name",
            document_count=MAX_DOCUMENTS_PER_CHANNEL,
        )
        assert channel.is_at_capacity() is True

    def test_is_at_capacity_false(self):
        """Test is_at_capacity returns False when under limit."""
        channel = Channel(id="channel-123", name="Name", document_count=50)
        assert channel.is_at_capacity() is False

    def test_is_near_capacity_true(self):
        """Test is_near_capacity returns True when above threshold."""
        channel = Channel(id="channel-123", name="Name", document_count=85)
        assert channel.is_near_capacity(threshold=80.0) is True

    def test_is_near_capacity_false(self):
        """Test is_near_capacity returns False when below threshold."""
        channel = Channel(id="channel-123", name="Name", document_count=50)
        assert channel.is_near_capacity(threshold=80.0) is False


class TestChannelQueryMethods:
    """Tests for Channel query methods."""

    def test_is_empty_true(self):
        """Test is_empty returns True when no documents."""
        channel = Channel(id="channel-123", name="Name")
        assert channel.is_empty() is True

    def test_is_empty_false(self):
        """Test is_empty returns False when has documents."""
        channel = Channel(id="channel-123", name="Name", document_count=1)
        assert channel.is_empty() is False

    def test_days_since_access(self):
        """Test days_since_access calculation."""
        past = datetime.now() - timedelta(days=5)
        channel = Channel(id="channel-123", name="Name", last_accessed_at=past)
        assert channel.days_since_access() == 5

    def test_is_inactive_true(self):
        """Test is_inactive returns True for old channel."""
        past = datetime.now() - timedelta(days=100)
        channel = Channel(id="channel-123", name="Name", last_accessed_at=past)
        assert channel.is_inactive(inactive_days=90) is True

    def test_is_inactive_false(self):
        """Test is_inactive returns False for recent channel."""
        channel = Channel(id="channel-123", name="Name")
        assert channel.is_inactive(inactive_days=90) is False

    def test_size_mb(self):
        """Test size_mb returns correct value."""
        # 10 MB = 10 * 1024 * 1024 bytes
        channel = Channel(
            id="channel-123",
            name="Name",
            total_size_bytes=10 * 1024 * 1024,
        )
        assert channel.size_mb() == 10.0


class TestChannelFactoryMethods:
    """Tests for Channel factory methods."""

    def test_create_basic(self):
        """Test creating a channel with factory method."""
        channel = Channel.create(id="channel-123", name="Test Channel")
        assert channel.id == "channel-123"
        assert channel.name == "Test Channel"
        assert channel.description == ""

    def test_create_with_description(self):
        """Test creating a channel with description."""
        channel = Channel.create(
            id="channel-123",
            name="Test Channel",
            description="Test description",
        )
        assert channel.description == "Test description"

    def test_create_strips_name(self):
        """Test that create strips whitespace from name."""
        channel = Channel.create(id="channel-123", name="  Test Channel  ")
        assert channel.name == "Test Channel"

    def test_to_dict(self):
        """Test converting channel to dictionary."""
        channel = Channel(
            id="channel-123",
            name="Test Channel",
            description="Test description",
            document_count=5,
            total_size_bytes=1000,
        )
        result = channel.to_dict()

        assert result["id"] == "channel-123"
        assert result["name"] == "Test Channel"
        assert result["description"] == "Test description"
        assert result["document_count"] == 5
        assert result["total_size_bytes"] == 1000
        assert result["is_deleted"] is False
