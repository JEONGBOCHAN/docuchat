# -*- coding: utf-8 -*-
"""Capacity management service for channel storage limits.

This module provides capacity checking and validation for channel storage.
It enforces file count and size limits to prevent resource exhaustion.
"""

from dataclasses import dataclass

from src.core.config import get_settings
from src.application.ports.persistence import ChannelRepositoryPort, ChannelMetadataDTO
from src.domain.exceptions import CapacityExceededError


@dataclass
class CapacityUsage:
    """Current capacity usage for a channel.

    Attributes:
        file_count: Current number of files
        max_files: Maximum allowed files
        file_usage_percent: Percentage of file limit used
        size_bytes: Current size in bytes
        max_size_bytes: Maximum allowed size in bytes
        size_usage_percent: Percentage of size limit used
        can_upload: Whether new uploads are allowed
        remaining_files: Number of files that can still be uploaded
        remaining_bytes: Bytes that can still be uploaded
    """
    file_count: int
    max_files: int
    file_usage_percent: float
    size_bytes: int
    max_size_bytes: int
    size_usage_percent: float
    can_upload: bool
    remaining_files: int
    remaining_bytes: int


class CapacityService:
    """Service for managing channel capacity limits.

    Provides methods for checking and enforcing storage limits.

    Example:
        ```python
        service = CapacityService(channel_repo=channel_repo_port)

        # Check if upload is allowed
        service.validate_upload(channel_id, file_size=1024*1024)  # 1MB

        # Get current usage
        usage = service.get_usage(channel_id)
        print(f"Using {usage.file_usage_percent}% of file limit")
        ```
    """

    def __init__(self, channel_repo: ChannelRepositoryPort):
        """Initialize service with channel repository port.

        Args:
            channel_repo: Channel repository port
        """
        self.repo = channel_repo
        settings = get_settings()
        self.max_files = settings.max_files_per_channel
        self.max_size_bytes = settings.max_channel_size_mb * 1024 * 1024

    def get_usage(self, channel_id: str) -> CapacityUsage | None:
        """Get current capacity usage for a channel.

        Args:
            channel_id: The Gemini store ID of the channel

        Returns:
            CapacityUsage object or None if channel not found
        """
        channel = self.repo.get_by_gemini_id(channel_id)
        if not channel:
            return None

        return self._calculate_usage(channel)

    def _calculate_usage(self, channel: ChannelMetadataDTO) -> CapacityUsage:
        """Calculate capacity usage from channel metadata."""
        file_usage = (channel.file_count / self.max_files) * 100
        size_usage = (channel.total_size_bytes / self.max_size_bytes) * 100

        remaining_files = max(0, self.max_files - channel.file_count)
        remaining_bytes = max(0, self.max_size_bytes - channel.total_size_bytes)

        can_upload = channel.file_count < self.max_files and channel.total_size_bytes < self.max_size_bytes

        return CapacityUsage(
            file_count=channel.file_count,
            max_files=self.max_files,
            file_usage_percent=round(file_usage, 1),
            size_bytes=channel.total_size_bytes,
            max_size_bytes=self.max_size_bytes,
            size_usage_percent=round(size_usage, 1),
            can_upload=can_upload,
            remaining_files=remaining_files,
            remaining_bytes=remaining_bytes,
        )

    def validate_upload(
        self,
        channel_id: str,
        file_size: int,
        file_count: int = 1,
    ) -> bool:
        """Validate if an upload is allowed within capacity limits.

        Args:
            channel_id: The Gemini store ID of the channel
            file_size: Size of the file to upload in bytes
            file_count: Number of files being uploaded (default 1)

        Returns:
            True if upload is allowed

        Raises:
            CapacityExceededError: If the upload would exceed limits
        """
        channel = self.repo.get_by_gemini_id(channel_id)

        # If channel doesn't exist in DB yet, allow the upload
        # (will be tracked after creation)
        if not channel:
            return True

        # Check file count limit
        new_file_count = channel.file_count + file_count
        if new_file_count > self.max_files:
            raise CapacityExceededError(
                f"File count limit exceeded. Current: {channel.file_count}, "
                f"Limit: {self.max_files}. Cannot add {file_count} file(s).",
                limit_type="file_count",
                current=channel.file_count,
                limit=self.max_files,
            )

        # Check size limit
        new_size = channel.total_size_bytes + file_size
        if new_size > self.max_size_bytes:
            current_mb = channel.total_size_bytes / (1024 * 1024)
            limit_mb = self.max_size_bytes / (1024 * 1024)
            file_mb = file_size / (1024 * 1024)
            raise CapacityExceededError(
                f"Size limit exceeded. Current: {current_mb:.1f}MB, "
                f"Limit: {limit_mb:.0f}MB. Cannot add {file_mb:.1f}MB file.",
                limit_type="size",
                current=channel.total_size_bytes,
                limit=self.max_size_bytes,
            )

        return True

    def update_after_upload(
        self,
        channel_id: str,
        file_size: int,
        file_count: int = 1,
    ) -> CapacityUsage | None:
        """Update capacity tracking after a successful upload.

        Args:
            channel_id: The Gemini store ID of the channel
            file_size: Size of the uploaded file in bytes
            file_count: Number of files uploaded (default 1)

        Returns:
            Updated CapacityUsage or None if channel not found
        """
        channel = self.repo.get_by_gemini_id(channel_id)
        if not channel:
            # Auto-create local metadata if not exists
            # This ensures file_count is tracked even for newly created channels
            channel = self.repo.create(
                gemini_store_id=channel_id,
                name="",  # Name will be synced on next channel list
            )

        # Update stats
        new_file_count = channel.file_count + file_count
        new_size = channel.total_size_bytes + file_size

        self.repo.update_stats(
            gemini_store_id=channel_id,
            file_count=new_file_count,
            total_size_bytes=new_size,
        )

        # Refresh channel and return new usage
        channel = self.repo.get_by_gemini_id(channel_id)
        return self._calculate_usage(channel)

    def update_after_delete(
        self,
        channel_id: str,
        file_size: int,
        file_count: int = 1,
    ) -> CapacityUsage | None:
        """Update capacity tracking after a file deletion.

        Args:
            channel_id: The Gemini store ID of the channel
            file_size: Size of the deleted file in bytes
            file_count: Number of files deleted (default 1)

        Returns:
            Updated CapacityUsage or None if channel not found
        """
        channel = self.repo.get_by_gemini_id(channel_id)
        if not channel:
            return None

        # Update stats (ensure non-negative)
        new_file_count = max(0, channel.file_count - file_count)
        new_size = max(0, channel.total_size_bytes - file_size)

        self.repo.update_stats(
            gemini_store_id=channel_id,
            file_count=new_file_count,
            total_size_bytes=new_size,
        )

        # Refresh channel and return new usage
        channel = self.repo.get_by_gemini_id(channel_id)
        return self._calculate_usage(channel)


def get_capacity_service(channel_repo: ChannelRepositoryPort) -> CapacityService:
    """Get a CapacityService instance.

    Args:
        channel_repo: Channel repository port

    Returns:
        CapacityService instance
    """
    return CapacityService(channel_repo)
