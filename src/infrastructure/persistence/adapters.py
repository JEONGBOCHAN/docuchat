# -*- coding: utf-8 -*-
"""Repository adapters that implement application ports.

These adapters wrap the existing repository implementations and convert
between SQLAlchemy models and application DTOs.
"""

import json
from datetime import datetime, UTC

from src.application.ports.persistence import (
    ChannelMetadataDTO,
    ChatMessageDTO,
    ChatSessionDTO,
    NoteDTO,
    FavoriteDTO,
    SearchHistoryDTO,
    TrashItemDTO,
    AudioOverviewDTO,
    DocumentPreviewCacheDTO,
    ChannelRepositoryPort,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    NoteRepositoryPort,
    FavoriteRepositoryPort,
    SearchHistoryRepositoryPort,
    TrashRepositoryPort,
    AudioRepositoryPort,
    DocumentPreviewCacheRepositoryPort,
)
from src.models.db_models import ChannelMetadata, ChatMessageDB, ChatSessionDB, NoteDB, DocumentPreviewCacheDB


# =============================================================================
# Model to DTO Converters
# =============================================================================

def _channel_to_dto(channel: ChannelMetadata) -> ChannelMetadataDTO:
    """Convert ChannelMetadata model to DTO."""
    return ChannelMetadataDTO(
        id=channel.id,
        gemini_store_id=channel.gemini_store_id,
        name=channel.name,
        description=channel.description,
        created_at=channel.created_at,
        last_accessed_at=channel.last_accessed_at,
        file_count=channel.file_count,
        total_size_bytes=channel.total_size_bytes,
        is_deleted=channel.is_deleted,
        deleted_at=channel.deleted_at,
    )


def _chat_message_to_dto(msg: ChatMessageDB) -> ChatMessageDTO:
    """Convert ChatMessageDB model to DTO."""
    return ChatMessageDTO(
        id=msg.id,
        channel_id=msg.channel_id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        sources=json.loads(msg.sources_json) if msg.sources_json else [],
        created_at=msg.created_at,
    )


def _chat_session_to_dto(session: ChatSessionDB) -> ChatSessionDTO:
    """Convert ChatSessionDB model to DTO."""
    return ChatSessionDTO(
        id=session.id,
        session_id=session.session_id,
        channel_id=session.channel_id,
        channel_gemini_store_id=session.channel.gemini_store_id if session.channel else "",
        context_window=session.context_window,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
    )


def _note_to_dto(note: NoteDB) -> NoteDTO:
    """Convert NoteDB model to DTO."""
    return NoteDTO(
        id=note.id,
        channel_id=note.channel_id,
        title=note.title,
        content=note.content,
        sources=json.loads(note.sources_json) if note.sources_json else [],
        created_at=note.created_at,
        updated_at=note.updated_at,
        is_deleted=note.is_deleted if hasattr(note, 'is_deleted') else False,
        deleted_at=note.deleted_at if hasattr(note, 'deleted_at') else None,
    )


# =============================================================================
# Channel Repository Adapter
# =============================================================================

class ChannelRepositoryAdapter(ChannelRepositoryPort):
    """Adapter that implements ChannelRepositoryPort using existing repository."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.channel_repository import ChannelRepository
        self._db = db
        self._repo = ChannelRepository(self._db)

    def create(
        self,
        gemini_store_id: str,
        name: str,
        description: str | None = None,
    ) -> ChannelMetadataDTO:
        channel = self._repo.create(gemini_store_id, name, description)
        return _channel_to_dto(channel)

    def get_by_gemini_id(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        channel = self._repo.get_by_gemini_id(gemini_store_id)
        return _channel_to_dto(channel) if channel else None

    def get_all(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChannelMetadataDTO]:
        channels = self._repo.get_all(limit, offset)
        return [_channel_to_dto(c) for c in channels]

    def count(self) -> int:
        return self._repo.count()

    def touch(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        channel = self._repo.touch(gemini_store_id)
        return _channel_to_dto(channel) if channel else None

    def update_stats(
        self,
        gemini_store_id: str,
        file_count: int | None = None,
        total_size_bytes: int | None = None,
    ) -> ChannelMetadataDTO | None:
        channel = self._repo.update_stats(gemini_store_id, file_count, total_size_bytes)
        return _channel_to_dto(channel) if channel else None

    def update(
        self,
        gemini_store_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> ChannelMetadataDTO | None:
        channel = self._repo.update(gemini_store_id, name, description)
        return _channel_to_dto(channel) if channel else None

    def delete(self, gemini_store_id: str) -> bool:
        return self._repo.delete(gemini_store_id)

    def get_inactive_channels(self, inactive_days: int) -> list[ChannelMetadataDTO]:
        channels = self._repo.get_inactive_channels(inactive_days)
        return [_channel_to_dto(c) for c in channels]

    def get_deleted_store_ids(self) -> set[str]:
        return self._repo.get_deleted_store_ids()


# =============================================================================
# Chat History Repository Adapter
# =============================================================================

class ChatHistoryRepositoryAdapter(ChatHistoryRepositoryPort):
    """Adapter that implements ChatHistoryRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.channel_repository import ChatHistoryRepository
        self._db = db
        self._repo = ChatHistoryRepository(self._db)

    def add_message(
        self,
        channel_id: int,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        session_id: str | None = None,
    ) -> ChatMessageDTO:
        # Get channel object for the repository
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        session = None
        if session_id:
            # Query by session_id string (e.g. "sess_xxx"), not the integer id
            session = self._db.query(ChatSessionDB).filter(
                ChatSessionDB.session_id == session_id
            ).first()

        msg = self._repo.add_message(channel, role, content, sources, session)
        return _chat_message_to_dto(msg)

    def get_history(
        self,
        channel_id: int,
        limit: int = 100,
    ) -> list[ChatMessageDTO]:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        if not channel:
            return []

        messages = self._repo.get_history(channel, limit)
        return [_chat_message_to_dto(m) for m in messages]

    def get_session_history(
        self,
        session_id: str,
        limit: int | None = None,
        context_window: int | None = None,
    ) -> list[ChatMessageDTO]:
        # Query by session_id string (e.g. "sess_xxx"), not the integer id
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()

        if not session:
            return []

        messages = self._repo.get_session_history(session, limit)
        return [_chat_message_to_dto(m) for m in messages]

    def clear_history(self, channel_id: int) -> int:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        if not channel:
            return 0

        return self._repo.clear_history(channel)


# =============================================================================
# Chat Session Repository Adapter
# =============================================================================

class ChatSessionRepositoryAdapter(ChatSessionRepositoryPort):
    """Adapter that implements ChatSessionRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.channel_repository import ChatSessionRepository
        self._db = db
        self._repo = ChatSessionRepository(self._db)

    def create(
        self,
        channel_id: int,
        context_window: int = 10,
    ) -> ChatSessionDTO:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        session = self._repo.create(channel, context_window)
        return _chat_session_to_dto(session)

    def get_by_session_id(self, session_id: str) -> ChatSessionDTO | None:
        session = self._repo.get_by_session_id(session_id)
        return _chat_session_to_dto(session) if session else None

    def get_or_create(
        self,
        channel_id: int,
        session_id: str | None = None,
        context_window: int = 10,
    ) -> tuple[ChatSessionDTO, bool]:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        session, created = self._repo.get_or_create(channel, session_id, context_window)
        return _chat_session_to_dto(session), created

    def touch(self, session_id: str) -> ChatSessionDTO | None:
        session = self._repo.get_by_session_id(session_id)
        if session:
            session = self._repo.touch(session)
            return _chat_session_to_dto(session)
        return None

    def is_expired(self, session_id: str) -> bool:
        session = self._repo.get_by_session_id(session_id)
        if session:
            return self._repo.is_expired(session)
        return True

    def delete(self, session_id: str) -> bool:
        return self._repo.delete(session_id)

    def cleanup_expired(self) -> int:
        return self._repo.cleanup_expired()


# =============================================================================
# Note Repository Adapter
# =============================================================================

class NoteRepositoryAdapter(NoteRepositoryPort):
    """Adapter that implements NoteRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.note_repository import NoteRepository
        self._db = db
        self._repo = NoteRepository(self._db)

    def create(
        self,
        channel_id: int,
        title: str,
        content: str,
        sources: list[dict],
    ) -> NoteDTO:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        note = self._repo.create(channel, title, content, sources)
        return _note_to_dto(note)

    def get_by_id(self, note_id: int) -> NoteDTO | None:
        note = self._repo.get_by_id(note_id)
        return _note_to_dto(note) if note else None

    def get_by_channel(
        self,
        channel_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NoteDTO]:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        if not channel:
            return []

        notes = self._repo.get_by_channel(channel, limit, offset)
        return [_note_to_dto(n) for n in notes]

    def count_by_channel(self, channel_id: int) -> int:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        if not channel:
            return 0

        return self._repo.count_by_channel(channel)

    def update(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> NoteDTO | None:
        note = self._repo.get_by_id(note_id)
        if note:
            updated = self._repo.update(note, title, content)
            return _note_to_dto(updated)
        return None

    def delete(self, note_id: int) -> bool:
        note = self._repo.get_by_id(note_id)
        if note:
            self._repo.delete(note)
            return True
        return False


# =============================================================================
# Favorite Repository Adapter
# =============================================================================

class FavoriteRepositoryAdapter(FavoriteRepositoryPort):
    """Adapter that implements FavoriteRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.favorite_repository import FavoriteRepository
        from src.domain.value_objects import TargetType
        self._db = db
        self._repo = FavoriteRepository(self._db)
        self._TargetType = TargetType

    def _str_to_target_type(self, target_type: str):
        """Convert string to TargetType enum."""
        return self._TargetType(target_type)

    def add(self, target_type: str, target_id: str) -> FavoriteDTO:
        fav = self._repo.add(self._str_to_target_type(target_type), target_id)
        return FavoriteDTO(
            id=fav.id,
            target_type=fav.target_type,  # Already a string, no .value needed
            target_id=fav.target_id,
            display_order=fav.display_order,
            created_at=fav.created_at,
        )

    def remove(self, target_type: str, target_id: str) -> bool:
        return self._repo.remove(self._str_to_target_type(target_type), target_id)

    def is_favorited(self, target_type: str, target_id: str) -> bool:
        return self._repo.is_favorited(self._str_to_target_type(target_type), target_id)

    def get_favorited_ids(self, target_type: str) -> set[str]:
        return self._repo.get_favorited_ids(self._str_to_target_type(target_type))

    def get_all(self, target_type: str | None = None) -> list[FavoriteDTO]:
        tt = self._str_to_target_type(target_type) if target_type else None
        favorites = self._repo.get_all(tt)
        return [
            FavoriteDTO(
                id=f.id,
                target_type=f.target_type,  # Already a string, no .value needed
                target_id=f.target_id,
                display_order=f.display_order,
                created_at=f.created_at,
            )
            for f in favorites
        ]

    def list_all(
        self,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FavoriteDTO]:
        tt = self._str_to_target_type(target_type) if target_type else None
        favorites = self._repo.list_all(tt, limit=limit, offset=offset)
        return [
            FavoriteDTO(
                id=f.id,
                target_type=f.target_type,
                target_id=f.target_id,
                display_order=f.display_order,
                created_at=f.created_at,
            )
            for f in favorites
        ]

    def count(self, target_type: str | None = None) -> int:
        tt = self._str_to_target_type(target_type) if target_type else None
        return self._repo.count(tt)

    def reorder(self, favorite_ids: list[int]) -> None:
        self._repo.reorder(favorite_ids)


# =============================================================================
# Search History Repository Adapter
# =============================================================================

class SearchHistoryRepositoryAdapter(SearchHistoryRepositoryPort):
    """Adapter that implements SearchHistoryRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.search_repository import SearchHistoryRepository
        self._db = db
        self._repo = SearchHistoryRepository(self._db)

    def _to_dto(self, entry) -> SearchHistoryDTO:
        """Convert SearchHistoryDB to DTO."""
        return SearchHistoryDTO(
            id=entry.id,
            channel_id=entry.channel_id,
            query=entry.query,
            search_count=entry.search_count,
            created_at=entry.created_at,
            last_searched_at=entry.last_searched_at,
        )

    def _get_channel(self, channel_id: int):
        """Get channel by database ID."""
        return self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

    def add_or_update(self, channel_id: int, query: str) -> SearchHistoryDTO:
        channel = self._get_channel(channel_id)
        entry = self._repo.add_or_update(channel, query)
        return self._to_dto(entry)

    def get_recent(
        self,
        channel_id: int,
        limit: int = 10,
    ) -> list[SearchHistoryDTO]:
        channel = self._get_channel(channel_id)
        if not channel:
            return []
        entries = self._repo.get_recent(channel, limit)
        return [self._to_dto(e) for e in entries]

    def get_history(
        self,
        channel_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchHistoryDTO]:
        channel = self._get_channel(channel_id)
        if not channel:
            return []
        entries = self._repo.get_history(channel, limit, offset)
        return [self._to_dto(e) for e in entries]

    def count_history(self, channel_id: int) -> int:
        channel = self._get_channel(channel_id)
        if not channel:
            return 0
        return self._repo.count_history(channel)

    def get_suggestions(
        self,
        channel_id: int,
        prefix: str,
        limit: int = 10,
    ) -> list[SearchHistoryDTO]:
        channel = self._get_channel(channel_id)
        if not channel:
            return []
        entries = self._repo.get_suggestions(channel, prefix, limit)
        return [self._to_dto(e) for e in entries]

    def get_popular(
        self,
        channel_id: int,
        limit: int = 10,
    ) -> list[SearchHistoryDTO]:
        channel = self._get_channel(channel_id)
        if not channel:
            return []
        entries = self._repo.get_popular(channel, limit)
        return [self._to_dto(e) for e in entries]

    def get_by_id(self, history_id: int) -> SearchHistoryDTO | None:
        entry = self._repo.get_by_id(history_id)
        return self._to_dto(entry) if entry else None

    def delete(self, history_id: int) -> bool:
        entry = self._repo.get_by_id(history_id)
        if entry:
            return self._repo.delete(entry)
        return False

    def clear_for_channel(self, channel_id: int) -> int:
        channel = self._get_channel(channel_id)
        if not channel:
            return 0
        return self._repo.clear_channel_history(channel)

    def clear_channel_history(self, channel_id: int) -> int:
        """Alias for clear_for_channel."""
        return self.clear_for_channel(channel_id)


# =============================================================================
# Trash Repository Adapter
# =============================================================================

class TrashRepositoryAdapter(TrashRepositoryPort):
    """Adapter that implements TrashRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.trash_repository import TrashRepository
        self._db = db
        self._repo = TrashRepository(self._db)

    def soft_delete_channel(self, channel_id: int) -> bool:
        return self._repo.soft_delete_channel(channel_id) is not None

    def soft_delete_note(self, note_id: int) -> bool:
        return self._repo.soft_delete_note(note_id) is not None

    def restore_channel(self, channel_id: int) -> ChannelMetadataDTO | None:
        channel = self._repo.restore_channel(channel_id)
        return _channel_to_dto(channel) if channel else None

    def restore_note(self, note_id: int) -> NoteDTO | None:
        note = self._repo.restore_note(note_id)
        return _note_to_dto(note) if note else None

    def permanent_delete_channel(self, channel_id: int) -> bool:
        return self._repo.permanent_delete_channel(channel_id)

    def permanent_delete_note(self, note_id: int) -> bool:
        return self._repo.permanent_delete_note(note_id)

    def get_all_trashed_items(self) -> list[TrashItemDTO]:
        items = self._repo.get_all_trashed_items()
        result = []
        now = datetime.now(UTC)
        for item in items:
            # Calculate days until permanent deletion (30 day retention)
            # Handle both timezone-aware and naive datetimes
            deleted_at = item.deleted_at
            if deleted_at.tzinfo is None:
                deleted_at = deleted_at.replace(tzinfo=UTC)
            days_in_trash = (now - deleted_at).days
            days_until_deletion = max(0, 30 - days_in_trash)
            result.append(
                TrashItemDTO(
                    id=item.id,
                    type=item.type.value if hasattr(item.type, 'value') else item.type,
                    name=item.name,
                    deleted_at=item.deleted_at,
                    days_until_permanent_deletion=days_until_deletion,
                )
            )
        return result

    def empty_trash(self) -> tuple[int, int]:
        return self._repo.empty_trash()

    def get_trash_stats(self) -> dict:
        return self._repo.get_trash_stats()

    def get_trashed_channel_by_db_id(self, db_id: int) -> ChannelMetadataDTO | None:
        """Get a trashed channel by its database ID."""
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == db_id,
            ChannelMetadata.deleted_at.isnot(None),
        ).first()
        return _channel_to_dto(channel) if channel else None

    def get_all_trashed_channels(self) -> list[ChannelMetadataDTO]:
        """Get all trashed channels."""
        channels = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None),
        ).all()
        return [_channel_to_dto(c) for c in channels]


# =============================================================================
# Audio Repository Adapter
# =============================================================================

class AudioRepositoryAdapter(AudioRepositoryPort):
    """Adapter that implements AudioRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        from src.infrastructure.persistence.audio_repository import AudioRepository
        self._db = db
        self._repo = AudioRepository(self._db)

    def _to_dto(self, audio) -> AudioOverviewDTO:
        """Convert AudioOverviewDB to DTO."""
        return AudioOverviewDTO(
            id=audio.id,
            audio_id=audio.audio_id,
            channel_id=audio.channel_id,
            title=audio.title,
            status=audio.status,
            language=audio.language,
            style=audio.style,
            script_json=audio.script_json,
            audio_path=audio.audio_path,
            audio_duration_seconds=audio.duration_seconds,
            error_message=audio.error_message,
            created_at=audio.created_at,
            completed_at=audio.completed_at,
        )

    def create_audio_overview(
        self,
        channel_id: int,
        language: str,
        style: str,
    ) -> AudioOverviewDTO:
        audio = self._repo.create_audio_overview(channel_id, language, style)
        return self._to_dto(audio)

    def get_audio_by_id(self, audio_id: str) -> AudioOverviewDTO | None:
        audio = self._repo.get_audio_by_id(audio_id)
        return self._to_dto(audio) if audio else None

    def get_audios_by_channel(
        self,
        channel_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AudioOverviewDTO]:
        audios = self._repo.get_audios_by_channel(channel_id, limit, offset)
        return [self._to_dto(a) for a in audios]

    def count_audios_by_channel(self, channel_id: int) -> int:
        return self._repo.count_audios_by_channel(channel_id)

    def update_status(
        self,
        audio_id: str,
        status: str,
        error_message: str | None = None,
    ) -> AudioOverviewDTO | None:
        audio = self._repo.update_status(audio_id, status, error_message)
        return self._to_dto(audio) if audio else None

    def update_script(self, audio_id: str, script_json: str) -> AudioOverviewDTO | None:
        audio = self._repo.update_script(audio_id, script_json)
        return self._to_dto(audio) if audio else None

    def update_audio_complete(
        self,
        audio_id: str,
        audio_path: str,
        duration_seconds: int,
    ) -> AudioOverviewDTO | None:
        audio = self._repo.update_audio_complete(audio_id, audio_path, duration_seconds)
        return self._to_dto(audio) if audio else None

    def delete_audio(self, audio_id: str) -> bool:
        return self._repo.delete_audio(audio_id)

    def get_channel_by_store_id(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        channel = self._repo.get_channel_by_store_id(gemini_store_id)
        return _channel_to_dto(channel) if channel else None


# =============================================================================
# Document Preview Cache Repository Adapter
# =============================================================================

def _preview_cache_to_dto(cache: DocumentPreviewCacheDB) -> DocumentPreviewCacheDTO:
    """Convert DocumentPreviewCacheDB model to DTO."""
    return DocumentPreviewCacheDTO(
        id=cache.id,
        document_id=cache.document_id,
        channel_id=cache.channel_id,
        filename=cache.filename,
        content=cache.content,
        total_characters=cache.total_characters,
        created_at=cache.created_at,
        updated_at=cache.updated_at,
    )


class DocumentPreviewCacheRepositoryAdapter(DocumentPreviewCacheRepositoryPort):
    """Adapter that implements DocumentPreviewCacheRepositoryPort."""

    def __init__(self, db):
        """Initialize adapter with database session.

        Args:
            db: Database session (required).
        """
        self._db = db

    def get_by_document_id(self, document_id: str) -> DocumentPreviewCacheDTO | None:
        cache = self._db.query(DocumentPreviewCacheDB).filter(
            DocumentPreviewCacheDB.document_id == document_id
        ).first()
        return _preview_cache_to_dto(cache) if cache else None

    def create(
        self,
        document_id: str,
        channel_id: str,
        filename: str,
        content: str,
    ) -> DocumentPreviewCacheDTO:
        cache = DocumentPreviewCacheDB(
            document_id=document_id,
            channel_id=channel_id,
            filename=filename,
            content=content,
            total_characters=len(content),
        )
        self._db.add(cache)
        self._db.commit()
        self._db.refresh(cache)
        return _preview_cache_to_dto(cache)

    def delete_by_document_id(self, document_id: str) -> bool:
        cache = self._db.query(DocumentPreviewCacheDB).filter(
            DocumentPreviewCacheDB.document_id == document_id
        ).first()
        if cache:
            self._db.delete(cache)
            self._db.commit()
            return True
        return False

    def delete_by_channel_id(self, channel_id: str) -> int:
        count = self._db.query(DocumentPreviewCacheDB).filter(
            DocumentPreviewCacheDB.channel_id == channel_id
        ).delete()
        self._db.commit()
        return count
