# -*- coding: utf-8 -*-
"""Channel lifecycle policy definitions and state management.

This module defines the lifecycle states and policies for channel management.
The policy is designed to optimize Gemini API costs while maintaining good UX.
"""

from enum import Enum
from datetime import datetime, timedelta, UTC
from dataclasses import dataclass

from src.shared.kernel.contracts.ports.persistence import ChannelMetadataDTO
from src.modules.ops.domain.lifecycle_rules import (
    ChannelState,
    ChannelAction,
    evaluate_channel_state,
)


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
        policy = LifecyclePolicy(config)
        status = policy.get_status(channel)

        if status.action == ChannelAction.ARCHIVE:
            # Cleanup the channel
            pass
        ```
    """

    def __init__(self, config: LifecycleConfig):
        """Initialize policy with lifecycle configuration.

        Args:
            config: Lifecycle configuration with thresholds and limits.
        """
        self.config = config

    def get_status(self, channel: ChannelMetadataDTO) -> LifecycleStatus:
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

        Delegates to the domain-layer pure function.

        Returns:
            Tuple of (state, action, message)
        """
        return evaluate_channel_state(
            days_since_access=days_since_access,
            days_until_inactive=days_until_inactive,
            usage_percent=usage_percent,
            idle_warning_days=self.config.idle_warning_days,
        )

    def get_inactive_channels(
        self,
        channels: list[ChannelMetadataDTO],
    ) -> list[tuple[ChannelMetadataDTO, LifecycleStatus]]:
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
        channels: list[ChannelMetadataDTO],
        state: ChannelState,
    ) -> list[tuple[ChannelMetadataDTO, LifecycleStatus]]:
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
