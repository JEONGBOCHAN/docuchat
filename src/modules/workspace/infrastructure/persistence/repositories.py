# -*- coding: utf-8 -*-
"""Workspace repository adapters.

These adapters wrap the existing repository implementations and convert
between SQLAlchemy models and application DTOs.
"""

import json
from datetime import datetime, timedelta, UTC

from sqlalchemy import func

from src.shared.kernel.contracts.ports.persistence import (
    ChannelMetadataDTO,
    NoteDTO,
    FavoriteDTO,
    SearchHistoryDTO,
    TrashItemDTO,
    AudioOverviewDTO,
    DocumentPreviewCacheDTO,
    ChannelRepositoryPort,
    NoteRepositoryPort,
    FavoriteRepositoryPort,
    SearchHistoryRepositoryPort,
    TrashRepositoryPort,
    AudioRepositoryPort,
    DocumentPreviewCacheRepositoryPort,
)
from src.modules.workspace.infrastructure.persistence.models import (
    ChannelMetadata,
    NoteDB,
    FavoriteDB,
    DocumentPreviewCacheDB,
)


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
    """Adapter that implements ChannelRepositoryPort with direct SQLAlchemy queries."""

    def __init__(self, db):
        self._db = db

    def _get_by_gemini_id(self, gemini_store_id: str) -> ChannelMetadata | None:
        return self._db.query(ChannelMetadata).filter(
            ChannelMetadata.gemini_store_id == gemini_store_id
        ).first()

    def create(
        self,
        gemini_store_id: str,
        name: str,
        description: str | None = None,
    ) -> ChannelMetadataDTO:
        channel = ChannelMetadata(
            gemini_store_id=gemini_store_id,
            name=name,
            description=description,
        )
        self._db.add(channel)
        self._db.commit()
        self._db.refresh(channel)
        return _channel_to_dto(channel)

    def get_by_gemini_id(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        channel = self._get_by_gemini_id(gemini_store_id)
        return _channel_to_dto(channel) if channel else None

    def get_all(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ChannelMetadataDTO]:
        query = self._db.query(ChannelMetadata).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return [_channel_to_dto(c) for c in query.all()]

    def count(self) -> int:
        return self._db.query(ChannelMetadata).count()

    def touch(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        channel = self._get_by_gemini_id(gemini_store_id)
        if channel:
            channel.last_accessed_at = datetime.now(UTC)
            self._db.commit()
            self._db.refresh(channel)
        return _channel_to_dto(channel) if channel else None

    def update_stats(
        self,
        gemini_store_id: str,
        file_count: int | None = None,
        total_size_bytes: int | None = None,
    ) -> ChannelMetadataDTO | None:
        channel = self._get_by_gemini_id(gemini_store_id)
        if channel:
            if file_count is not None:
                channel.file_count = file_count
            if total_size_bytes is not None:
                channel.total_size_bytes = total_size_bytes
            self._db.commit()
            self._db.refresh(channel)
        return _channel_to_dto(channel) if channel else None

    def update(
        self,
        gemini_store_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> ChannelMetadataDTO | None:
        channel = self._get_by_gemini_id(gemini_store_id)
        if channel:
            if name is not None:
                channel.name = name
            if description is not None:
                channel.description = description
            channel.last_accessed_at = datetime.now(UTC)
            self._db.commit()
            self._db.refresh(channel)
        return _channel_to_dto(channel) if channel else None

    def delete(self, gemini_store_id: str) -> bool:
        channel = self._get_by_gemini_id(gemini_store_id)
        if channel:
            self._db.delete(channel)
            self._db.commit()
            return True
        return False

    def get_inactive_channels(self, inactive_days: int) -> list[ChannelMetadataDTO]:
        cutoff = datetime.now(UTC) - timedelta(days=inactive_days)
        channels = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.last_accessed_at < cutoff
        ).all()
        return [_channel_to_dto(c) for c in channels]

    def get_deleted_store_ids(self) -> set[str]:
        rows = self._db.query(ChannelMetadata.gemini_store_id).filter(
            ChannelMetadata.deleted_at.isnot(None)
        ).all()
        return {r[0] for r in rows}



# =============================================================================
# Note Repository Adapter
# =============================================================================

class NoteRepositoryAdapter(NoteRepositoryPort):
    """Adapter that implements NoteRepositoryPort with direct SQLAlchemy queries."""

    def __init__(self, db):
        self._db = db

    def _get_active_note(self, note_id: int) -> NoteDB | None:
        return self._db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.is_(None),
        ).first()

    def create(
        self,
        channel_id: int,
        title: str,
        content: str,
        sources: list[dict],
    ) -> NoteDTO:
        note = NoteDB(
            channel_id=channel_id,
            title=title,
            content=content,
            sources_json=json.dumps(sources or []),
        )
        self._db.add(note)
        self._db.commit()
        self._db.refresh(note)
        return _note_to_dto(note)

    def get_by_id(self, note_id: int) -> NoteDTO | None:
        note = self._get_active_note(note_id)
        return _note_to_dto(note) if note else None

    def get_by_channel(
        self,
        channel_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NoteDTO]:
        notes = (
            self._db.query(NoteDB)
            .filter(
                NoteDB.channel_id == channel_id,
                NoteDB.deleted_at.is_(None),
            )
            .order_by(NoteDB.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_note_to_dto(n) for n in notes]

    def count_by_channel(self, channel_id: int) -> int:
        return self._db.query(NoteDB).filter(
            NoteDB.channel_id == channel_id,
            NoteDB.deleted_at.is_(None),
        ).count()

    def update(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> NoteDTO | None:
        note = self._get_active_note(note_id)
        if not note:
            return None
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        self._db.commit()
        self._db.refresh(note)
        return _note_to_dto(note)

    def delete(self, note_id: int) -> bool:
        note = self._get_active_note(note_id)
        if not note:
            return False
        self._db.delete(note)
        self._db.commit()
        return True


# =============================================================================
# Favorite Repository Adapter
# =============================================================================

class FavoriteRepositoryAdapter(FavoriteRepositoryPort):
    """Adapter that implements FavoriteRepositoryPort with direct SQLAlchemy queries."""

    def __init__(self, db):
        self._db = db

    def _get(self, target_type: str, target_id: str) -> FavoriteDB | None:
        return self._db.query(FavoriteDB).filter(
            FavoriteDB.target_type == target_type,
            FavoriteDB.target_id == target_id,
        ).first()

    @staticmethod
    def _to_dto(f: FavoriteDB) -> FavoriteDTO:
        return FavoriteDTO(
            id=f.id,
            target_type=f.target_type,
            target_id=f.target_id,
            display_order=f.display_order,
            created_at=f.created_at,
        )

    def add(self, target_type: str, target_id: str) -> FavoriteDTO:
        existing = self._get(target_type, target_id)
        if existing:
            return self._to_dto(existing)

        max_order = (
            self._db.query(func.max(FavoriteDB.display_order))
            .filter(FavoriteDB.target_type == target_type)
            .scalar()
        )
        fav = FavoriteDB(
            target_type=target_type,
            target_id=target_id,
            display_order=(max_order or 0) + 1,
        )
        self._db.add(fav)
        self._db.commit()
        self._db.refresh(fav)
        return self._to_dto(fav)

    def remove(self, target_type: str, target_id: str) -> bool:
        fav = self._get(target_type, target_id)
        if not fav:
            return False
        self._db.delete(fav)
        self._db.commit()
        return True

    def is_favorited(self, target_type: str, target_id: str) -> bool:
        return self._get(target_type, target_id) is not None

    def get_favorited_ids(self, target_type: str) -> set[str]:
        rows = self._db.query(FavoriteDB.target_id).filter(
            FavoriteDB.target_type == target_type
        ).all()
        return {r[0] for r in rows}

    def get_all(self, target_type: str | None = None) -> list[FavoriteDTO]:
        query = self._db.query(FavoriteDB)
        if target_type:
            query = query.filter(FavoriteDB.target_type == target_type)
        return [self._to_dto(f) for f in query.order_by(FavoriteDB.display_order).all()]

    def list_all(
        self,
        target_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FavoriteDTO]:
        query = self._db.query(FavoriteDB)
        if target_type:
            query = query.filter(FavoriteDB.target_type == target_type)
        favs = query.order_by(FavoriteDB.display_order).offset(offset).limit(limit).all()
        return [self._to_dto(f) for f in favs]

    def count(self, target_type: str | None = None) -> int:
        query = self._db.query(func.count(FavoriteDB.id))
        if target_type:
            query = query.filter(FavoriteDB.target_type == target_type)
        return query.scalar() or 0

    def reorder(self, favorite_ids: list[int]) -> None:
        for order, fav_id in enumerate(favorite_ids, start=1):
            fav = self._db.query(FavoriteDB).filter(FavoriteDB.id == fav_id).first()
            if fav:
                fav.display_order = order
        self._db.commit()


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

    def get_expired_trashed_channels(self, retention_days: int) -> list[ChannelMetadataDTO]:
        """Get trashed channels that have exceeded the retention period."""
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        channels = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None),
            ChannelMetadata.deleted_at < cutoff,
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


