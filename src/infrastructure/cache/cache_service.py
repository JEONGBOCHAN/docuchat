# -*- coding: utf-8 -*-
"""Caching service for performance optimization."""

import hashlib
import json
from datetime import datetime, UTC
from functools import lru_cache
from typing import Any, TypeVar, Generic

from cachetools import TTLCache

T = TypeVar("T")


class CacheTTL:
    """Cache TTL constants in seconds."""

    CHAT_RESPONSE = 3600  # 1 hour
    DOCUMENT_LIST = 300  # 5 minutes
    CHANNEL_INFO = 600  # 10 minutes
    STORE_LIST = 300  # 5 minutes


class CacheService:
    """Service for managing application caches."""

    def __init__(
        self,
        chat_maxsize: int = 1000,
        document_maxsize: int = 500,
        channel_maxsize: int = 200,
    ):
        """Initialize cache service with TTL caches.

        Args:
            chat_maxsize: Maximum number of chat response cache entries
            document_maxsize: Maximum number of document list cache entries
            channel_maxsize: Maximum number of channel info cache entries
        """
        # Chat response cache: key = hash(channel_id + query)
        self._chat_cache: TTLCache = TTLCache(
            maxsize=chat_maxsize,
            ttl=CacheTTL.CHAT_RESPONSE,
        )

        # Document list cache: key = channel_id
        self._document_cache: TTLCache = TTLCache(
            maxsize=document_maxsize,
            ttl=CacheTTL.DOCUMENT_LIST,
        )

        # Channel info cache: key = channel_id
        self._channel_cache: TTLCache = TTLCache(
            maxsize=channel_maxsize,
            ttl=CacheTTL.CHANNEL_INFO,
        )

        # Store list cache: single entry
        self._store_cache: TTLCache = TTLCache(
            maxsize=10,
            ttl=CacheTTL.STORE_LIST,
        )

        # Cache statistics
        self._stats = {
            "chat": {"hits": 0, "misses": 0},
            "document": {"hits": 0, "misses": 0},
            "channel": {"hits": 0, "misses": 0},
            "store": {"hits": 0, "misses": 0},
        }

    # ========== Cache Key Generation ==========

    @staticmethod
    def _generate_chat_key(channel_id: str, query: str) -> str:
        """Generate cache key for chat response.

        Args:
            channel_id: The channel ID
            query: The user query

        Returns:
            Hash-based cache key
        """
        content = f"{channel_id}:{query.strip().lower()}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    # ========== Chat Response Cache ==========

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
        key = self._generate_chat_key(channel_id, query)
        result = self._chat_cache.get(key)

        if result is not None:
            self._stats["chat"]["hits"] += 1
        else:
            self._stats["chat"]["misses"] += 1

        return result

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
        key = self._generate_chat_key(channel_id, query)
        self._chat_cache[key] = {
            **response,
            "_cached_at": datetime.now(UTC).isoformat(),
        }

    def invalidate_chat_cache(self, channel_id: str) -> int:
        """Invalidate all chat cache entries for a channel.

        Called when documents in a channel are modified.

        Args:
            channel_id: The channel ID

        Returns:
            Number of entries invalidated
        """
        keys_to_remove = [
            key for key in self._chat_cache.keys()
            if key.startswith(channel_id[:16])  # Prefix match
        ]

        # Since we can't easily match by channel_id in hash keys,
        # we'll clear all entries for simplicity.
        # In production, consider using a prefix-based key structure.
        count = len(self._chat_cache)
        self._chat_cache.clear()
        return count

    # ========== Document List Cache ==========

    def get_document_list(self, channel_id: str) -> list[dict[str, Any]] | None:
        """Get cached document list for a channel.

        Args:
            channel_id: The channel ID

        Returns:
            Cached document list or None if not found
        """
        result = self._document_cache.get(channel_id)

        if result is not None:
            self._stats["document"]["hits"] += 1
        else:
            self._stats["document"]["misses"] += 1

        return result

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
        self._document_cache[channel_id] = documents

    def invalidate_document_cache(self, channel_id: str) -> bool:
        """Invalidate document cache for a channel.

        Args:
            channel_id: The channel ID

        Returns:
            True if entry was removed
        """
        if channel_id in self._document_cache:
            del self._document_cache[channel_id]
            return True
        return False

    # ========== Channel Info Cache ==========

    def get_channel_info(self, channel_id: str) -> dict[str, Any] | None:
        """Get cached channel info.

        Args:
            channel_id: The channel ID

        Returns:
            Cached channel info or None if not found
        """
        result = self._channel_cache.get(channel_id)

        if result is not None:
            self._stats["channel"]["hits"] += 1
        else:
            self._stats["channel"]["misses"] += 1

        return result

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
        self._channel_cache[channel_id] = info

    def invalidate_channel_cache(self, channel_id: str) -> bool:
        """Invalidate channel cache.

        Args:
            channel_id: The channel ID

        Returns:
            True if entry was removed
        """
        if channel_id in self._channel_cache:
            del self._channel_cache[channel_id]
            return True
        return False

    # ========== Store List Cache ==========

    def get_store_list(self) -> list[dict[str, Any]] | None:
        """Get cached store list.

        Returns:
            Cached store list or None if not found
        """
        result = self._store_cache.get("stores")

        if result is not None:
            self._stats["store"]["hits"] += 1
        else:
            self._stats["store"]["misses"] += 1

        return result

    def set_store_list(self, stores: list[dict[str, Any]]) -> None:
        """Cache store list.

        Args:
            stores: The store list to cache
        """
        self._store_cache["stores"] = stores

    def invalidate_store_cache(self) -> bool:
        """Invalidate store list cache.

        Returns:
            True if entry was removed
        """
        if "stores" in self._store_cache:
            del self._store_cache["stores"]
            return True
        return False

    # ========== Cache Management ==========

    def invalidate_channel(self, channel_id: str) -> dict[str, bool]:
        """Invalidate all caches related to a channel.

        Called when a channel or its documents are modified.

        Args:
            channel_id: The channel ID

        Returns:
            Dict indicating which caches were invalidated
        """
        return {
            "chat": self.invalidate_chat_cache(channel_id) > 0,
            "document": self.invalidate_document_cache(channel_id),
            "channel": self.invalidate_channel_cache(channel_id),
            "store": self.invalidate_store_cache(),
        }

    def clear_all(self) -> None:
        """Clear all caches."""
        self._chat_cache.clear()
        self._document_cache.clear()
        self._channel_cache.clear()
        self._store_cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        return {
            "chat": {
                **self._stats["chat"],
                "size": len(self._chat_cache),
                "maxsize": self._chat_cache.maxsize,
                "ttl": CacheTTL.CHAT_RESPONSE,
            },
            "document": {
                **self._stats["document"],
                "size": len(self._document_cache),
                "maxsize": self._document_cache.maxsize,
                "ttl": CacheTTL.DOCUMENT_LIST,
            },
            "channel": {
                **self._stats["channel"],
                "size": len(self._channel_cache),
                "maxsize": self._channel_cache.maxsize,
                "ttl": CacheTTL.CHANNEL_INFO,
            },
            "store": {
                **self._stats["store"],
                "size": len(self._store_cache),
                "maxsize": self._store_cache.maxsize,
                "ttl": CacheTTL.STORE_LIST,
            },
        }

    def get_hit_rate(self, cache_type: str) -> float:
        """Calculate hit rate for a cache type.

        Args:
            cache_type: One of 'chat', 'document', 'channel', 'store'

        Returns:
            Hit rate as percentage (0-100)
        """
        stats = self._stats.get(cache_type, {"hits": 0, "misses": 0})
        total = stats["hits"] + stats["misses"]
        if total == 0:
            return 0.0
        return (stats["hits"] / total) * 100


# Global cache instance
_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Get the global cache service instance.

    Returns:
        CacheService singleton instance
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def reset_cache_service() -> None:
    """Reset the global cache service (for testing)."""
    global _cache_service
    if _cache_service is not None:
        _cache_service.clear_all()
    _cache_service = None
