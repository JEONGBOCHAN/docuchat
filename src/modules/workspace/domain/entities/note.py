# -*- coding: utf-8 -*-
"""
Note Domain Entity.

Pure Python representation of a note with business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.modules.workspace.domain.exceptions import NoteTitleError, NoteContentError


# Validation constants
MAX_TITLE_LENGTH = 200
MAX_CONTENT_LENGTH = 100_000  # 100KB of text


@dataclass
class NoteSource:
    """A source reference in a note.

    Attributes:
        source: Source document name or identifier
        content: Excerpt or summary from the source
        page: Optional page number
    """

    source: str
    content: str
    page: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"source": self.source, "content": self.content}
        if self.page is not None:
            result["page"] = self.page
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoteSource":
        """Create from dictionary."""
        return cls(
            source=data.get("source", ""),
            content=data.get("content", ""),
            page=data.get("page"),
        )


@dataclass
class Note:
    """A note entity representing user-created content.

    A note is a piece of content created from research or analysis
    of documents in a channel. It can include citations/sources.

    Attributes:
        id: Unique note identifier
        channel_id: The channel this note belongs to
        title: Note title
        content: Note content (markdown supported)
        sources: List of source references
        created_at: When the note was created
        updated_at: When the note was last modified
        is_deleted: Soft delete flag
        deleted_at: When the note was deleted
    """

    id: int | None
    channel_id: int
    title: str
    content: str
    sources: list[NoteSource] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate note after initialization."""
        self._validate_title(self.title)
        self._validate_content(self.content)

    # =========================================================================
    # Validation Methods
    # =========================================================================

    @staticmethod
    def _validate_title(title: str) -> None:
        """Validate note title.

        Args:
            title: Title to validate

        Raises:
            NoteTitleError: If title is invalid
        """
        if not title or not title.strip():
            raise NoteTitleError("Note title cannot be empty")
        if len(title) > MAX_TITLE_LENGTH:
            raise NoteTitleError(
                f"Note title cannot exceed {MAX_TITLE_LENGTH} characters"
            )

    @staticmethod
    def _validate_content(content: str) -> None:
        """Validate note content.

        Args:
            content: Content to validate

        Raises:
            NoteContentError: If content is invalid
        """
        if len(content) > MAX_CONTENT_LENGTH:
            raise NoteContentError(
                f"Note content cannot exceed {MAX_CONTENT_LENGTH} characters"
            )

    # =========================================================================
    # Business Methods
    # =========================================================================

    def update_title(self, new_title: str) -> None:
        """Update note title.

        Args:
            new_title: New title for the note

        Raises:
            NoteTitleError: If new title is invalid
        """
        self._validate_title(new_title)
        self.title = new_title.strip()
        self._touch()

    def update_content(self, new_content: str) -> None:
        """Update note content.

        Args:
            new_content: New content for the note

        Raises:
            NoteContentError: If new content is invalid
        """
        self._validate_content(new_content)
        self.content = new_content
        self._touch()

    def add_source(self, source: NoteSource) -> None:
        """Add a source reference to the note.

        Args:
            source: Source to add
        """
        self.sources.append(source)
        self._touch()

    def remove_source(self, source_name: str) -> bool:
        """Remove a source reference by name.

        Args:
            source_name: Name of the source to remove

        Returns:
            True if source was removed, False if not found
        """
        original_count = len(self.sources)
        self.sources = [s for s in self.sources if s.source != source_name]
        if len(self.sources) < original_count:
            self._touch()
            return True
        return False

    def clear_sources(self) -> None:
        """Remove all sources from the note."""
        if self.sources:
            self.sources = []
            self._touch()

    def soft_delete(self) -> None:
        """Mark the note as deleted (soft delete)."""
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = datetime.now()

    def restore(self) -> None:
        """Restore a soft-deleted note."""
        if self.is_deleted:
            self.is_deleted = False
            self.deleted_at = None
            self._touch()

    def _touch(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()

    # =========================================================================
    # Query Methods
    # =========================================================================

    def has_sources(self) -> bool:
        """Check if note has any sources."""
        return len(self.sources) > 0

    def source_count(self) -> int:
        """Get the number of sources."""
        return len(self.sources)

    def get_source_names(self) -> list[str]:
        """Get list of source names."""
        return [s.source for s in self.sources]

    def word_count(self) -> int:
        """Get approximate word count of content."""
        return len(self.content.split())

    def is_empty(self) -> bool:
        """Check if note content is effectively empty."""
        return not self.content.strip()

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def create(
        cls,
        channel_id: int,
        title: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> "Note":
        """Create a new note with validation.

        Args:
            channel_id: Channel ID
            title: Note title
            content: Note content
            sources: Optional list of source dictionaries

        Returns:
            New Note instance

        Raises:
            NoteTitleError: If title is invalid
            NoteContentError: If content is invalid
        """
        note_sources = []
        if sources:
            note_sources = [NoteSource.from_dict(s) for s in sources]

        return cls(
            id=None,
            channel_id=channel_id,
            title=title.strip(),
            content=content,
            sources=note_sources,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert note to dictionary.

        Returns:
            Dictionary representation of the note
        """
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "title": self.title,
            "content": self.content,
            "sources": [s.to_dict() for s in self.sources],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }
