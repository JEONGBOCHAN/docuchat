# -*- coding: utf-8 -*-
"""SQLAlchemy database models.

Workspace models have been moved to src.modules.workspace.infrastructure.persistence.models.
This file keeps conversation models and re-exports workspace models for backward compatibility.
"""

from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from src.core.database import Base

# Re-export workspace models for backward compatibility
from src.modules.workspace.infrastructure.persistence.models import (  # noqa: F401
    utc_now,
    ChannelMetadata,
    NoteDB,
    SearchHistoryDB,
    FavoriteDB,
    DocumentPreviewCacheDB,
    AudioOverviewDB,
    DocumentSummaryCacheDB,
)


class ChatMessageDB(Base):
    """Chat message for history persistence."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources_json = Column(Text, default="[]")  # JSON array of sources
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship to channel
    channel = relationship("ChannelMetadata", back_populates="messages")
    # Relationship to session
    session = relationship("ChatSessionDB", back_populates="messages")


class ChatSessionDB(Base):
    """Chat session for multi-turn conversation context."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    context_window = Column(Integer, default=100)  # Number of messages to include as context

    # Relationship to channel
    channel = relationship("ChannelMetadata", back_populates="sessions")
    # Relationship to messages
    messages = relationship("ChatMessageDB", back_populates="session", cascade="all, delete-orphan")

    def touch(self):
        """Update last activity time."""
        self.last_activity_at = utc_now()


class ChatSessionMemoryDB(Base):
    """Rolling summary memory for chat sessions."""

    __tablename__ = "chat_session_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    rolling_summary = Column(Text, nullable=False, default="")
    last_compacted_message_id = Column(Integer, nullable=True)
    total_compactions = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    version = Column(Integer, nullable=False, default=1)

    # Relationship to session
    session = relationship("ChatSessionDB", backref="memory", uselist=False)
