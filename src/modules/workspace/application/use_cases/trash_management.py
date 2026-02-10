# -*- coding: utf-8 -*-
"""Trash management use case.

Orchestrates trash operations: list, restore, permanent delete, empty, stats.
No FastAPI/HTTP dependencies — pure application logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.persistence import (
    TrashRepositoryPort,
    TrashItemDTO,
    ChannelMetadataDTO,
    NoteDTO,
)

logger = logging.getLogger(__name__)


class TrashItemNotFoundError(Exception):
    """Raised when a trashed item is not found."""
    pass


class ExternalDeleteFailedError(Exception):
    """Raised when external storage deletion fails."""
    pass


@dataclass
class EmptyTrashResultDTO:
    deleted_channels: int
    deleted_notes: int
    failed_channels: int
    message: str


class TrashManagementUseCase:
    """Orchestrates trash management operations."""

    def __init__(
        self,
        trash_repo: TrashRepositoryPort,
        channel_port: ChannelPort,
    ):
        self._trash_repo = trash_repo
        self._channel_port = channel_port

    def list_items(self) -> list[TrashItemDTO]:
        """List all trashed items."""
        return self._trash_repo.get_all_trashed_items()

    def restore(self, item_type: str, item_id: int) -> ChannelMetadataDTO | NoteDTO:
        """Restore a trashed item.

        Raises:
            TrashItemNotFoundError: Item not found in trash.
            ValueError: Invalid item type.
        """
        if item_type == "channel":
            result = self._trash_repo.restore_channel(item_id)
            if not result:
                raise TrashItemNotFoundError(f"Trashed channel not found: {item_id}")
            return result
        elif item_type == "note":
            result = self._trash_repo.restore_note(item_id)
            if not result:
                raise TrashItemNotFoundError(f"Trashed note not found: {item_id}")
            return result
        else:
            raise ValueError(f"Invalid item type: {item_type}")

    def permanent_delete(self, item_type: str, item_id: int) -> None:
        """Permanently delete a trashed item.

        For channels, deletes from external storage first.

        Raises:
            TrashItemNotFoundError: Item not found.
            ExternalDeleteFailedError: External storage deletion failed.
            ValueError: Invalid item type.
        """
        if item_type == "channel":
            channel_dto = self._trash_repo.get_trashed_channel_by_db_id(item_id)
            if not channel_dto:
                raise TrashItemNotFoundError(f"Trashed channel not found: {item_id}")

            success = self._channel_port.delete_channel(channel_dto.gemini_store_id, force=True)
            if not success:
                raise ExternalDeleteFailedError(
                    "Failed to delete channel from external storage. Channel remains in trash for retry."
                )

            if not self._trash_repo.permanent_delete_channel(item_id):
                raise RuntimeError("Failed to delete channel from database")

        elif item_type == "note":
            if not self._trash_repo.permanent_delete_note(item_id):
                raise TrashItemNotFoundError(f"Trashed note not found: {item_id}")

        else:
            raise ValueError(f"Invalid item type: {item_type}")

    def empty(self) -> EmptyTrashResultDTO:
        """Permanently delete all items in the trash.

        Channels are only DB-deleted if external deletion succeeds.
        """
        trashed_channels = self._trash_repo.get_all_trashed_channels()
        deleted_channels = 0
        failed_channels = 0

        for ch in trashed_channels:
            if self._channel_port.delete_channel(ch.gemini_store_id, force=True):
                self._trash_repo.permanent_delete_channel(ch.id)
                deleted_channels += 1
            else:
                failed_channels += 1

        all_items = self._trash_repo.get_all_trashed_items()
        deleted_notes = 0
        for item in all_items:
            if item.type == "note":
                if self._trash_repo.permanent_delete_note(item.id):
                    deleted_notes += 1

        message = f"Permanently deleted {deleted_channels} channels and {deleted_notes} notes"
        if failed_channels > 0:
            message += f" ({failed_channels} channels failed external deletion and remain in trash)"

        return EmptyTrashResultDTO(
            deleted_channels=deleted_channels,
            deleted_notes=deleted_notes,
            failed_channels=failed_channels,
            message=message,
        )

    def stats(self) -> dict[str, Any]:
        """Get trash statistics."""
        return self._trash_repo.get_trash_stats()
