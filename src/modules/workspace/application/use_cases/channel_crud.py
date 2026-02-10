# -*- coding: utf-8 -*-
"""
Channel CRUD use case.

Extracts channel orchestration logic from the API router into the application layer.
The router becomes a thin controller handling only HTTP concerns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC

from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.document import DocumentPort
from src.shared.kernel.contracts.ports.persistence import (
    ChannelRepositoryPort,
    FavoriteRepositoryPort,
)
from src.shared.kernel.contracts.ports.cache import CachePort

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class ChannelDetailDTO:
    """Application-layer DTO for channel details."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    file_count: int = 0
    is_favorited: bool = False


@dataclass
class ChannelListResultDTO:
    """Result of listing channels."""

    channels: list[ChannelDetailDTO] = field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Use Case
# ---------------------------------------------------------------------------

class ChannelCrudUseCase:
    """Orchestrates channel CRUD operations.

    Encapsulates the business logic that was previously in the API router:
    channel creation, listing with caching/sorting/pagination, retrieval,
    update, and deletion.
    """

    def __init__(
        self,
        channel_port: ChannelPort,
        document_port: DocumentPort,
        channel_repo: ChannelRepositoryPort,
        fav_repo: FavoriteRepositoryPort,
        cache: CachePort,
    ):
        self._channel_port = channel_port
        self._document_port = document_port
        self._channel_repo = channel_repo
        self._fav_repo = fav_repo
        self._cache = cache

    # -- Create ---------------------------------------------------------------

    def create(self, name: str, description: str | None = None) -> ChannelDetailDTO:
        """Create a new channel.

        Args:
            name: Channel display name.
            description: Optional channel description.

        Returns:
            ChannelDetailDTO for the created channel.

        Raises:
            Exception: If channel creation fails in the external service.
        """
        channel = self._channel_port.create_channel(name)
        store_id = channel.name

        local = self._channel_repo.create(
            gemini_store_id=store_id,
            name=name,
            description=description,
        )

        self._cache.invalidate_store_cache()

        return ChannelDetailDTO(
            id=store_id,
            name=name,
            description=local.description if local else description,
            created_at=local.created_at if local else datetime.now(UTC),
            file_count=0,
        )

    # -- List -----------------------------------------------------------------

    def list(
        self,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> ChannelListResultDTO:
        """List channels with caching, sorting, and pagination.

        Args:
            limit: Max channels to return (None = all).
            offset: Number of channels to skip.
            sort_by: Sort field ("created_at" or "name").
            sort_order: "asc" or "desc".

        Returns:
            ChannelListResultDTO with paginated, sorted channel list.
        """
        stores = self._get_stores()
        favorited_ids = self._fav_repo.get_favorited_ids("channel")
        deleted_ids = self._channel_repo.get_deleted_store_ids()

        channels: list[ChannelDetailDTO] = []
        for store in stores:
            store_id = store["name"]

            if store_id in deleted_ids:
                continue

            local_meta = self._channel_repo.get_by_gemini_id(store_id)
            if local_meta and local_meta.is_deleted:
                continue

            if not local_meta:
                local_meta = self._channel_repo.create(
                    gemini_store_id=store_id,
                    name=store.get("display_name", ""),
                )

            try:
                files = self._document_port.list_documents(store_id)
                actual_file_count = len(files)
            except Exception:
                logger.warning(
                    "Failed to list documents for channel %s, using cached count",
                    store_id,
                )
                actual_file_count = local_meta.file_count if local_meta else 0

            if local_meta and local_meta.file_count != actual_file_count:
                self._channel_repo.update_stats(store_id, file_count=actual_file_count)

            channels.append(ChannelDetailDTO(
                id=store_id,
                name=store.get("display_name", ""),
                description=local_meta.description,
                created_at=local_meta.created_at,
                file_count=actual_file_count,
                is_favorited=store_id in favorited_ids,
            ))

        self._sort_channels(channels, sort_by, sort_order)

        total = len(channels)
        if offset:
            channels = channels[offset:]
        if limit:
            channels = channels[:limit]

        return ChannelListResultDTO(channels=channels, total=total)

    # -- Get ------------------------------------------------------------------

    def get(self, channel_id: str) -> ChannelDetailDTO | None:
        """Get a single channel by ID.

        Args:
            channel_id: The Gemini store ID.

        Returns:
            ChannelDetailDTO or None if not found / deleted.
        """
        local_meta = self._channel_repo.get_by_gemini_id(channel_id)
        if local_meta and local_meta.is_deleted:
            return None

        is_favorited = self._fav_repo.is_favorited("channel", channel_id)

        # Try cache
        cached = self._cache.get_channel_info(channel_id)
        if cached:
            self._channel_repo.touch(channel_id)
            created_at = cached.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            elif not isinstance(created_at, datetime):
                created_at = datetime.now(UTC)
            return ChannelDetailDTO(
                id=cached.get("id", channel_id),
                name=cached.get("name", ""),
                description=cached.get("description"),
                created_at=created_at,
                file_count=cached.get("file_count", 0),
                is_favorited=is_favorited,
            )

        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            return None

        files = self._document_port.list_documents(channel_id)
        actual_file_count = len(files)

        if not local_meta:
            local_meta = self._channel_repo.create(
                gemini_store_id=channel_id,
                name=channel.display_name,
            )

        local_meta = self._channel_repo.touch(channel_id)
        if local_meta and local_meta.file_count != actual_file_count:
            self._channel_repo.update_stats(channel_id, file_count=actual_file_count)
            local_meta = self._channel_repo.get_by_gemini_id(channel_id)

        dto = ChannelDetailDTO(
            id=channel.name,
            name=channel.display_name,
            description=local_meta.description if local_meta else None,
            created_at=local_meta.created_at if local_meta else datetime.now(UTC),
            file_count=actual_file_count,
            is_favorited=is_favorited,
        )

        # Populate cache
        self._cache.set_channel_info(channel_id, {
            "id": dto.id,
            "name": dto.name,
            "description": dto.description,
            "created_at": dto.created_at.isoformat() if dto.created_at else None,
            "file_count": dto.file_count,
        })

        return dto

    # -- Update ---------------------------------------------------------------

    def update(
        self,
        channel_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> ChannelDetailDTO | None:
        """Update a channel's metadata.

        Args:
            channel_id: The Gemini store ID.
            name: New name (optional).
            description: New description (optional).

        Returns:
            Updated ChannelDetailDTO or None if channel not found.
        """
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            return None

        local_meta = self._channel_repo.get_by_gemini_id(channel_id)

        if not local_meta:
            local_meta = self._channel_repo.create(
                gemini_store_id=channel_id,
                name=name or channel.display_name,
                description=description,
            )
        else:
            local_meta = self._channel_repo.update(
                gemini_store_id=channel_id,
                name=name,
                description=description,
            )

        self._cache.invalidate_channel_cache(channel_id)
        self._cache.invalidate_store_cache()

        return ChannelDetailDTO(
            id=channel_id,
            name=local_meta.name if local_meta else name or "",
            description=local_meta.description if local_meta else description,
            created_at=local_meta.created_at if local_meta else datetime.now(UTC),
            file_count=local_meta.file_count if local_meta else 0,
        )

    # -- Delete ---------------------------------------------------------------

    def delete(self, channel_id: str) -> bool:
        """Delete a channel permanently.

        Args:
            channel_id: The Gemini store ID.

        Returns:
            True if deleted, False if channel not found.

        Raises:
            RuntimeError: If the external service fails to delete.
        """
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            return False

        success = self._channel_port.delete_channel(channel_id, force=True)
        if not success:
            raise RuntimeError("Failed to delete channel from external service")

        self._channel_repo.delete(channel_id)
        self._cache.invalidate_channel(channel_id)
        return True

    # -- Helpers --------------------------------------------------------------

    def _get_stores(self) -> list[dict]:
        """Get store list from cache or API."""
        cached = self._cache.get_store_list()
        if cached is not None:
            return cached
        channels = self._channel_port.list_channels()
        stores = [{"name": c.name, "display_name": c.display_name} for c in channels]
        self._cache.set_store_list(stores)
        return stores

    @staticmethod
    def _sort_channels(
        channels: list[ChannelDetailDTO],
        sort_by: str,
        sort_order: str,
    ) -> None:
        """Sort channels in-place: favorited first, then by field."""

        def get_naive_ts(c: ChannelDetailDTO) -> datetime:
            ts = c.created_at
            if ts and ts.tzinfo is not None:
                return ts.replace(tzinfo=None)
            return ts if ts else datetime.min

        reverse = sort_order == "desc"
        if sort_by == "name":
            channels.sort(key=lambda c: c.name.lower(), reverse=reverse)
        else:
            channels.sort(key=lambda c: get_naive_ts(c), reverse=reverse)

        # Stable sort: favorited channels always come first
        channels.sort(key=lambda c: not c.is_favorited)
