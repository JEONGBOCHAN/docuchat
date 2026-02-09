# -*- coding: utf-8 -*-
"""
Search History use case.

Extracts search history orchestration logic from the API router.
Handles channel validation + search history CRUD operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC

from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import (
    ChannelRepositoryPort,
    SearchHistoryRepositoryPort,
)
from src.application.use_cases.exceptions import ChannelNotFoundError


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class SearchHistoryItemDTO:
    """Application-layer DTO for a search history entry."""

    id: int
    channel_id: str  # gemini_store_id
    query: str
    search_count: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_searched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SearchHistoryListDTO:
    """Result of listing search history."""

    history: list[SearchHistoryItemDTO] = field(default_factory=list)
    total: int = 0


@dataclass
class SearchSuggestionDTO:
    """Application-layer DTO for search suggestion."""

    query: str
    search_count: int = 1


@dataclass
class SearchSuggestionListDTO:
    """Result of listing search suggestions."""

    suggestions: list[SearchSuggestionDTO] = field(default_factory=list)
    query: str = ""


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class SearchHistoryUseCase:
    """Orchestrates search history operations with channel validation."""

    def __init__(
        self,
        channel_port: ChannelPort,
        channel_repo: ChannelRepositoryPort,
        search_history_repo: SearchHistoryRepositoryPort,
    ):
        self._channel_port = channel_port
        self._channel_repo = channel_repo
        self._search_history_repo = search_history_repo

    def _resolve_channel(self, channel_id: str) -> int:
        """Resolve gemini_store_id to DB primary key.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
        """
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            raise ChannelNotFoundError(channel_id)

        meta = self._channel_repo.get_by_gemini_id(channel_id)
        if not meta:
            meta = self._channel_repo.create(
                gemini_store_id=channel_id,
                name=channel.display_name or "unknown",
            )
        return meta.id

    def _resolve_channel_locally(self, channel_id: str) -> int | None:
        """Resolve gemini_store_id to DB primary key using local DB only.

        Returns None if channel is not found locally (no external API call).
        Used for read-only operations to avoid external API dependency.
        """
        meta = self._channel_repo.get_by_gemini_id(channel_id)
        return meta.id if meta else None

    def _to_dto(self, history_dto, channel_id: str) -> SearchHistoryItemDTO:
        """Convert persistence DTO to application DTO."""
        return SearchHistoryItemDTO(
            id=history_dto.id,
            channel_id=channel_id,
            query=history_dto.query,
            search_count=history_dto.search_count,
            created_at=history_dto.created_at,
            last_searched_at=history_dto.last_searched_at,
        )

    # -- Get History ----------------------------------------------------------

    def get_history(
        self,
        channel_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchHistoryListDTO:
        """Get search history for a channel.

        Uses local DB only (no external API call) for resilience.
        Returns empty list if channel has no local record.
        """
        db_channel_id = self._resolve_channel_locally(channel_id)
        if db_channel_id is None:
            return SearchHistoryListDTO(history=[], total=0)

        history = self._search_history_repo.get_history(
            db_channel_id, limit=limit, offset=offset,
        )
        total = self._search_history_repo.count_history(db_channel_id)

        return SearchHistoryListDTO(
            history=[self._to_dto(h, channel_id) for h in history],
            total=total,
        )

    # -- Get Suggestions ------------------------------------------------------

    def get_suggestions(
        self,
        channel_id: str,
        prefix: str = "",
        limit: int = 10,
    ) -> SearchSuggestionListDTO:
        """Get search suggestions based on query prefix.

        Uses local DB only (no external API call) for resilience.
        """
        db_channel_id = self._resolve_channel_locally(channel_id)
        if db_channel_id is None:
            return SearchSuggestionListDTO(suggestions=[], query=prefix)

        suggestions = self._search_history_repo.get_suggestions(
            db_channel_id, prefix, limit=limit,
        )

        return SearchSuggestionListDTO(
            suggestions=[
                SearchSuggestionDTO(query=s.query, search_count=s.search_count)
                for s in suggestions
            ],
            query=prefix,
        )

    # -- Get Popular ----------------------------------------------------------

    def get_popular(
        self,
        channel_id: str,
        limit: int = 10,
    ) -> SearchSuggestionListDTO:
        """Get popular searches for a channel.

        Uses local DB only (no external API call) for resilience.
        """
        db_channel_id = self._resolve_channel_locally(channel_id)
        if db_channel_id is None:
            return SearchSuggestionListDTO(suggestions=[], query="")

        popular = self._search_history_repo.get_popular(db_channel_id, limit=limit)

        return SearchSuggestionListDTO(
            suggestions=[
                SearchSuggestionDTO(query=p.query, search_count=p.search_count)
                for p in popular
            ],
            query="",
        )

    # -- Delete Entry ---------------------------------------------------------

    def delete_entry(self, channel_id: str, history_id: int) -> bool:
        """Delete a specific search history entry. Returns False if not found.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
        """
        db_channel_id = self._resolve_channel(channel_id)

        history = self._search_history_repo.get_by_id(history_id)
        if not history or history.channel_id != db_channel_id:
            return False

        self._search_history_repo.delete(history_id)
        return True

    # -- Clear History --------------------------------------------------------

    def clear_history(self, channel_id: str) -> None:
        """Clear all search history for a channel.

        Raises:
            ChannelNotFoundError: If channel doesn't exist.
        """
        db_channel_id = self._resolve_channel(channel_id)
        self._search_history_repo.clear_channel_history(db_channel_id)
