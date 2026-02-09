# -*- coding: utf-8 -*-
"""Repository for chat session memory (rolling summary) operations."""

from datetime import datetime, UTC
from sqlalchemy.orm import Session

from src.infrastructure.persistence.db_models import ChatSessionMemoryDB, ChatSessionDB


class ChatSessionMemoryRepository:
    """Repository for chat session memory operations."""

    def __init__(self, db: Session):
        self.db = db

    def _resolve_session_pk(self, session_id: str) -> int | None:
        """Resolve string session_id to integer PK."""
        session = self.db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()
        return session.id if session else None

    def get_by_session_id(self, session_id: str) -> ChatSessionMemoryDB | None:
        """Get memory by session ID string."""
        pk = self._resolve_session_pk(session_id)
        if pk is None:
            return None
        return self.db.query(ChatSessionMemoryDB).filter(
            ChatSessionMemoryDB.session_id == pk
        ).first()

    def upsert(
        self,
        session_id: str,
        rolling_summary: str,
        last_compacted_message_id: int | None = None,
        increment_compaction: bool = True,
    ) -> ChatSessionMemoryDB:
        """Create or update session memory."""
        pk = self._resolve_session_pk(session_id)
        if pk is None:
            raise ValueError(f"Session not found: {session_id}")

        memory = self.db.query(ChatSessionMemoryDB).filter(
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
            self.db.add(memory)

        self.db.commit()
        self.db.refresh(memory)
        return memory

    def clear(self, session_id: str) -> bool:
        """Delete session memory."""
        pk = self._resolve_session_pk(session_id)
        if pk is None:
            return False
        count = self.db.query(ChatSessionMemoryDB).filter(
            ChatSessionMemoryDB.session_id == pk
        ).delete()
        self.db.commit()
        return count > 0
