# -*- coding: utf-8 -*-
"""Channel lifecycle domain rules.

Pure functions that evaluate channel state based on metrics.
No external dependencies — only stdlib.
"""

from enum import Enum


class ChannelState(str, Enum):
    """Channel lifecycle states."""

    ACTIVE = "active"
    IDLE = "idle"
    INACTIVE = "inactive"
    OVER_LIMIT = "over_limit"


class ChannelAction(str, Enum):
    """Recommended actions for channel lifecycle management."""

    NONE = "none"
    WARN_IDLE = "warn_idle"
    WARN_OVER_LIMIT = "warn_over_limit"
    ARCHIVE = "archive"
    FORCE_CLEANUP = "force_cleanup"


def evaluate_channel_state(
    days_since_access: int,
    days_until_inactive: int,
    usage_percent: float,
    idle_warning_days: int,
) -> tuple[ChannelState, ChannelAction, str]:
    """Evaluate channel lifecycle state from metrics.

    Priority order:
      1. Over capacity (>=100%) → OVER_LIMIT + WARN_OVER_LIMIT
      2. Inactive (days_until_inactive <= 0) → INACTIVE + ARCHIVE
      3. Idle warning (days_since_access >= idle_warning_days) → IDLE + WARN_IDLE
      4. Approaching capacity (>=80%) → ACTIVE + WARN_OVER_LIMIT
      5. Default → ACTIVE + NONE

    Args:
        days_since_access: Number of days since channel was last accessed.
        days_until_inactive: Days remaining before channel becomes inactive.
        usage_percent: Capacity usage percentage (0-100+).
        idle_warning_days: Threshold for idle warning.

    Returns:
        Tuple of (state, action, message).
    """
    if usage_percent >= 100:
        return (
            ChannelState.OVER_LIMIT,
            ChannelAction.WARN_OVER_LIMIT,
            f"Channel has exceeded capacity limits ({usage_percent:.0f}% used). "
            "Please remove some documents to continue using this channel.",
        )

    if days_until_inactive <= 0:
        return (
            ChannelState.INACTIVE,
            ChannelAction.ARCHIVE,
            f"Channel has been inactive for {days_since_access} days. "
            "It is scheduled for cleanup. Access the channel to prevent deletion.",
        )

    if days_since_access >= idle_warning_days:
        return (
            ChannelState.IDLE,
            ChannelAction.WARN_IDLE,
            f"Channel has been idle for {days_since_access} days. "
            f"It will be marked inactive in {days_until_inactive} days.",
        )

    if usage_percent >= 80:
        return (
            ChannelState.ACTIVE,
            ChannelAction.WARN_OVER_LIMIT,
            f"Channel is approaching capacity limits ({usage_percent:.0f}% used).",
        )

    return (
        ChannelState.ACTIVE,
        ChannelAction.NONE,
        "Channel is active and within limits.",
    )
