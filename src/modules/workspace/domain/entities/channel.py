# -*- coding: utf-8 -*-
"""
Channel Domain Entity.

Pure Python representation of a channel (document workspace) with business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.modules.workspace.domain.exceptions import ChannelNameError


# Validation constants
MAX_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1000
MAX_DOCUMENTS_PER_CHANNEL = 100
MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


@dataclass
class Channel:
    """A channel (document workspace) in the system.

    A channel is a container for documents that can be queried together.
    It represents a logical grouping of related documents.

    Attributes:
        id: Unique channel identifier
        name: Display name of the channel
        description: Optional description
        created_at: When the channel was created
        updated_at: When the channel was last modified
        last_accessed_at: When the channel was last accessed
        document_count: Number of documents in the channel
        total_size_bytes: Total size of all documents in bytes
        is_deleted: Soft delete flag
        deleted_at: When the channel was deleted
        metadata: Additional channel metadata
    """

    id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: datetime = field(default_factory=datetime.now)
    document_count: int = 0
    total_size_bytes: int = 0
    is_deleted: bool = False
    deleted_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate channel after initialization."""
        self._validate_name(self.name)
        self._validate_description(self.description)

    # =========================================================================
    # Validation Methods
    # =========================================================================

    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate channel name.

        Args:
            name: Name to validate

        Raises:
            ChannelNameError: If name is invalid
        """
        if not name or not name.strip():
            raise ChannelNameError("Channel name cannot be empty")
        if len(name) > MAX_NAME_LENGTH:
            raise ChannelNameError(
                f"Channel name cannot exceed {MAX_NAME_LENGTH} characters"
            )

    @staticmethod
    def _validate_description(description: str) -> None:
        """Validate channel description.

        Args:
            description: Description to validate

        Raises:
            ChannelNameError: If description is too long
        """
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise ChannelNameError(
                f"Channel description cannot exceed {MAX_DESCRIPTION_LENGTH} characters"
            )

    # =========================================================================
    # Business Methods
    # =========================================================================

    def update_name(self, new_name: str) -> None:
        """Update channel name.

        Args:
            new_name: New name for the channel

        Raises:
            ChannelNameError: If new name is invalid
        """
        self._validate_name(new_name)
        self.name = new_name.strip()
        self._touch()

    def update_description(self, new_description: str) -> None:
        """Update channel description.

        Args:
            new_description: New description for the channel

        Raises:
            ChannelNameError: If new description is too long
        """
        self._validate_description(new_description)
        self.description = new_description
        self._touch()

    def record_access(self) -> None:
        """Record a channel access."""
        self.last_accessed_at = datetime.now()

    def update_stats(
        self,
        document_count: int | None = None,
        total_size_bytes: int | None = None,
    ) -> None:
        """Update channel statistics.

        Args:
            document_count: New document count (if provided)
            total_size_bytes: New total size (if provided)
        """
        if document_count is not None:
            self.document_count = max(0, document_count)
        if total_size_bytes is not None:
            self.total_size_bytes = max(0, total_size_bytes)
        self._touch()

    def increment_document_count(self, size_bytes: int = 0) -> None:
        """Increment document count when a document is added.

        Args:
            size_bytes: Size of the added document
        """
        self.document_count += 1
        self.total_size_bytes += size_bytes
        self._touch()

    def decrement_document_count(self, size_bytes: int = 0) -> None:
        """Decrement document count when a document is removed.

        Args:
            size_bytes: Size of the removed document
        """
        self.document_count = max(0, self.document_count - 1)
        self.total_size_bytes = max(0, self.total_size_bytes - size_bytes)
        self._touch()

    def soft_delete(self) -> None:
        """Mark the channel as deleted (soft delete)."""
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = datetime.now()

    def restore(self) -> None:
        """Restore a soft-deleted channel."""
        if self.is_deleted:
            self.is_deleted = False
            self.deleted_at = None
            self._touch()

    def _touch(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()

    # =========================================================================
    # Capacity Methods
    # =========================================================================

    def can_add_document(self, size_bytes: int = 0) -> bool:
        """Check if a document can be added to this channel.

        Args:
            size_bytes: Size of the document to add

        Returns:
            True if document can be added, False otherwise
        """
        if self.document_count >= MAX_DOCUMENTS_PER_CHANNEL:
            return False
        if self.total_size_bytes + size_bytes > MAX_SIZE_BYTES:
            return False
        return True

    def get_capacity_usage(self) -> dict[str, float]:
        """Get capacity usage as percentages.

        Returns:
            Dictionary with 'documents' and 'size' percentages
        """
        doc_pct = (self.document_count / MAX_DOCUMENTS_PER_CHANNEL) * 100
        size_pct = (self.total_size_bytes / MAX_SIZE_BYTES) * 100
        return {"documents": doc_pct, "size": size_pct}

    def is_at_capacity(self) -> bool:
        """Check if channel is at document or size capacity.

        Returns:
            True if at capacity, False otherwise
        """
        return (
            self.document_count >= MAX_DOCUMENTS_PER_CHANNEL
            or self.total_size_bytes >= MAX_SIZE_BYTES
        )

    def is_near_capacity(self, threshold: float = 80.0) -> bool:
        """Check if channel is near capacity.

        Args:
            threshold: Percentage threshold to consider "near capacity"

        Returns:
            True if any capacity metric is above threshold
        """
        usage = self.get_capacity_usage()
        return usage["documents"] >= threshold or usage["size"] >= threshold

    # =========================================================================
    # Query Methods
    # =========================================================================

    def is_empty(self) -> bool:
        """Check if channel has no documents."""
        return self.document_count == 0

    def days_since_access(self) -> int:
        """Get number of days since last access.

        Returns:
            Number of days since last access
        """
        delta = datetime.now() - self.last_accessed_at
        return delta.days

    def is_inactive(self, inactive_days: int = 90) -> bool:
        """Check if channel is inactive.

        Args:
            inactive_days: Number of days to consider inactive

        Returns:
            True if last access was more than inactive_days ago
        """
        return self.days_since_access() > inactive_days

    def size_mb(self) -> float:
        """Get total size in megabytes.

        Returns:
            Total size in MB
        """
        return self.total_size_bytes / (1024 * 1024)

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def create(
        cls,
        id: str,
        name: str,
        description: str = "",
    ) -> "Channel":
        """Create a new channel with validation.

        Args:
            id: Channel ID
            name: Channel name
            description: Optional description

        Returns:
            New Channel instance

        Raises:
            ChannelNameError: If name is invalid
        """
        return cls(id=id, name=name.strip(), description=description)

    def to_dict(self) -> dict[str, Any]:
        """Convert channel to dictionary.

        Returns:
            Dictionary representation of the channel
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
            "document_count": self.document_count,
            "total_size_bytes": self.total_size_bytes,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "metadata": self.metadata,
        }
