# -*- coding: utf-8 -*-
"""Repository for trash (soft delete) operations."""

from datetime import datetime, UTC, timedelta
from sqlalchemy.orm import Session

from src.models.db_models import ChannelMetadata, NoteDB
from src.models.trash import TrashItem, TrashItemType


class TrashRepository:
    """Repository for trash operations."""

    # Default retention period for trashed items (30 days)
    DEFAULT_RETENTION_DAYS = 30

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ========== Soft Delete Operations ==========

    def soft_delete_channel(self, gemini_store_id: str) -> ChannelMetadata | None:
        """Soft delete a channel by setting deleted_at.

        Args:
            gemini_store_id: The Gemini File Search Store ID

        Returns:
            Soft-deleted ChannelMetadata or None if not found
        """
        channel = self.db.query(ChannelMetadata).filter(
            ChannelMetadata.gemini_store_id == gemini_store_id,
            ChannelMetadata.deleted_at.is_(None),
        ).first()

        if channel:
            channel.deleted_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(channel)
        return channel

    def soft_delete_note(self, note_id: int) -> NoteDB | None:
        """Soft delete a note by setting deleted_at.

        Args:
            note_id: The note ID

        Returns:
            Soft-deleted NoteDB or None if not found
        """
        note = self.db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.is_(None),
        ).first()

        if note:
            note.deleted_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(note)
        return note

    # ========== List Trashed Items ==========

    def get_trashed_channels(self) -> list[ChannelMetadata]:
        """Get all soft-deleted channels.

        Returns:
            List of soft-deleted channels
        """
        return self.db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None)
        ).order_by(ChannelMetadata.deleted_at.desc()).all()

    def get_trashed_notes(self) -> list[NoteDB]:
        """Get all soft-deleted notes.

        Returns:
            List of soft-deleted notes
        """
        return self.db.query(NoteDB).filter(
            NoteDB.deleted_at.isnot(None)
        ).order_by(NoteDB.deleted_at.desc()).all()

    def get_all_trashed_items(self) -> list[TrashItem]:
        """Get all trashed items (channels and notes) as TrashItem models.

        Returns:
            List of TrashItem models
        """
        items = []

        # Get trashed channels
        for channel in self.get_trashed_channels():
            items.append(TrashItem(
                id=channel.id,
                type=TrashItemType.CHANNEL,
                name=channel.name,
                description=channel.description,
                deleted_at=channel.deleted_at,
                gemini_store_id=channel.gemini_store_id,
                file_count=channel.file_count,
                channel_id=None,
            ))

        # Get trashed notes
        for note in self.get_trashed_notes():
            items.append(TrashItem(
                id=note.id,
                type=TrashItemType.NOTE,
                name=note.title,
                description=note.content[:100] + "..." if len(note.content) > 100 else note.content,
                deleted_at=note.deleted_at,
                gemini_store_id=None,
                file_count=None,
                channel_id=note.channel_id,
            ))

        # Sort by deleted_at descending
        items.sort(key=lambda x: x.deleted_at, reverse=True)
        return items

    # ========== Restore Operations ==========

    def restore_channel(self, channel_id: int) -> ChannelMetadata | None:
        """Restore a soft-deleted channel.

        Args:
            channel_id: The channel ID (not gemini_store_id)

        Returns:
            Restored ChannelMetadata or None if not found
        """
        channel = self.db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id,
            ChannelMetadata.deleted_at.isnot(None),
        ).first()

        if channel:
            channel.deleted_at = None
            channel.last_accessed_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(channel)
        return channel

    def restore_note(self, note_id: int) -> NoteDB | None:
        """Restore a soft-deleted note.

        Args:
            note_id: The note ID

        Returns:
            Restored NoteDB or None if not found
        """
        note = self.db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.isnot(None),
        ).first()

        if note:
            note.deleted_at = None
            self.db.commit()
            self.db.refresh(note)
        return note

    # ========== Permanent Delete Operations ==========

    def permanent_delete_channel(self, channel_id: int) -> bool:
        """Permanently delete a trashed channel.

        Args:
            channel_id: The channel ID

        Returns:
            True if deleted, False if not found
        """
        channel = self.db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id,
            ChannelMetadata.deleted_at.isnot(None),
        ).first()

        if channel:
            self.db.delete(channel)
            self.db.commit()
            return True
        return False

    def permanent_delete_note(self, note_id: int) -> bool:
        """Permanently delete a trashed note.

        Args:
            note_id: The note ID

        Returns:
            True if deleted, False if not found
        """
        note = self.db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.isnot(None),
        ).first()

        if note:
            self.db.delete(note)
            self.db.commit()
            return True
        return False

    def empty_trash(self) -> tuple[int, int]:
        """Permanently delete all trashed items.

        Returns:
            Tuple of (deleted_channels_count, deleted_notes_count)
        """
        # Delete all trashed channels (cascade will delete related items)
        channel_count = self.db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None)
        ).delete()

        # Delete all trashed notes
        note_count = self.db.query(NoteDB).filter(
            NoteDB.deleted_at.isnot(None)
        ).delete()

        self.db.commit()
        return channel_count, note_count

    # ========== Auto Cleanup Operations ==========

    def cleanup_specific_channels(self, channel_ids: list[int]) -> int:
        """Permanently delete specific trashed channels by their IDs.

        This method is used when Gemini deletion succeeded for specific channels,
        ensuring we only delete from local DB what was successfully deleted from cloud.

        Args:
            channel_ids: List of channel IDs (primary keys) to delete

        Returns:
            Number of channels deleted
        """
        if not channel_ids:
            return 0

        deleted_count = self.db.query(ChannelMetadata).filter(
            ChannelMetadata.id.in_(channel_ids),
            ChannelMetadata.deleted_at.isnot(None),  # Must be in trash
        ).delete(synchronize_session=False)

        self.db.commit()
        return deleted_count

    def cleanup_expired_notes(self, retention_days: int | None = None) -> int:
        """Permanently delete trashed notes older than retention period.

        Notes are independent from Gemini (no cloud resources), so they can be
        deleted purely based on time-based expiration.

        Args:
            retention_days: Number of days to retain trashed items (default: 30)

        Returns:
            Number of notes deleted
        """
        if retention_days is None:
            retention_days = self.DEFAULT_RETENTION_DAYS

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        # Delete expired notes (no Gemini resources, safe to delete by time)
        note_count = self.db.query(NoteDB).filter(
            NoteDB.deleted_at.isnot(None),
            NoteDB.deleted_at < cutoff,
        ).delete()

        self.db.commit()
        return note_count

    def cleanup_expired_trash(self, retention_days: int | None = None) -> tuple[int, int]:
        """Permanently delete trashed items older than retention period.

        Args:
            retention_days: Number of days to retain trashed items (default: 30)

        Returns:
            Tuple of (deleted_channels_count, deleted_notes_count)
        """
        if retention_days is None:
            retention_days = self.DEFAULT_RETENTION_DAYS

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)

        # Delete expired channels
        channel_count = self.db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None),
            ChannelMetadata.deleted_at < cutoff,
        ).delete()

        # Delete expired notes
        note_count = self.db.query(NoteDB).filter(
            NoteDB.deleted_at.isnot(None),
            NoteDB.deleted_at < cutoff,
        ).delete()

        self.db.commit()
        return channel_count, note_count

    def get_trash_stats(self) -> dict:
        """Get statistics about trashed items.

        Returns:
            Dict with trash statistics
        """
        channel_count = self.db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None)
        ).count()

        note_count = self.db.query(NoteDB).filter(
            NoteDB.deleted_at.isnot(None)
        ).count()

        return {
            "trashed_channels": channel_count,
            "trashed_notes": note_count,
            "total": channel_count + note_count,
        }
