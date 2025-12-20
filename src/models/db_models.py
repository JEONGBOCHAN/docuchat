# -*- coding: utf-8 -*-
"""SQLAlchemy database models."""

from datetime import datetime, UTC
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from src.core.database import Base


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class ChannelMetadata(Base):
    """Channel metadata for lifecycle management."""

    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gemini_store_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    file_count = Column(Integer, default=0)
    total_size_bytes = Column(BigInteger, default=0)

    # Relationship to chat messages
    messages = relationship("ChatMessageDB", back_populates="channel", cascade="all, delete-orphan")

    def touch(self):
        """Update last accessed time."""
        self.last_accessed_at = utc_now()


class ChatMessageDB(Base):
    """Chat message for history persistence."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources_json = Column(Text, default="[]")  # JSON array of sources
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship to channel
    channel = relationship("ChannelMetadata", back_populates="messages")
