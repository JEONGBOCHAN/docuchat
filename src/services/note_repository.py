# -*- coding: utf-8 -*-
"""Repository for note database operations."""

import json
from sqlalchemy.orm import Session

from src.models.db_models import NoteDB, ChannelMetadata


class NoteRepository:
    """Repository for note operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(
        self,
        channel: ChannelMetadata,
        title: str,
        content: str,
        sources: list[dict] | None = None,
    ) -> NoteDB:
        """Create a new note.

        Args:
            channel: The channel metadata
            title: Note title
            content: Note content
            sources: List of source dicts (if from AI response)

        Returns:
            Created NoteDB
        """
        note = NoteDB(
            channel_id=channel.id,
            title=title,
            content=content,
            sources_json=json.dumps(sources or []),
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_by_id(self, note_id: int) -> NoteDB | None:
        """Get note by ID.

        Args:
            note_id: The note ID

        Returns:
            NoteDB or None (excludes soft-deleted notes)
        """
        return self.db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.is_(None),
        ).first()

    def get_by_channel(
        self, channel: ChannelMetadata, limit: int = 100, offset: int = 0
    ) -> list[NoteDB]:
        """Get notes for a channel.

        Args:
            channel: The channel metadata
            limit: Maximum number of notes
            offset: Number of notes to skip

        Returns:
            List of notes (excludes soft-deleted notes)
        """
        return (
            self.db.query(NoteDB)
            .filter(
                NoteDB.channel_id == channel.id,
                NoteDB.deleted_at.is_(None),
            )
            .order_by(NoteDB.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_by_channel(self, channel: ChannelMetadata) -> int:
        """Count notes in a channel.

        Args:
            channel: The channel metadata

        Returns:
            Number of notes (excludes soft-deleted notes)
        """
        return self.db.query(NoteDB).filter(
            NoteDB.channel_id == channel.id,
            NoteDB.deleted_at.is_(None),
        ).count()

    def update(
        self,
        note: NoteDB,
        title: str | None = None,
        content: str | None = None,
    ) -> NoteDB:
        """Update a note.

        Args:
            note: The note to update
            title: New title (if provided)
            content: New content (if provided)

        Returns:
            Updated NoteDB
        """
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete(self, note: NoteDB) -> bool:
        """Delete a note.

        Args:
            note: The note to delete

        Returns:
            True if deleted
        """
        self.db.delete(note)
        self.db.commit()
        return True

    def delete_by_channel(self, channel: ChannelMetadata) -> int:
        """Delete all notes in a channel.

        Args:
            channel: The channel metadata

        Returns:
            Number of deleted notes
        """
        count = (
            self.db.query(NoteDB).filter(NoteDB.channel_id == channel.id).delete()
        )
        self.db.commit()
        return count
