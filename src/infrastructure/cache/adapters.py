# -*- coding: utf-8 -*-
"""Cache adapter that implements the CachePort.

This adapter wraps the existing CacheService and exposes it through
the application port interface.
"""

from typing import Any

from src.application.ports.cache import CachePort
from src.infrastructure.cache.cache_service import CacheService


class CacheAdapter(CachePort):
    """Adapter that implements CachePort using existing CacheService."""

    def __init__(self, cache_service: CacheService | None = None):
        """Initialize adapter.

        Args:
            cache_service: Optional CacheService instance. If not provided,
                          uses the global singleton.
        """
        if cache_service is None:
            from src.infrastructure.cache.cache_service import get_cache_service
            cache_service = get_cache_service()
        self._service = cache_service

    # ========== Chat Response Cache ==========

    def get_chat_response(
        self,
        channel_id: str,
        query: str,
    ) -> dict[str, Any] | None:
        return self._service.get_chat_response(channel_id, query)

    def set_chat_response(
        self,
        channel_id: str,
        query: str,
        response: dict[str, Any],
    ) -> None:
        self._service.set_chat_response(channel_id, query, response)

    def invalidate_chat_cache(self, channel_id: str) -> int:
        return self._service.invalidate_chat_cache(channel_id)

    # ========== Document List Cache ==========

    def get_document_list(self, channel_id: str) -> list[dict[str, Any]] | None:
        return self._service.get_document_list(channel_id)

    def set_document_list(
        self,
        channel_id: str,
        documents: list[dict[str, Any]],
    ) -> None:
        self._service.set_document_list(channel_id, documents)

    def invalidate_document_cache(self, channel_id: str) -> bool:
        return self._service.invalidate_document_cache(channel_id)

    # ========== Channel Info Cache ==========

    def get_channel_info(self, channel_id: str) -> dict[str, Any] | None:
        return self._service.get_channel_info(channel_id)

    def set_channel_info(
        self,
        channel_id: str,
        info: dict[str, Any],
    ) -> None:
        self._service.set_channel_info(channel_id, info)

    def invalidate_channel_cache(self, channel_id: str) -> bool:
        return self._service.invalidate_channel_cache(channel_id)

    # ========== Store List Cache ==========

    def get_store_list(self) -> list[dict[str, Any]] | None:
        return self._service.get_store_list()

    def set_store_list(self, stores: list[dict[str, Any]]) -> None:
        self._service.set_store_list(stores)

    def invalidate_store_cache(self) -> bool:
        return self._service.invalidate_store_cache()

    # ========== Cache Management ==========

    def invalidate_channel(self, channel_id: str) -> dict[str, bool]:
        return self._service.invalidate_channel(channel_id)

    def clear_all(self) -> None:
        self._service.clear_all()

    def get_stats(self) -> dict[str, Any]:
        return self._service.get_stats()
