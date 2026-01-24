# -*- coding: utf-8 -*-
"""Channel lifecycle policy definitions and state management.

This module defines the lifecycle states and policies for channel management.
The policy is designed to optimize Gemini API costs while maintaining good UX.
"""

from enum import Enum
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass

from src.core.config import get_settings
from src.models.db_models import ChannelMetadata


class ChannelState(str, Enum):
    """Channel lifecycle states.

    States represent the lifecycle stage of a channel based on activity and usage.
    """
    ACTIVE = "active"           # Recently accessed, fully operational
    IDLE = "idle"               # No recent activity, but under threshold
    INACTIVE = "inactive"       # Exceeded inactivity threshold, candidate for cleanup
    OVER_LIMIT = "over_limit"   # Exceeded capacity limits


class ChannelAction(str, Enum):
    """Recommended actions for channel lifecycle management."""
    NONE = "none"                       # No action needed
    WARN_IDLE = "warn_idle"             # Warn user about approaching inactivity
    WARN_OVER_LIMIT = "warn_over_limit" # Warn user about capacity limits
    ARCHIVE = "archive"                 # Archive and cleanup inactive channel
    FORCE_CLEANUP = "force_cleanup"     # Force cleanup due to limits exceeded


@dataclass
class LifecycleConfig:
    """Lifecycle policy configuration.

    Attributes:
        inactive_days: Days of inactivity before channel is marked inactive
        idle_warning_days: Days of inactivity before showing idle warning
        max_files_per_channel: Maximum files allowed per channel
        max_channel_size_mb: Maximum size in MB per channel
    """
    inactive_days: int = 90
    idle_warning_days: int = 60  # 60 days - show warning before inactive
    max_files_per_channel: int = 100
    max_channel_size_mb: int = 500

    @classmethod
    def from_settings(cls) -> "LifecycleConfig":
        """Create config from application settings."""
        settings = get_settings()
        return cls(
            inactive_days=settings.channel_inactive_days,
            max_files_per_channel=settings.max_files_per_channel,
            max_channel_size_mb=settings.max_channel_size_mb,
        )


@dataclass
class LifecycleStatus:
    """Channel lifecycle status with recommended action.

    Attributes:
        state: Current lifecycle state of the channel
        action: Recommended action to take
        days_since_access: Days since last access
        days_until_inactive: Days remaining until inactive (negative if already inactive)
        usage_percent: Percentage of capacity used (0-100+)
        message: Human-readable status message
    """
    state: ChannelState
    action: ChannelAction
    days_since_access: int
    days_until_inactive: int
    usage_percent: float
    message: str


class LifecyclePolicy:
    """Channel lifecycle policy manager.

    Determines the lifecycle state and recommended actions for channels
    based on activity and capacity usage.

    Example:
        ```python
        policy = LifecyclePolicy()
        status = policy.get_status(channel)

        if status.action == ChannelAction.ARCHIVE:
            # Cleanup the channel
            pass
        ```
    """

    def __init__(self, config: LifecycleConfig | None = None):
        """Initialize policy with optional custom config.

        Args:
            config: Optional custom configuration. Uses settings if not provided.
        """
        self.config = config or LifecycleConfig.from_settings()

    def get_status(self, channel: ChannelMetadata) -> LifecycleStatus:
        """Get the lifecycle status for a channel.

        Args:
            channel: The channel metadata to evaluate

        Returns:
            LifecycleStatus with state, action, and details
        """
        now = datetime.now(UTC)
        last_accessed = channel.last_accessed_at

        # Ensure last_accessed is timezone-aware
        if last_accessed.tzinfo is None:
            from datetime import timezone
            last_accessed = last_accessed.replace(tzinfo=timezone.utc)

        days_since_access = (now - last_accessed).days
        days_until_inactive = self.config.inactive_days - days_since_access

        # Calculate usage percentage (based on file count and size)
        file_usage = (channel.file_count / self.config.max_files_per_channel) * 100
        size_mb = channel.total_size_bytes / (1024 * 1024)
        size_usage = (size_mb / self.config.max_channel_size_mb) * 100
        usage_percent = max(file_usage, size_usage)

        # Determine state and action
        state, action, message = self._evaluate_state(
            days_since_access=days_since_access,
            days_until_inactive=days_until_inactive,
            usage_percent=usage_percent,
        )

        return LifecycleStatus(
            state=state,
            action=action,
            days_since_access=days_since_access,
            days_until_inactive=days_until_inactive,
            usage_percent=round(usage_percent, 1),
            message=message,
        )

    def _evaluate_state(
        self,
        days_since_access: int,
        days_until_inactive: int,
        usage_percent: float,
    ) -> tuple[ChannelState, ChannelAction, str]:
        """Evaluate channel state based on metrics.

        Returns:
            Tuple of (state, action, message)
        """
        # Check capacity limits first (takes priority)
        if usage_percent >= 100:
            return (
                ChannelState.OVER_LIMIT,
                ChannelAction.WARN_OVER_LIMIT,
                f"Channel has exceeded capacity limits ({usage_percent:.0f}% used). "
                "Please remove some documents to continue using this channel.",
            )

        # Check inactivity
        if days_until_inactive <= 0:
            return (
                ChannelState.INACTIVE,
                ChannelAction.ARCHIVE,
                f"Channel has been inactive for {days_since_access} days. "
                "It is scheduled for cleanup. Access the channel to prevent deletion.",
            )

        # Check idle warning threshold
        if days_since_access >= self.config.idle_warning_days:
            return (
                ChannelState.IDLE,
                ChannelAction.WARN_IDLE,
                f"Channel has been idle for {days_since_access} days. "
                f"It will be marked inactive in {days_until_inactive} days.",
            )

        # Capacity warning (80% threshold)
        if usage_percent >= 80:
            return (
                ChannelState.ACTIVE,
                ChannelAction.WARN_OVER_LIMIT,
                f"Channel is approaching capacity limits ({usage_percent:.0f}% used).",
            )

        # All good
        return (
            ChannelState.ACTIVE,
            ChannelAction.NONE,
            "Channel is active and within limits.",
        )

    def get_inactive_channels(
        self,
        channels: list[ChannelMetadata],
    ) -> list[tuple[ChannelMetadata, LifecycleStatus]]:
        """Get all inactive channels with their status.

        Args:
            channels: List of channels to evaluate

        Returns:
            List of (channel, status) tuples for inactive channels
        """
        inactive = []
        for channel in channels:
            status = self.get_status(channel)
            if status.state == ChannelState.INACTIVE:
                inactive.append((channel, status))
        return inactive

    def get_channels_by_state(
        self,
        channels: list[ChannelMetadata],
        state: ChannelState,
    ) -> list[tuple[ChannelMetadata, LifecycleStatus]]:
        """Get all channels in a specific state.

        Args:
            channels: List of channels to evaluate
            state: The state to filter by

        Returns:
            List of (channel, status) tuples for matching channels
        """
        matching = []
        for channel in channels:
            status = self.get_status(channel)
            if status.state == state:
                matching.append((channel, status))
        return matching
