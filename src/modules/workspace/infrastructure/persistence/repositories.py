# -*- coding: utf-8 -*-
"""Workspace repository adapters.

These adapters wrap the existing repository implementations and convert
between SQLAlchemy models and application DTOs.
"""

import json
import uuid
from datetime import datetime, timedelta, UTC

from sqlalchemy import func, select

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
    SearchHistoryDB,
    AudioOverviewDB,
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
    """Adapter that implements SearchHistoryRepositoryPort with direct SQLAlchemy queries."""

    def __init__(self, db):
        self._db = db

    @staticmethod
    def _to_dto(entry: SearchHistoryDB) -> SearchHistoryDTO:
        return SearchHistoryDTO(
            id=entry.id,
            channel_id=entry.channel_id,
            query=entry.query,
            search_count=entry.search_count,
            created_at=entry.created_at,
            last_searched_at=entry.last_searched_at,
        )

    def add_or_update(self, channel_id: int, query: str) -> SearchHistoryDTO:
        normalized = query.strip()
        existing = self._db.query(SearchHistoryDB).filter(
            SearchHistoryDB.channel_id == channel_id,
            func.lower(SearchHistoryDB.query) == normalized.lower(),
        ).first()
        if existing:
            existing.search_count += 1
            existing.last_searched_at = datetime.now(UTC)
            self._db.commit()
            self._db.refresh(existing)
            return self._to_dto(existing)
        entry = SearchHistoryDB(
            channel_id=channel_id,
            query=normalized,
            search_count=1,
        )
        self._db.add(entry)
        self._db.commit()
        self._db.refresh(entry)
        return self._to_dto(entry)

    def get_recent(self, channel_id: int, limit: int = 10) -> list[SearchHistoryDTO]:
        entries = (
            self._db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.channel_id == channel_id)
            .order_by(SearchHistoryDB.last_searched_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_dto(e) for e in entries]

    def get_history(self, channel_id: int, limit: int = 50, offset: int = 0) -> list[SearchHistoryDTO]:
        entries = (
            self._db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.channel_id == channel_id)
            .order_by(SearchHistoryDB.last_searched_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_dto(e) for e in entries]

    def count_history(self, channel_id: int) -> int:
        return self._db.query(SearchHistoryDB).filter(
            SearchHistoryDB.channel_id == channel_id
        ).count()

    def get_suggestions(self, channel_id: int, prefix: str, limit: int = 10) -> list[SearchHistoryDTO]:
        p = prefix.strip().lower()
        query = self._db.query(SearchHistoryDB).filter(SearchHistoryDB.channel_id == channel_id)
        if p:
            query = query.filter(func.lower(SearchHistoryDB.query).like(f"{p}%"))
        entries = query.order_by(SearchHistoryDB.search_count.desc()).limit(limit).all()
        return [self._to_dto(e) for e in entries]

    def get_popular(self, channel_id: int, limit: int = 10) -> list[SearchHistoryDTO]:
        entries = (
            self._db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.channel_id == channel_id)
            .order_by(SearchHistoryDB.search_count.desc())
            .limit(limit)
            .all()
        )
        return [self._to_dto(e) for e in entries]

    def get_by_id(self, history_id: int) -> SearchHistoryDTO | None:
        entry = self._db.query(SearchHistoryDB).filter(SearchHistoryDB.id == history_id).first()
        return self._to_dto(entry) if entry else None

    def delete(self, history_id: int) -> bool:
        entry = self._db.query(SearchHistoryDB).filter(SearchHistoryDB.id == history_id).first()
        if not entry:
            return False
        self._db.delete(entry)
        self._db.commit()
        return True

    def clear_for_channel(self, channel_id: int) -> int:
        count = self._db.query(SearchHistoryDB).filter(
            SearchHistoryDB.channel_id == channel_id
        ).delete()
        self._db.commit()
        return count

    def clear_channel_history(self, channel_id: int) -> int:
        return self.clear_for_channel(channel_id)


# =============================================================================
# Trash Repository Adapter
# =============================================================================

class TrashRepositoryAdapter(TrashRepositoryPort):
    """Adapter that implements TrashRepositoryPort with direct SQLAlchemy queries."""

    def __init__(self, db):
        self._db = db

    def soft_delete_channel(self, channel_id: int) -> bool:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id,
            ChannelMetadata.deleted_at.is_(None),
        ).first()
        if not channel:
            return False
        channel.deleted_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(channel)
        return True

    def soft_delete_note(self, note_id: int) -> bool:
        note = self._db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.is_(None),
        ).first()
        if not note:
            return False
        note.deleted_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(note)
        return True

    def restore_channel(self, channel_id: int) -> ChannelMetadataDTO | None:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id,
            ChannelMetadata.deleted_at.isnot(None),
        ).first()
        if not channel:
            return None
        channel.deleted_at = None
        channel.last_accessed_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(channel)
        return _channel_to_dto(channel)

    def restore_note(self, note_id: int) -> NoteDTO | None:
        note = self._db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.isnot(None),
        ).first()
        if not note:
            return None
        note.deleted_at = None
        self._db.commit()
        self._db.refresh(note)
        return _note_to_dto(note)

    def permanent_delete_channel(self, channel_id: int) -> bool:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id,
            ChannelMetadata.deleted_at.isnot(None),
        ).first()
        if not channel:
            return False
        self._db.delete(channel)
        self._db.commit()
        return True

    def permanent_delete_note(self, note_id: int) -> bool:
        note = self._db.query(NoteDB).filter(
            NoteDB.id == note_id,
            NoteDB.deleted_at.isnot(None),
        ).first()
        if not note:
            return False
        self._db.delete(note)
        self._db.commit()
        return True

    def get_all_trashed_items(self) -> list[TrashItemDTO]:
        now = datetime.now(UTC)
        result: list[TrashItemDTO] = []
        for ch in self._db.query(ChannelMetadata).filter(ChannelMetadata.deleted_at.isnot(None)).order_by(ChannelMetadata.deleted_at.desc()).all():
            deleted_at = ch.deleted_at
            if deleted_at.tzinfo is None:
                deleted_at = deleted_at.replace(tzinfo=UTC)
            days = max(0, 30 - (now - deleted_at).days)
            result.append(TrashItemDTO(id=ch.id, type="channel", name=ch.name, deleted_at=ch.deleted_at, days_until_permanent_deletion=days))
        for note in self._db.query(NoteDB).filter(NoteDB.deleted_at.isnot(None)).order_by(NoteDB.deleted_at.desc()).all():
            deleted_at = note.deleted_at
            if deleted_at.tzinfo is None:
                deleted_at = deleted_at.replace(tzinfo=UTC)
            days = max(0, 30 - (now - deleted_at).days)
            result.append(TrashItemDTO(id=note.id, type="note", name=note.title, deleted_at=note.deleted_at, days_until_permanent_deletion=days))
        result.sort(key=lambda x: x.deleted_at, reverse=True)
        return result

    def empty_trash(self) -> tuple[int, int]:
        ch_count = self._db.query(ChannelMetadata).filter(ChannelMetadata.deleted_at.isnot(None)).delete()
        note_count = self._db.query(NoteDB).filter(NoteDB.deleted_at.isnot(None)).delete()
        self._db.commit()
        return ch_count, note_count

    def get_trash_stats(self) -> dict:
        ch = self._db.query(ChannelMetadata).filter(ChannelMetadata.deleted_at.isnot(None)).count()
        notes = self._db.query(NoteDB).filter(NoteDB.deleted_at.isnot(None)).count()
        return {"trashed_channels": ch, "trashed_notes": notes, "total": ch + notes}

    def get_trashed_channel_by_db_id(self, db_id: int) -> ChannelMetadataDTO | None:
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == db_id,
            ChannelMetadata.deleted_at.isnot(None),
        ).first()
        return _channel_to_dto(channel) if channel else None

    def get_all_trashed_channels(self) -> list[ChannelMetadataDTO]:
        channels = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None),
        ).all()
        return [_channel_to_dto(c) for c in channels]

    def get_expired_trashed_channels(self, retention_days: int) -> list[ChannelMetadataDTO]:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        channels = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None),
            ChannelMetadata.deleted_at < cutoff,
        ).all()
        return [_channel_to_dto(c) for c in channels]

    def cleanup_specific_channels(self, channel_ids: list[int]) -> int:
        if not channel_ids:
            return 0
        count = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id.in_(channel_ids),
            ChannelMetadata.deleted_at.isnot(None),
        ).delete(synchronize_session=False)
        self._db.commit()
        return count

    def cleanup_expired_notes(self, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        count = self._db.query(NoteDB).filter(
            NoteDB.deleted_at.isnot(None),
            NoteDB.deleted_at < cutoff,
        ).delete()
        self._db.commit()
        return count


# =============================================================================
# Audio Repository Adapter
# =============================================================================

class AudioRepositoryAdapter(AudioRepositoryPort):
    """Adapter that implements AudioRepositoryPort."""

    def __init__(self, db):
        self._db = db

    def _get(self, audio_id: str) -> AudioOverviewDB | None:
        stmt = select(AudioOverviewDB).where(AudioOverviewDB.audio_id == audio_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def _to_dto(self, audio: AudioOverviewDB) -> AudioOverviewDTO:
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
        audio = AudioOverviewDB(
            audio_id=str(uuid.uuid4()),
            channel_id=channel_id,
            status="pending",
            language=language,
            style=style,
        )
        self._db.add(audio)
        self._db.commit()
        self._db.refresh(audio)
        return self._to_dto(audio)

    def get_audio_by_id(self, audio_id: str) -> AudioOverviewDTO | None:
        audio = self._get(audio_id)
        return self._to_dto(audio) if audio else None

    def get_audios_by_channel(
        self,
        channel_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AudioOverviewDTO]:
        stmt = (
            select(AudioOverviewDB)
            .where(AudioOverviewDB.channel_id == channel_id)
            .order_by(AudioOverviewDB.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._to_dto(a) for a in self._db.execute(stmt).scalars().all()]

    def count_audios_by_channel(self, channel_id: int) -> int:
        stmt = select(func.count()).select_from(AudioOverviewDB).where(AudioOverviewDB.channel_id == channel_id)
        return self._db.execute(stmt).scalar_one()

    def update_status(
        self,
        audio_id: str,
        status: str,
        error_message: str | None = None,
    ) -> AudioOverviewDTO | None:
        audio = self._get(audio_id)
        if not audio:
            return None
        audio.status = status
        if error_message:
            audio.error_message = error_message
        if status == "completed":
            audio.completed_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(audio)
        return self._to_dto(audio)

    def update_script(self, audio_id: str, script_json: str, title: str | None = None) -> AudioOverviewDTO | None:
        audio = self._get(audio_id)
        if not audio:
            return None
        audio.script_json = script_json
        if title is not None:
            audio.title = title
        audio.status = "generating_audio"
        self._db.commit()
        self._db.refresh(audio)
        return self._to_dto(audio)

    def update_audio_complete(
        self,
        audio_id: str,
        audio_path: str,
        duration_seconds: int,
    ) -> AudioOverviewDTO | None:
        audio = self._get(audio_id)
        if not audio:
            return None
        audio.audio_path = audio_path
        audio.duration_seconds = duration_seconds
        audio.status = "completed"
        audio.completed_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(audio)
        return self._to_dto(audio)

    def delete_audio(self, audio_id: str) -> bool:
        audio = self._get(audio_id)
        if not audio:
            return False
        self._db.delete(audio)
        self._db.commit()
        return True

    def get_channel_by_store_id(self, gemini_store_id: str) -> ChannelMetadataDTO | None:
        stmt = select(ChannelMetadata).where(
            ChannelMetadata.gemini_store_id == gemini_store_id,
            ChannelMetadata.deleted_at.is_(None),
        )
        channel = self._db.execute(stmt).scalar_one_or_none()
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


