# -*- coding: utf-8 -*-
"""Cache port.

This port defines the abstract interface for caching operations.
It allows the application layer to use caching without knowing
about the specific caching implementation (in-memory, Redis, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any


class CachePort(ABC):
    """Port for caching operations."""

    # ========== Chat Response Cache ==========

    @abstractmethod
    def get_chat_response(
        self,
        channel_id: str,
        query: str,
    ) -> dict[str, Any] | None:
        """Get cached chat response.

        Args:
            channel_id: The channel ID
            query: The user query

        Returns:
            Cached response dict or None if not found
        """
        ...

    @abstractmethod
    def set_chat_response(
        self,
        channel_id: str,
        query: str,
        response: dict[str, Any],
    ) -> None:
        """Cache a chat response.

        Args:
            channel_id: The channel ID
            query: The user query
            response: The response to cache
        """
        ...

    @abstractmethod
    def invalidate_chat_cache(self, channel_id: str) -> int:
        """Invalidate all chat cache entries for a channel.

        Args:
            channel_id: The channel ID

        Returns:
            Number of entries invalidated
        """
        ...

    # ========== Document List Cache ==========

    @abstractmethod
    def get_document_list(self, channel_id: str) -> list[dict[str, Any]] | None:
        """Get cached document list for a channel.

        Args:
            channel_id: The channel ID

        Returns:
            Cached document list or None if not found
        """
        ...

    @abstractmethod
    def set_document_list(
        self,
        channel_id: str,
        documents: list[dict[str, Any]],
    ) -> None:
        """Cache document list for a channel.

        Args:
            channel_id: The channel ID
            documents: The document list to cache
        """
        ...

    @abstractmethod
    def invalidate_document_cache(self, channel_id: str) -> bool:
        """Invalidate document cache for a channel.

        Args:
            channel_id: The channel ID

        Returns:
            True if entry was removed
        """
        ...

    # ========== Channel Info Cache ==========

    @abstractmethod
    def get_channel_info(self, channel_id: str) -> dict[str, Any] | None:
        """Get cached channel info.

        Args:
            channel_id: The channel ID

        Returns:
            Cached channel info or None if not found
        """
        ...

    @abstractmethod
    def set_channel_info(
        self,
        channel_id: str,
        info: dict[str, Any],
    ) -> None:
        """Cache channel info.

        Args:
            channel_id: The channel ID
            info: The channel info to cache
        """
        ...

    @abstractmethod
    def invalidate_channel_cache(self, channel_id: str) -> bool:
        """Invalidate channel cache.

        Args:
            channel_id: The channel ID

        Returns:
            True if entry was removed
        """
        ...

    # ========== Store List Cache ==========

    @abstractmethod
    def get_store_list(self) -> list[dict[str, Any]] | None:
        """Get cached store list.

        Returns:
            Cached store list or None if not found
        """
        ...

    @abstractmethod
    def set_store_list(self, stores: list[dict[str, Any]]) -> None:
        """Cache store list.

        Args:
            stores: The store list to cache
        """
        ...

    @abstractmethod
    def invalidate_store_cache(self) -> bool:
        """Invalidate store list cache.

        Returns:
            True if entry was removed
        """
        ...

    # ========== Cache Management ==========

    @abstractmethod
    def invalidate_channel(self, channel_id: str) -> dict[str, bool]:
        """Invalidate all caches related to a channel.

        Args:
            channel_id: The channel ID

        Returns:
            Dict indicating which caches were invalidated
        """
        ...

    @abstractmethod
    def clear_all(self) -> None:
        """Clear all caches."""
        ...

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        ...
