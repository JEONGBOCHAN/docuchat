# -*- coding: utf-8 -*-
"""Conversation module persistence adapters.

Self-contained adapters that implement chat history, session, and session memory
repository ports using module-local ORM models.
"""

import json
import secrets
from datetime import datetime, UTC, timedelta

from src.shared.kernel.contracts.ports.persistence import (
    ChatMessageDTO,
    ChatSessionDTO,
    ChatSessionMemoryDTO,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    ChatSessionMemoryRepositoryPort,
)
from src.modules.conversation.infrastructure.persistence.models import (
    ChatMessageDB,
    ChatSessionDB,
    ChatSessionMemoryDB,
)


# =============================================================================
# DTO Converters
# =============================================================================

def _chat_message_to_dto(msg: ChatMessageDB) -> ChatMessageDTO:
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
    return ChatSessionDTO(
        id=session.id,
        session_id=session.session_id,
        channel_id=session.channel_id,
        channel_gemini_store_id=session.channel.gemini_store_id if session.channel else "",
        context_window=session.context_window,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
    )


def _session_memory_to_dto(memory: ChatSessionMemoryDB) -> ChatSessionMemoryDTO:
    return ChatSessionMemoryDTO(
        id=memory.id,
        session_id=memory.session_id,
        rolling_summary=memory.rolling_summary,
        last_compacted_message_id=memory.last_compacted_message_id,
        total_compactions=memory.total_compactions,
        updated_at=memory.updated_at,
        version=memory.version,
    )


# =============================================================================
# Chat History Repository Adapter
# =============================================================================

class ChatHistoryRepositoryAdapter(ChatHistoryRepositoryPort):
    """Adapter that implements ChatHistoryRepositoryPort."""

    def __init__(self, db):
        self._db = db

    def add_message(
        self,
        channel_id: int,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        session_id: str | None = None,
    ) -> ChatMessageDTO:
        session_pk = None
        if session_id:
            session = self._db.query(ChatSessionDB).filter(
                ChatSessionDB.session_id == session_id
            ).first()
            session_pk = session.id if session else None

        msg = ChatMessageDB(
            channel_id=channel_id,
            session_id=session_pk,
            role=role,
            content=content,
            sources_json=json.dumps(sources or []),
        )
        self._db.add(msg)
        self._db.commit()
        self._db.refresh(msg)
        return _chat_message_to_dto(msg)

    def get_history(
        self,
        channel_id: int,
        limit: int = 100,
    ) -> list[ChatMessageDTO]:
        rows = (
            self._db.query(ChatMessageDB)
            .filter(ChatMessageDB.channel_id == channel_id)
            .order_by(ChatMessageDB.created_at.desc(), ChatMessageDB.id.desc())
            .limit(limit)
            .all()
        )
        return [_chat_message_to_dto(m) for m in reversed(rows)]

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
        if effective_limit is None:
            effective_limit = session.context_window

        if effective_limit:
            rows = (
                self._db.query(ChatMessageDB)
                .filter(ChatMessageDB.session_id == session.id)
                .order_by(ChatMessageDB.created_at.desc(), ChatMessageDB.id.desc())
                .limit(effective_limit)
                .all()
            )
            return [_chat_message_to_dto(m) for m in reversed(rows)]

        rows = (
            self._db.query(ChatMessageDB)
            .filter(ChatMessageDB.session_id == session.id)
            .order_by(ChatMessageDB.created_at.asc(), ChatMessageDB.id.asc())
            .all()
        )
        return [_chat_message_to_dto(m) for m in rows]

    def get_full_session_history(self, session_id: str) -> list[ChatMessageDTO]:
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()
        if not session:
            return []

        rows = (
            self._db.query(ChatMessageDB)
            .filter(ChatMessageDB.session_id == session.id)
            .order_by(ChatMessageDB.created_at.asc(), ChatMessageDB.id.asc())
            .all()
        )
        return [_chat_message_to_dto(m) for m in rows]

    def clear_history(self, channel_id: int) -> int:
        count = self._db.query(ChatMessageDB).filter(
            ChatMessageDB.channel_id == channel_id
        ).delete()
        self._db.commit()
        return count


# =============================================================================
# Chat Session Repository Adapter
# =============================================================================

class ChatSessionRepositoryAdapter(ChatSessionRepositoryPort):
    """Adapter that implements ChatSessionRepositoryPort."""

    def __init__(self, db, session_timeout_hours: int = 168):
        self._db = db
        self._session_timeout_hours = session_timeout_hours

    def create(
        self,
        channel_id: int,
        context_window: int = 100,
    ) -> ChatSessionDTO:
        session_id = f"sess_{secrets.token_hex(16)}"
        session = ChatSessionDB(
            session_id=session_id,
            channel_id=channel_id,
            context_window=context_window,
        )
        self._db.add(session)
        self._db.commit()
        self._db.refresh(session)
        return _chat_session_to_dto(session)

    def get_by_session_id(self, session_id: str) -> ChatSessionDTO | None:
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()
        return _chat_session_to_dto(session) if session else None

    def get_or_create(
        self,
        channel_id: int,
        session_id: str | None = None,
        context_window: int = 100,
    ) -> tuple[ChatSessionDTO, bool]:
        if session_id:
            session = self._db.query(ChatSessionDB).filter(
                ChatSessionDB.session_id == session_id
            ).first()
            if session and session.channel_id == channel_id:
                if not self._is_expired_model(session):
                    session.last_activity_at = datetime.now(UTC)
                    self._db.commit()
                    self._db.refresh(session)
                    return _chat_session_to_dto(session), False

        return self.create(channel_id, context_window), True

    def touch(self, session_id: str) -> ChatSessionDTO | None:
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()
        if not session:
            return None
        session.last_activity_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(session)
        return _chat_session_to_dto(session)

    def is_expired(self, session_id: str) -> bool:
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()
        if not session:
            return True
        return self._is_expired_model(session)

    def delete(self, session_id: str) -> bool:
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()
        if not session:
            return False
        self._db.delete(session)
        self._db.commit()
        return True

    def cleanup_expired(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=self._session_timeout_hours)
        count = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.last_activity_at < cutoff
        ).delete()
        self._db.commit()
        return count

    def list_session_ids_by_channel(self, channel_id: int) -> list[str]:
        rows = self._db.query(ChatSessionDB.session_id).filter(
            ChatSessionDB.channel_id == channel_id
        ).all()
        return [row[0] for row in rows]

    def _is_expired_model(self, session: ChatSessionDB) -> bool:
        cutoff = datetime.now(UTC) - timedelta(hours=self._session_timeout_hours)
        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=UTC)
        return last_activity < cutoff


# =============================================================================
# Chat Session Memory Repository Adapter
# =============================================================================

class ChatSessionMemoryRepositoryAdapter(ChatSessionMemoryRepositoryPort):
    """Adapter that implements ChatSessionMemoryRepositoryPort."""

    def __init__(self, db):
        self._db = db

    def _resolve_session_pk(self, session_id: str) -> int | None:
        session = self._db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()
        return session.id if session else None

    def get_by_session_id(self, session_id: str) -> ChatSessionMemoryDTO | None:
        pk = self._resolve_session_pk(session_id)
        if pk is None:
            return None
        memory = self._db.query(ChatSessionMemoryDB).filter(
            ChatSessionMemoryDB.session_id == pk
        ).first()
        return _session_memory_to_dto(memory) if memory else None

    def upsert(
        self,
        session_id: str,
        rolling_summary: str,
        last_compacted_message_id: int | None = None,
        increment_compaction: bool = True,
    ) -> ChatSessionMemoryDTO:
        pk = self._resolve_session_pk(session_id)
        if pk is None:
            raise ValueError(f"Session not found: {session_id}")

        memory = self._db.query(ChatSessionMemoryDB).filter(
            ChatSessionMemoryDB.session_id == pk
        ).first()

        if memory:
            memory.rolling_summary = rolling_summary
            if last_compacted_message_id is not None:
                memory.last_compacted_message_id = last_compacted_message_id
            if increment_compaction:
                memory.total_compactions += 1
            memory.updated_at = datetime.now(UTC)
            memory.version += 1
        else:
            memory = ChatSessionMemoryDB(
                session_id=pk,
                rolling_summary=rolling_summary,
                last_compacted_message_id=last_compacted_message_id,
                total_compactions=1 if increment_compaction else 0,
                updated_at=datetime.now(UTC),
            )
            self._db.add(memory)

        self._db.commit()
        self._db.refresh(memory)
        return _session_memory_to_dto(memory)

    def clear(self, session_id: str) -> bool:
        pk = self._resolve_session_pk(session_id)
        if pk is None:
            return False
        count = self._db.query(ChatSessionMemoryDB).filter(
            ChatSessionMemoryDB.session_id == pk
        ).delete()
        self._db.commit()
        return count > 0

    def clear_by_channel(self, channel_id: int) -> int:
        session_pk_subquery = self._db.query(ChatSessionDB.id).filter(
            ChatSessionDB.channel_id == channel_id
        )
        count = self._db.query(ChatSessionMemoryDB).filter(
            ChatSessionMemoryDB.session_id.in_(session_pk_subquery)
        ).delete(synchronize_session="fetch")
        self._db.commit()
        return count
