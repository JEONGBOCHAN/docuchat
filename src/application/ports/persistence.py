# -*- coding: utf-8 -*-
"""Persistence ports (Repository abstractions).

These ports define abstract interfaces for data persistence operations.
They allow the application layer to work with data without knowing
about the specific database or ORM implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


# =============================================================================
# Data Transfer Objects (DTOs)
# =============================================================================

@dataclass
class ChannelMetadataDTO:
    """DTO for channel metadata."""

    id: int
    gemini_store_id: str
    name: str
    description: str | None
    created_at: datetime
    last_accessed_at: datetime
    file_count: int
    total_size_bytes: int
    is_deleted: bool
    deleted_at: datetime | None


@dataclass
class ChatMessageDTO:
    """DTO for chat message."""

    id: int
    channel_id: int
    session_id: int | None
    role: str
    content: str
    sources: list[dict[str, Any]]
    created_at: datetime


@dataclass
class ChatSessionDTO:
    """DTO for chat session."""

    id: int
    session_id: str
    channel_id: int
    channel_gemini_store_id: str  # For convenience
    context_window: int
    created_at: datetime
    last_activity_at: datetime


@dataclass
class NoteDTO:
    """DTO for note."""

    id: int
    channel_id: int
    title: str
    content: str
    sources: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime | None
    is_deleted: bool
    deleted_at: datetime | None


@dataclass
class FavoriteDTO:
    """DTO for favorite."""

    id: int
    target_type: str
    target_id: str
    display_order: int
    created_at: datetime


@dataclass
class SearchHistoryDTO:
    """DTO for search history."""

    id: int
    channel_id: int
    query: str
    search_count: int
    created_at: datetime
    last_searched_at: datetime


@dataclass
class TrashItemDTO:
    """DTO for trash item."""

    id: int
    type: str  # 'channel' or 'note'
    name: str
    deleted_at: datetime
    days_until_permanent_deletion: int


@dataclass
class AudioOverviewDTO:
    """DTO for audio overview."""

    id: int
    audio_id: str
    channel_id: int
    title: str | None
    status: str
    language: str
    style: str
    script_json: str | None
    audio_path: str | None
    audio_duration_seconds: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


# =============================================================================
# Port Interfaces
# =============================================================================

class ChannelRepositoryPort(ABC):
    """Port for channel metadata repository operations."""

    @abstractmethod
    def create(
        self,
        gemini_store_id: str,
        name: str,
        description: str | None = None,
    ) -> ChannelMetadataDTO:
        """Create a new channel metadata record."""
        ...

    @abstractmethod
    def get_by_gemini_id(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        """Get channel by Gemini store ID."""
        ...

    @abstractmethod
    def get_all(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChannelMetadataDTO]:
        """Get all channels with optional pagination."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Get total count of channels."""
        ...

    @abstractmethod
    def touch(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        """Update last accessed time for a channel."""
        ...

    @abstractmethod
    def update_stats(
        self,
        gemini_store_id: str,
        file_count: int | None = None,
        total_size_bytes: int | None = None,
    ) -> ChannelMetadataDTO | None:
        """Update channel statistics."""
        ...

    @abstractmethod
    def update(
        self,
        gemini_store_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> ChannelMetadataDTO | None:
        """Update channel metadata."""
        ...

    @abstractmethod
    def delete(self, gemini_store_id: str) -> bool:
        """Delete channel metadata."""
        ...

    @abstractmethod
    def get_inactive_channels(self, inactive_days: int) -> list[ChannelMetadataDTO]:
        """Get channels that haven't been accessed for specified days."""
        ...

    @abstractmethod
    def get_deleted_store_ids(self) -> set[str]:
        """Get all soft-deleted channel Gemini store IDs."""
        ...


class ChatHistoryRepositoryPort(ABC):
    """Port for chat history repository operations."""

    @abstractmethod
    def add_message(
        self,
        channel_id: int,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        session_id: str | None = None,
    ) -> ChatMessageDTO:
        """Add a chat message."""
        ...

    @abstractmethod
    def get_history(
        self,
        channel_id: int,
        limit: int = 100,
    ) -> list[ChatMessageDTO]:
        """Get chat history for a channel."""
        ...

    @abstractmethod
    def get_session_history(
        self,
        session_id: str,
        limit: int | None = None,
        context_window: int | None = None,
    ) -> list[ChatMessageDTO]:
        """Get chat history for a specific session."""
        ...

    @abstractmethod
    def clear_history(self, channel_id: int) -> int:
        """Clear chat history for a channel."""
        ...


class ChatSessionRepositoryPort(ABC):
    """Port for chat session repository operations."""

    @abstractmethod
    def create(
        self,
        channel_id: int,
        context_window: int = 10,
    ) -> ChatSessionDTO:
        """Create a new chat session."""
        ...

    @abstractmethod
    def get_by_session_id(self, session_id: str) -> ChatSessionDTO | None:
        """Get session by session ID."""
        ...

    @abstractmethod
    def get_or_create(
        self,
        channel_id: int,
        session_id: str | None = None,
        context_window: int = 10,
    ) -> tuple[ChatSessionDTO, bool]:
        """Get existing session or create a new one."""
        ...

    @abstractmethod
    def touch(self, session_id: str) -> ChatSessionDTO | None:
        """Update last activity time for a session."""
        ...

    @abstractmethod
    def is_expired(self, session_id: str) -> bool:
        """Check if a session has expired."""
        ...

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        ...

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Delete all expired sessions."""
        ...


class NoteRepositoryPort(ABC):
    """Port for note repository operations."""

    @abstractmethod
    def create(
        self,
        channel_id: int,
        title: str,
        content: str,
        sources: list[dict[str, Any]],
    ) -> NoteDTO:
        """Create a new note."""
        ...

    @abstractmethod
    def get_by_id(self, note_id: int) -> NoteDTO | None:
        """Get a note by ID."""
        ...

    @abstractmethod
    def get_by_channel(
        self,
        channel_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NoteDTO]:
        """Get notes for a channel."""
        ...

    @abstractmethod
    def count_by_channel(self, channel_id: int) -> int:
        """Count notes for a channel."""
        ...

    @abstractmethod
    def update(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> NoteDTO | None:
        """Update a note."""
        ...

    @abstractmethod
    def delete(self, note_id: int) -> bool:
        """Hard delete a note."""
        ...


class FavoriteRepositoryPort(ABC):
    """Port for favorite repository operations."""

    @abstractmethod
    def add(self, target_type: str, target_id: str) -> FavoriteDTO:
        """Add a favorite."""
        ...

    @abstractmethod
    def remove(self, target_type: str, target_id: str) -> bool:
        """Remove a favorite."""
        ...

    @abstractmethod
    def is_favorited(self, target_type: str, target_id: str) -> bool:
        """Check if an item is favorited."""
        ...

    @abstractmethod
    def get_favorited_ids(self, target_type: str) -> set[str]:
        """Get all favorited IDs for a target type."""
        ...

    @abstractmethod
    def get_all(self, target_type: str | None = None) -> list[FavoriteDTO]:
        """Get all favorites, optionally filtered by type."""
        ...

    @abstractmethod
    def list_all(
        self,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FavoriteDTO]:
        """Get favorites with pagination."""
        ...

    @abstractmethod
    def count(self, target_type: str | None = None) -> int:
        """Count favorites, optionally filtered by type."""
        ...

    @abstractmethod
    def reorder(self, favorite_ids: list[int]) -> None:
        """Reorder favorites by their IDs."""
        ...


class SearchHistoryRepositoryPort(ABC):
    """Port for search history repository operations."""

    @abstractmethod
    def add_or_update(self, channel_id: int, query: str) -> SearchHistoryDTO:
        """Add or update a search query."""
        ...

    @abstractmethod
    def get_recent(
        self,
        channel_id: int,
        limit: int = 10,
    ) -> list[SearchHistoryDTO]:
        """Get recent search queries for a channel."""
        ...

    @abstractmethod
    def get_history(
        self,
        channel_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchHistoryDTO]:
        """Get search history for a channel with pagination."""
        ...

    @abstractmethod
    def count_history(self, channel_id: int) -> int:
        """Count search history entries for a channel."""
        ...

    @abstractmethod
    def get_suggestions(
        self,
        channel_id: int,
        prefix: str,
        limit: int = 10,
    ) -> list[SearchHistoryDTO]:
        """Get search suggestions based on query prefix."""
        ...

    @abstractmethod
    def get_popular(
        self,
        channel_id: int,
        limit: int = 10,
    ) -> list[SearchHistoryDTO]:
        """Get popular searches for a channel."""
        ...

    @abstractmethod
    def get_by_id(self, history_id: int) -> SearchHistoryDTO | None:
        """Get search history entry by ID."""
        ...

    @abstractmethod
    def delete(self, history_id: int) -> bool:
        """Delete a search history entry."""
        ...

    @abstractmethod
    def clear_for_channel(self, channel_id: int) -> int:
        """Clear search history for a channel."""
        ...

    @abstractmethod
    def clear_channel_history(self, channel_id: int) -> int:
        """Clear all search history for a channel (alias for clear_for_channel)."""
        ...


class TrashRepositoryPort(ABC):
    """Port for trash repository operations."""

    @abstractmethod
    def soft_delete_channel(self, channel_id: int) -> bool:
        """Soft delete a channel (move to trash)."""
        ...

    @abstractmethod
    def soft_delete_note(self, note_id: int) -> bool:
        """Soft delete a note (move to trash)."""
        ...

    @abstractmethod
    def restore_channel(self, channel_id: int) -> ChannelMetadataDTO | None:
        """Restore a channel from trash."""
        ...

    @abstractmethod
    def restore_note(self, note_id: int) -> NoteDTO | None:
        """Restore a note from trash."""
        ...

    @abstractmethod
    def permanent_delete_channel(self, channel_id: int) -> bool:
        """Permanently delete a channel."""
        ...

    @abstractmethod
    def permanent_delete_note(self, note_id: int) -> bool:
        """Permanently delete a note."""
        ...

    @abstractmethod
    def get_all_trashed_items(self) -> list[TrashItemDTO]:
        """Get all items in trash."""
        ...

    @abstractmethod
    def empty_trash(self) -> tuple[int, int]:
        """Empty the trash (delete all). Returns (channels_deleted, notes_deleted)."""
        ...

    @abstractmethod
    def get_trash_stats(self) -> dict[str, Any]:
        """Get trash statistics."""
        ...

    @abstractmethod
    def get_trashed_channel_by_db_id(self, db_id: int) -> ChannelMetadataDTO | None:
        """Get a trashed channel by its database ID."""
        ...

    @abstractmethod
    def get_all_trashed_channels(self) -> list[ChannelMetadataDTO]:
        """Get all trashed channels."""
        ...


class AudioRepositoryPort(ABC):
    """Port for audio overview repository operations."""

    @abstractmethod
    def create_audio_overview(
        self,
        channel_id: int,
        language: str,
        style: str,
    ) -> AudioOverviewDTO:
        """Create a new audio overview record."""
        ...

    @abstractmethod
    def get_audio_by_id(self, audio_id: str) -> AudioOverviewDTO | None:
        """Get audio overview by audio_id."""
        ...

    @abstractmethod
    def get_audios_by_channel(
        self,
        channel_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AudioOverviewDTO]:
        """Get audio overviews for a channel."""
        ...

    @abstractmethod
    def count_audios_by_channel(self, channel_id: int) -> int:
        """Count audio overviews for a channel."""
        ...

    @abstractmethod
    def update_status(
        self,
        audio_id: str,
        status: str,
        error_message: str | None = None,
    ) -> AudioOverviewDTO | None:
        """Update audio status."""
        ...

    @abstractmethod
    def update_script(self, audio_id: str, script_json: str) -> AudioOverviewDTO | None:
        """Update audio script."""
        ...

    @abstractmethod
    def update_audio_complete(
        self,
        audio_id: str,
        audio_path: str,
        duration_seconds: int,
    ) -> AudioOverviewDTO | None:
        """Mark audio as complete with path and duration."""
        ...

    @abstractmethod
    def delete_audio(self, audio_id: str) -> bool:
        """Delete an audio overview."""
        ...

    @abstractmethod
    def get_channel_by_store_id(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        """Get channel by Gemini store ID (convenience method)."""
        ...
