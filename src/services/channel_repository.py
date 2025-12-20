# -*- coding: utf-8 -*-
"""Repository for channel metadata database operations."""

import json
import secrets
from datetime import datetime, UTC, timedelta
from sqlalchemy.orm import Session

from src.models.db_models import ChannelMetadata, ChatMessageDB, ChatSessionDB


class ChannelRepository:
    """Repository for channel metadata operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(self, gemini_store_id: str, name: str, description: str | None = None) -> ChannelMetadata:
        """Create a new channel metadata record.

        Args:
            gemini_store_id: The Gemini File Search Store ID
            name: Channel display name
            description: Channel description

        Returns:
            Created ChannelMetadata
        """
        channel = ChannelMetadata(
            gemini_store_id=gemini_store_id,
            name=name,
            description=description,
        )
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return channel

    def get_by_gemini_id(self, gemini_store_id: str) -> ChannelMetadata | None:
        """Get channel by Gemini store ID.

        Args:
            gemini_store_id: The Gemini File Search Store ID

        Returns:
            ChannelMetadata or None
        """
        return self.db.query(ChannelMetadata).filter(
            ChannelMetadata.gemini_store_id == gemini_store_id
        ).first()

    def get_all(self, limit: int | None = None, offset: int = 0) -> list[ChannelMetadata]:
        """Get all channels with optional pagination.

        Args:
            limit: Maximum number of channels to return (None for all)
            offset: Number of channels to skip

        Returns:
            List of channels
        """
        query = self.db.query(ChannelMetadata).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def count(self) -> int:
        """Get total count of channels.

        Returns:
            Total number of channels
        """
        return self.db.query(ChannelMetadata).count()

    def touch(self, gemini_store_id: str) -> ChannelMetadata | None:
        """Update last accessed time for a channel.

        Args:
            gemini_store_id: The Gemini File Search Store ID

        Returns:
            Updated ChannelMetadata or None
        """
        channel = self.get_by_gemini_id(gemini_store_id)
        if channel:
            channel.last_accessed_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(channel)
        return channel

    def update_stats(
        self,
        gemini_store_id: str,
        file_count: int | None = None,
        total_size_bytes: int | None = None,
    ) -> ChannelMetadata | None:
        """Update channel statistics.

        Args:
            gemini_store_id: The Gemini File Search Store ID
            file_count: Number of files
            total_size_bytes: Total size in bytes

        Returns:
            Updated ChannelMetadata or None
        """
        channel = self.get_by_gemini_id(gemini_store_id)
        if channel:
            if file_count is not None:
                channel.file_count = file_count
            if total_size_bytes is not None:
                channel.total_size_bytes = total_size_bytes
            self.db.commit()
            self.db.refresh(channel)
        return channel

    def update(
        self,
        gemini_store_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> ChannelMetadata | None:
        """Update channel metadata.

        Args:
            gemini_store_id: The Gemini File Search Store ID
            name: New channel name (if provided)
            description: New channel description (if provided)

        Returns:
            Updated ChannelMetadata or None if not found
        """
        channel = self.get_by_gemini_id(gemini_store_id)
        if channel:
            if name is not None:
                channel.name = name
            if description is not None:
                channel.description = description
            channel.last_accessed_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(channel)
        return channel

    def delete(self, gemini_store_id: str) -> bool:
        """Delete channel metadata.

        Args:
            gemini_store_id: The Gemini File Search Store ID

        Returns:
            True if deleted
        """
        channel = self.get_by_gemini_id(gemini_store_id)
        if channel:
            self.db.delete(channel)
            self.db.commit()
            return True
        return False

    def get_inactive_channels(self, inactive_days: int) -> list[ChannelMetadata]:
        """Get channels that haven't been accessed for specified days.

        Args:
            inactive_days: Number of days of inactivity

        Returns:
            List of inactive channels
        """
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(days=inactive_days)
        return self.db.query(ChannelMetadata).filter(
            ChannelMetadata.last_accessed_at < cutoff
        ).all()


class ChatHistoryRepository:
    """Repository for chat history operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def add_message(
        self,
        channel: ChannelMetadata,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        session: ChatSessionDB | None = None,
    ) -> ChatMessageDB:
        """Add a chat message.

        Args:
            channel: The channel metadata
            role: 'user' or 'assistant'
            content: Message content
            sources: List of source dicts (for assistant messages)
            session: Optional chat session for multi-turn context

        Returns:
            Created ChatMessageDB
        """
        message = ChatMessageDB(
            channel_id=channel.id,
            session_id=session.id if session else None,
            role=role,
            content=content,
            sources_json=json.dumps(sources or []),
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_history(self, channel: ChannelMetadata, limit: int = 100) -> list[ChatMessageDB]:
        """Get chat history for a channel.

        Args:
            channel: The channel metadata
            limit: Maximum number of messages

        Returns:
            List of chat messages
        """
        return self.db.query(ChatMessageDB).filter(
            ChatMessageDB.channel_id == channel.id
        ).order_by(ChatMessageDB.created_at.asc()).limit(limit).all()

    def get_session_history(self, session: ChatSessionDB, limit: int | None = None) -> list[ChatMessageDB]:
        """Get chat history for a specific session.

        Args:
            session: The chat session
            limit: Maximum number of messages (defaults to session's context_window)

        Returns:
            List of chat messages in chronological order
        """
        query = self.db.query(ChatMessageDB).filter(
            ChatMessageDB.session_id == session.id
        ).order_by(ChatMessageDB.created_at.asc())

        if limit is not None:
            query = query.limit(limit)
        elif session.context_window:
            query = query.limit(session.context_window)

        return query.all()

    def clear_history(self, channel: ChannelMetadata) -> int:
        """Clear chat history for a channel.

        Args:
            channel: The channel metadata

        Returns:
            Number of deleted messages
        """
        count = self.db.query(ChatMessageDB).filter(
            ChatMessageDB.channel_id == channel.id
        ).delete()
        self.db.commit()
        return count


class ChatSessionRepository:
    """Repository for chat session operations."""

    SESSION_TIMEOUT_HOURS = 24  # Sessions expire after 24 hours of inactivity

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(
        self,
        channel: ChannelMetadata,
        context_window: int = 10,
    ) -> ChatSessionDB:
        """Create a new chat session.

        Args:
            channel: The channel metadata
            context_window: Number of messages to include as context

        Returns:
            Created ChatSessionDB
        """
        session_id = f"sess_{secrets.token_hex(16)}"
        session = ChatSessionDB(
            session_id=session_id,
            channel_id=channel.id,
            context_window=context_window,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_session_id(self, session_id: str) -> ChatSessionDB | None:
        """Get session by session ID.

        Args:
            session_id: The session ID string (e.g., "sess_abc123")

        Returns:
            ChatSessionDB or None
        """
        return self.db.query(ChatSessionDB).filter(
            ChatSessionDB.session_id == session_id
        ).first()

    def get_or_create(
        self,
        channel: ChannelMetadata,
        session_id: str | None = None,
        context_window: int = 10,
    ) -> tuple[ChatSessionDB, bool]:
        """Get existing session or create a new one.

        Args:
            channel: The channel metadata
            session_id: Optional existing session ID
            context_window: Number of messages for new sessions

        Returns:
            Tuple of (ChatSessionDB, created: bool)
        """
        if session_id:
            session = self.get_by_session_id(session_id)
            if session and session.channel_id == channel.id:
                # Check if session is expired
                if not self.is_expired(session):
                    self.touch(session)
                    return session, False

        # Create new session
        session = self.create(channel, context_window)
        return session, True

    def touch(self, session: ChatSessionDB) -> ChatSessionDB:
        """Update last activity time for a session.

        Args:
            session: The chat session

        Returns:
            Updated ChatSessionDB
        """
        session.last_activity_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(session)
        return session

    def is_expired(self, session: ChatSessionDB) -> bool:
        """Check if a session has expired.

        Args:
            session: The chat session

        Returns:
            True if expired
        """
        cutoff = datetime.now(UTC) - timedelta(hours=self.SESSION_TIMEOUT_HOURS)
        # Handle timezone-naive datetime from SQLite
        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=UTC)
        return last_activity < cutoff

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID string

        Returns:
            True if deleted
        """
        session = self.get_by_session_id(session_id)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False

    def cleanup_expired(self) -> int:
        """Delete all expired sessions.

        Returns:
            Number of deleted sessions
        """
        cutoff = datetime.now(UTC) - timedelta(hours=self.SESSION_TIMEOUT_HOURS)
        count = self.db.query(ChatSessionDB).filter(
            ChatSessionDB.last_activity_at < cutoff
        ).delete()
        self.db.commit()
        return count
