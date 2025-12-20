# -*- coding: utf-8 -*-
"""Repository for channel metadata database operations."""

import json
from datetime import datetime, UTC
from sqlalchemy.orm import Session

from src.models.db_models import ChannelMetadata, ChatMessageDB


class ChannelRepository:
    """Repository for channel metadata operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def create(self, gemini_store_id: str, name: str) -> ChannelMetadata:
        """Create a new channel metadata record.

        Args:
            gemini_store_id: The Gemini File Search Store ID
            name: Channel display name

        Returns:
            Created ChannelMetadata
        """
        channel = ChannelMetadata(
            gemini_store_id=gemini_store_id,
            name=name,
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

    def get_all(self) -> list[ChannelMetadata]:
        """Get all channels.

        Returns:
            List of all channels
        """
        return self.db.query(ChannelMetadata).all()

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
    ) -> ChatMessageDB:
        """Add a chat message.

        Args:
            channel: The channel metadata
            role: 'user' or 'assistant'
            content: Message content
            sources: List of source dicts (for assistant messages)

        Returns:
            Created ChatMessageDB
        """
        message = ChatMessageDB(
            channel_id=channel.id,
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
