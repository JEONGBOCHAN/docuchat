# -*- coding: utf-8 -*-
"""Repository adapters.

Workspace adapters have been moved to src.modules.workspace.infrastructure.persistence.repositories.
This file keeps conversation adapters and re-exports workspace adapters for backward compatibility.
"""

import json
from datetime import datetime, UTC

from src.application.ports.persistence import (
    ChannelMetadataDTO,
    ChatMessageDTO,
    ChatSessionDTO,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
)
from src.infrastructure.persistence.db_models import ChannelMetadata, ChatMessageDB, ChatSessionDB

# Re-export workspace adapters for backward compatibility
from src.modules.workspace.infrastructure.persistence.repositories import (  # noqa: F401
    _channel_to_dto,
    _note_to_dto,
    _preview_cache_to_dto,
    ChannelRepositoryAdapter,
    NoteRepositoryAdapter,
    FavoriteRepositoryAdapter,
    SearchHistoryRepositoryAdapter,
    TrashRepositoryAdapter,
    AudioRepositoryAdapter,
    DocumentPreviewCacheRepositoryAdapter,
)


# =============================================================================
# Model to DTO Converters (conversation)
# =============================================================================

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


# =============================================================================
# Chat History Repository Adapter
# =============================================================================

class ChatHistoryRepositoryAdapter(ChatHistoryRepositoryPort):
    """Adapter that implements ChatHistoryRepositoryPort."""

    def __init__(self, db):
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
        channel = self._db.query(ChannelMetadata).filter(
            ChannelMetadata.id == channel_id
        ).first()

        session = None
        if session_id:
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
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()

        if not session:
            return []

        effective_limit = context_window if context_window is not None else limit
        messages = self._repo.get_session_history(session, effective_limit)
        return [_chat_message_to_dto(m) for m in messages]

    def get_full_session_history(self, session_id: str) -> list[ChatMessageDTO]:
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()

        if not session:
            return []

        messages = self._repo.get_session_history(session, 0)
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

    def __init__(self, db, session_timeout_hours: int = 168):
        from src.infrastructure.persistence.channel_repository import ChatSessionRepository
        self._db = db
        self._repo = ChatSessionRepository(self._db, session_timeout_hours=session_timeout_hours)

    def create(
        self,
        channel_id: int,
        context_window: int = 100,
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
        context_window: int = 100,
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

    def list_session_ids_by_channel(self, channel_id: int) -> list[str]:
        return self._repo.list_session_ids_by_channel(channel_id)


# =============================================================================
# Chat Session Memory Repository Adapter
# =============================================================================

def _session_memory_to_dto(memory) -> "ChatSessionMemoryDTO":
    """Convert ChatSessionMemoryDB model to DTO."""
    from src.application.ports.persistence import ChatSessionMemoryDTO
    return ChatSessionMemoryDTO(
        id=memory.id,
        session_id=memory.session_id,
        rolling_summary=memory.rolling_summary,
        last_compacted_message_id=memory.last_compacted_message_id,
        total_compactions=memory.total_compactions,
        updated_at=memory.updated_at,
        version=memory.version,
    )


class ChatSessionMemoryRepositoryAdapter:
    """Adapter that implements ChatSessionMemoryRepositoryPort."""

    def __init__(self, db):
        from src.infrastructure.persistence.session_memory_repository import ChatSessionMemoryRepository
        self._db = db
        self._repo = ChatSessionMemoryRepository(self._db)

    def get_by_session_id(self, session_id: str):
        memory = self._repo.get_by_session_id(session_id)
        return _session_memory_to_dto(memory) if memory else None

    def upsert(
        self,
        session_id: str,
        rolling_summary: str,
        last_compacted_message_id: int | None = None,
        increment_compaction: bool = True,
    ):
        memory = self._repo.upsert(
            session_id=session_id,
            rolling_summary=rolling_summary,
            last_compacted_message_id=last_compacted_message_id,
            increment_compaction=increment_compaction,
        )
        return _session_memory_to_dto(memory)

    def clear(self, session_id: str) -> bool:
        return self._repo.clear(session_id)

    def clear_by_channel(self, channel_id: int) -> int:
        return self._repo.clear_by_channel(channel_id)
