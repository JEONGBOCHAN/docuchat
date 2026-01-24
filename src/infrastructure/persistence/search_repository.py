# -*- coding: utf-8 -*-
"""Repository for search history database operations."""

from datetime import datetime, UTC
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.db_models import SearchHistoryDB, ChannelMetadata


class SearchHistoryRepository:
    """Repository for search history operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def add_or_update(self, channel: ChannelMetadata, query: str) -> SearchHistoryDB:
        """Add a search query or update if exists.

        Args:
            channel: The channel metadata
            query: The search query

        Returns:
            Created or updated SearchHistoryDB
        """
        # Normalize query (trim whitespace, lowercase for matching)
        normalized_query = query.strip()

        # Check if this query already exists for this channel
        existing = (
            self.db.query(SearchHistoryDB)
            .filter(
                SearchHistoryDB.channel_id == channel.id,
                func.lower(SearchHistoryDB.query) == normalized_query.lower(),
            )
            .first()
        )

        if existing:
            # Update existing entry
            existing.search_count += 1
            existing.last_searched_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        # Create new entry
        history = SearchHistoryDB(
            channel_id=channel.id,
            query=normalized_query,
            search_count=1,
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_history(
        self,
        channel: ChannelMetadata,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchHistoryDB]:
        """Get search history for a channel.

        Args:
            channel: The channel metadata
            limit: Maximum number of entries
            offset: Number of entries to skip

        Returns:
            List of search history entries (most recent first)
        """
        return (
            self.db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.channel_id == channel.id)
            .order_by(SearchHistoryDB.last_searched_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_history(self, channel: ChannelMetadata) -> int:
        """Count search history entries for a channel.

        Args:
            channel: The channel metadata

        Returns:
            Number of history entries
        """
        return (
            self.db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.channel_id == channel.id)
            .count()
        )

    def get_suggestions(
        self,
        channel: ChannelMetadata,
        query_prefix: str,
        limit: int = 10,
    ) -> list[SearchHistoryDB]:
        """Get search suggestions based on query prefix.

        Args:
            channel: The channel metadata
            query_prefix: The prefix to match
            limit: Maximum number of suggestions

        Returns:
            List of matching search history entries (sorted by popularity)
        """
        prefix = query_prefix.strip().lower()
        if not prefix:
            # Return popular searches if no prefix
            return (
                self.db.query(SearchHistoryDB)
                .filter(SearchHistoryDB.channel_id == channel.id)
                .order_by(SearchHistoryDB.search_count.desc())
                .limit(limit)
                .all()
            )

        return (
            self.db.query(SearchHistoryDB)
            .filter(
                SearchHistoryDB.channel_id == channel.id,
                func.lower(SearchHistoryDB.query).like(f"{prefix}%"),
            )
            .order_by(SearchHistoryDB.search_count.desc())
            .limit(limit)
            .all()
        )

    def get_popular(
        self,
        channel: ChannelMetadata,
        limit: int = 10,
    ) -> list[SearchHistoryDB]:
        """Get popular searches for a channel.

        Args:
            channel: The channel metadata
            limit: Maximum number of entries

        Returns:
            List of popular search entries
        """
        return (
            self.db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.channel_id == channel.id)
            .order_by(SearchHistoryDB.search_count.desc())
            .limit(limit)
            .all()
        )

    def get_by_id(self, history_id: int) -> SearchHistoryDB | None:
        """Get search history entry by ID.

        Args:
            history_id: The history entry ID

        Returns:
            SearchHistoryDB or None
        """
        return (
            self.db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.id == history_id)
            .first()
        )

    def delete(self, history: SearchHistoryDB) -> bool:
        """Delete a search history entry.

        Args:
            history: The history entry to delete

        Returns:
            True if deleted
        """
        self.db.delete(history)
        self.db.commit()
        return True

    def clear_channel_history(self, channel: ChannelMetadata) -> int:
        """Clear all search history for a channel.

        Args:
            channel: The channel metadata

        Returns:
            Number of deleted entries
        """
        count = (
            self.db.query(SearchHistoryDB)
            .filter(SearchHistoryDB.channel_id == channel.id)
            .delete()
        )
        self.db.commit()
        return count
