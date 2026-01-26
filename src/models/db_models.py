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
    description = Column(String(500), nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    file_count = Column(Integer, default=0)
    total_size_bytes = Column(BigInteger, default=0)
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None, index=True)

    @property
    def is_deleted(self) -> bool:
        """Check if the channel is soft-deleted."""
        return self.deleted_at is not None

    # Relationship to chat messages
    messages = relationship("ChatMessageDB", back_populates="channel", cascade="all, delete-orphan")
    # Relationship to chat sessions
    sessions = relationship("ChatSessionDB", back_populates="channel", cascade="all, delete-orphan")
    # Relationship to notes
    notes = relationship("NoteDB", back_populates="channel", cascade="all, delete-orphan")
    # Relationship to search history
    search_history = relationship("SearchHistoryDB", back_populates="channel", cascade="all, delete-orphan")
    # Relationship to audio overviews
    audio_overviews = relationship("AudioOverviewDB", back_populates="channel", cascade="all, delete-orphan")

    def touch(self):
        """Update last accessed time."""
        self.last_accessed_at = utc_now()


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
    context_window = Column(Integer, default=10)  # Number of messages to include as context

    # Relationship to channel
    channel = relationship("ChannelMetadata", back_populates="sessions")
    # Relationship to messages
    messages = relationship("ChatMessageDB", back_populates="session", cascade="all, delete-orphan")

    def touch(self):
        """Update last activity time."""
        self.last_activity_at = utc_now()


class NoteDB(Base):
    """Note for saving user notes and AI responses."""

    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    sources_json = Column(Text, default="[]")  # JSON array of sources if from AI
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None, index=True)

    # Relationship to channel
    channel = relationship("ChannelMetadata", back_populates="notes")

    @property
    def is_deleted(self) -> bool:
        """Check if the note is soft-deleted."""
        return self.deleted_at is not None


class SearchHistoryDB(Base):
    """Search history for query suggestions and analytics."""

    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(String(2000), nullable=False)
    search_count = Column(Integer, default=1)  # Track how many times this query was used
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_searched_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship to channel
    channel = relationship("ChannelMetadata", back_populates="search_history")


class FavoriteDB(Base):
    """Favorite/pin for channels, documents, and notes."""

    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_type = Column(String(20), nullable=False, index=True)  # 'channel', 'document', 'note'
    target_id = Column(String(255), nullable=False, index=True)  # gemini_store_id, file_id, or note_id
    display_order = Column(Integer, default=0, nullable=False)  # Lower = higher priority
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class DocumentPreviewCacheDB(Base):
    """Cache for extracted document text content."""

    __tablename__ = "document_preview_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(255), unique=True, nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)  # Full extracted text
    total_characters = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class AudioOverviewDB(Base):
    """Audio overview (podcast) for channels."""

    __tablename__ = "audio_overviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audio_id = Column(String(64), unique=True, nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, generating_script, generating_audio, completed, failed
    title = Column(String(300), nullable=True)
    script_json = Column(Text, nullable=True)  # JSON of PodcastScript
    audio_path = Column(String(500), nullable=True)  # Path to audio file
    duration_seconds = Column(Integer, nullable=True)
    language = Column(String(10), default="ko")
    style = Column(String(20), default="conversational")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to channel
    channel = relationship("ChannelMetadata", back_populates="audio_overviews")


class DocumentSummaryCacheDB(Base):
    """Cache for document summaries to inject into agent system prompt.

    Stores concise summaries of uploaded documents so the agent
    knows what content is available and can choose the right tool.
    """

    __tablename__ = "document_summary_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(255), unique=True, nullable=False, index=True)
    channel_id = Column(String(255), nullable=False, index=True)  # Gemini store ID
    document_name = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)  # Concise summary (~100 tokens)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
