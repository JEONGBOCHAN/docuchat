# -*- coding: utf-8 -*-
"""Tests for lifecycle policy module."""

from datetime import datetime, timedelta, UTC

import pytest

from src.services.lifecycle_policy import (
    ChannelState,
    ChannelAction,
    LifecycleConfig,
    LifecyclePolicy,
)
from src.infrastructure.persistence.channel_repository import ChannelRepository


class TestLifecyclePolicy:
    """Tests for LifecyclePolicy."""

    @pytest.fixture
    def policy(self):
        """Create a policy with test config."""
        config = LifecycleConfig(
            inactive_days=90,
            idle_warning_days=60,
            max_files_per_channel=100,
            max_channel_size_mb=500,
        )
        return LifecyclePolicy(config)

    @pytest.fixture
    def active_channel(self, test_db):
        """Create an active channel (accessed recently)."""
        repo = ChannelRepository(test_db)
        return repo.create(gemini_store_id="store/active", name="Active Channel")

    @pytest.fixture
    def idle_channel(self, test_db):
        """Create an idle channel (70 days since access)."""
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="store/idle", name="Idle Channel")
        channel.last_accessed_at = datetime.now(UTC) - timedelta(days=70)
        test_db.commit()
        return channel

    @pytest.fixture
    def inactive_channel(self, test_db):
        """Create an inactive channel (100 days since access)."""
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="store/inactive", name="Inactive Channel")
        channel.last_accessed_at = datetime.now(UTC) - timedelta(days=100)
        test_db.commit()
        return channel

    @pytest.fixture
    def over_limit_channel(self, test_db):
        """Create a channel over capacity limits."""
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="store/overlimit", name="Over Limit")
        channel.file_count = 120  # Over 100 limit
        test_db.commit()
        return channel

    def test_active_channel_status(self, policy, active_channel):
        """Test status for active channel."""
        status = policy.get_status(active_channel)

        assert status.state == ChannelState.ACTIVE
        assert status.action == ChannelAction.NONE
        assert status.days_since_access == 0
        assert status.days_until_inactive == 90
        assert status.usage_percent == 0.0

    def test_idle_channel_status(self, policy, idle_channel):
        """Test status for idle channel (past warning threshold)."""
        status = policy.get_status(idle_channel)

        assert status.state == ChannelState.IDLE
        assert status.action == ChannelAction.WARN_IDLE
        assert status.days_since_access == 70
        assert status.days_until_inactive == 20
        assert "idle for 70 days" in status.message

    def test_inactive_channel_status(self, policy, inactive_channel):
        """Test status for inactive channel (past threshold)."""
        status = policy.get_status(inactive_channel)

        assert status.state == ChannelState.INACTIVE
        assert status.action == ChannelAction.ARCHIVE
        assert status.days_since_access == 100
        assert status.days_until_inactive == -10  # Already inactive
        assert "scheduled for cleanup" in status.message

    def test_over_limit_channel_status(self, policy, over_limit_channel):
        """Test status for channel over capacity."""
        status = policy.get_status(over_limit_channel)

        assert status.state == ChannelState.OVER_LIMIT
        assert status.action == ChannelAction.WARN_OVER_LIMIT
        assert status.usage_percent == 120.0  # 120 files / 100 limit
        assert "exceeded capacity" in status.message

    def test_approaching_limit_warning(self, policy, test_db):
        """Test warning when approaching capacity limits."""
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="store/approaching", name="Approaching")
        channel.file_count = 85  # 85% of 100 limit
        test_db.commit()

        status = policy.get_status(channel)

        assert status.state == ChannelState.ACTIVE
        assert status.action == ChannelAction.WARN_OVER_LIMIT
        assert "approaching capacity" in status.message

    def test_get_inactive_channels(self, policy, test_db):
        """Test getting all inactive channels."""
        repo = ChannelRepository(test_db)

        # Create mix of channels
        active = repo.create(gemini_store_id="store/1", name="Active")

        idle = repo.create(gemini_store_id="store/2", name="Idle")
        idle.last_accessed_at = datetime.now(UTC) - timedelta(days=70)

        inactive1 = repo.create(gemini_store_id="store/3", name="Inactive 1")
        inactive1.last_accessed_at = datetime.now(UTC) - timedelta(days=100)

        inactive2 = repo.create(gemini_store_id="store/4", name="Inactive 2")
        inactive2.last_accessed_at = datetime.now(UTC) - timedelta(days=120)

        test_db.commit()

        channels = repo.get_all()
        inactive_list = policy.get_inactive_channels(channels)

        assert len(inactive_list) == 2
        names = {ch.name for ch, _ in inactive_list}
        assert names == {"Inactive 1", "Inactive 2"}

    def test_get_channels_by_state(self, policy, test_db):
        """Test filtering channels by state."""
        repo = ChannelRepository(test_db)

        # Create mix
        repo.create(gemini_store_id="store/a1", name="Active 1")
        repo.create(gemini_store_id="store/a2", name="Active 2")

        idle = repo.create(gemini_store_id="store/i1", name="Idle 1")
        idle.last_accessed_at = datetime.now(UTC) - timedelta(days=70)
        test_db.commit()

        channels = repo.get_all()

        # Get active channels
        active_list = policy.get_channels_by_state(channels, ChannelState.ACTIVE)
        assert len(active_list) == 2

        # Get idle channels
        idle_list = policy.get_channels_by_state(channels, ChannelState.IDLE)
        assert len(idle_list) == 1
        assert idle_list[0][0].name == "Idle 1"

    def test_size_based_limit(self, policy, test_db):
        """Test that size-based limits work."""
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="store/size", name="Size Test")
        # 600 MB = 120% of 500 MB limit
        channel.total_size_bytes = 600 * 1024 * 1024
        test_db.commit()

        status = policy.get_status(channel)

        assert status.state == ChannelState.OVER_LIMIT
        assert status.usage_percent == 120.0

    def test_custom_config(self, test_db):
        """Test policy with custom config."""
        config = LifecycleConfig(
            inactive_days=30,  # Much shorter
            idle_warning_days=20,
            max_files_per_channel=50,
            max_channel_size_mb=100,
        )
        policy = LifecyclePolicy(config)

        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="store/custom", name="Custom")
        channel.last_accessed_at = datetime.now(UTC) - timedelta(days=25)
        test_db.commit()

        status = policy.get_status(channel)

        # Should be idle (past 20 day warning, before 30 day inactive)
        assert status.state == ChannelState.IDLE
        assert status.days_until_inactive == 5


class TestLifecycleConfig:
    """Tests for LifecycleConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LifecycleConfig()

        assert config.inactive_days == 90
        assert config.idle_warning_days == 60
        assert config.max_files_per_channel == 100
        assert config.max_channel_size_mb == 500

    def test_from_settings(self):
        """Test creating config from settings."""
        config = LifecycleConfig.from_settings()

        # Should match values from get_settings()
        assert config.inactive_days == 90
        assert config.max_files_per_channel == 100
        assert config.max_channel_size_mb == 500
