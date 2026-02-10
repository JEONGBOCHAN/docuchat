# -*- coding: utf-8 -*-
"""
Note CRUD use case.

Extracts note orchestration logic from the API router into the application layer.
Handles channel validation + note CRUD operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.persistence import (
    ChannelRepositoryPort,
    NoteRepositoryPort,
    TrashRepositoryPort,
)
from src.domain.entities.note import Note
from src.domain.exceptions import NoteValidationError as DomainNoteValidationError
from src.shared.kernel.contracts.errors.use_case_errors import ChannelNotFoundError, NoteValidationError


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class NoteDetailDTO:
    """Application-layer DTO for note details."""

    id: int
    channel_id: str  # gemini_store_id
    title: str
    content: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


@dataclass
class NoteListResultDTO:
    """Result of listing notes."""

    notes: list[NoteDetailDTO] = field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class NoteCrudUseCase:
    """Orchestrates note CRUD operations with channel validation."""

    def __init__(
        self,
        channel_port: ChannelPort,
        channel_repo: ChannelRepositoryPort,
        note_repo: NoteRepositoryPort,
        trash_repo: TrashRepositoryPort,
    ):
        self._channel_port = channel_port
        self._channel_repo = channel_repo
        self._note_repo = note_repo
        self._trash_repo = trash_repo

    def _resolve_channel(self, channel_id: str) -> int:
        """Resolve gemini_store_id to DB primary key.

        Auto-creates channel metadata if missing.

        Raises:
            ChannelNotFoundError: If channel doesn't exist in external service.
        """
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            raise ChannelNotFoundError(channel_id)

        meta = self._channel_repo.get_by_gemini_id(channel_id)
        if not meta:
            meta = self._channel_repo.create(
                gemini_store_id=channel_id,
                name=channel.display_name or "unknown",
            )
        return meta.id

    def _to_dto(self, note_dto, channel_id: str) -> NoteDetailDTO:
        """Convert persistence NoteDTO to application NoteDetailDTO."""
        return NoteDetailDTO(
            id=note_dto.id,
            channel_id=channel_id,
            title=note_dto.title,
            content=note_dto.content,
            sources=note_dto.sources,
            created_at=note_dto.created_at,
            updated_at=note_dto.updated_at,
        )

    # -- Create ---------------------------------------------------------------

    def create(
        self,
        channel_id: str,
        title: str,
        content: str,
        sources: list[dict[str, Any]],
    ) -> NoteDetailDTO:
        """Create a new note in a channel.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
            NoteValidationError: If title/content violates domain rules.
        """
        db_channel_id = self._resolve_channel(channel_id)

        # Domain validation via Note entity
        try:
            Note.create(
                channel_id=db_channel_id,
                title=title,
                content=content,
                sources=sources,
            )
        except DomainNoteValidationError as e:
            raise NoteValidationError(str(e)) from e

        note = self._note_repo.create(
            channel_id=db_channel_id,
            title=title,
            content=content,
            sources=sources,
        )
        return self._to_dto(note, channel_id)

    # -- List -----------------------------------------------------------------

    def list(
        self,
        channel_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> NoteListResultDTO:
        """List notes in a channel.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
        """
        db_channel_id = self._resolve_channel(channel_id)

        notes = self._note_repo.get_by_channel(db_channel_id, limit=limit, offset=offset)
        total = self._note_repo.count_by_channel(db_channel_id)

        return NoteListResultDTO(
            notes=[self._to_dto(n, channel_id) for n in notes],
            total=total,
        )

    # -- Get ------------------------------------------------------------------

    def get(self, channel_id: str, note_id: int) -> NoteDetailDTO | None:
        """Get a single note. Returns None if note not found or not in channel.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
        """
        db_channel_id = self._resolve_channel(channel_id)

        note = self._note_repo.get_by_id(note_id)
        if not note or note.channel_id != db_channel_id:
            return None

        return self._to_dto(note, channel_id)

    # -- Update ---------------------------------------------------------------

    def update(
        self,
        channel_id: str,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> NoteDetailDTO | None:
        """Update a note. Returns None if note not found.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
            NoteValidationError: If title/content violates domain rules.
        """
        db_channel_id = self._resolve_channel(channel_id)

        note = self._note_repo.get_by_id(note_id)
        if not note or note.channel_id != db_channel_id:
            return None

        # Domain validation for updated fields
        try:
            if title is not None:
                Note._validate_title(title)
            if content is not None:
                Note._validate_content(content)
        except DomainNoteValidationError as e:
            raise NoteValidationError(str(e)) from e

        updated = self._note_repo.update(note_id, title=title, content=content)
        return self._to_dto(updated, channel_id)

    # -- Delete ---------------------------------------------------------------

    def delete(self, channel_id: str, note_id: int) -> bool:
        """Soft-delete a note (move to trash). Returns False if not found.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
        """
        db_channel_id = self._resolve_channel(channel_id)

        note = self._note_repo.get_by_id(note_id)
        if not note or note.channel_id != db_channel_id:
            return False

        self._trash_repo.soft_delete_note(note_id)
        return True
