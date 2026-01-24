# -*- coding: utf-8 -*-
"""Tests for cache service."""

import time
import pytest

from src.infrastructure.cache.cache_service import (
    CacheService,
    CacheTTL,
    get_cache_service,
    reset_cache_service,
)


class TestCacheService:
    """Tests for CacheService class."""

    def setup_method(self):
        """Reset cache before each test."""
        reset_cache_service()
        self.cache = CacheService()

    def teardown_method(self):
        """Clean up after each test."""
        reset_cache_service()

    # ========== Chat Response Cache Tests ==========

    def test_chat_cache_set_and_get(self):
        """Test setting and getting chat response from cache."""
        channel_id = "test-channel"
        query = "What is the weather?"
        response = {"response": "It's sunny", "sources": []}

        # Initially not cached
        assert self.cache.get_chat_response(channel_id, query) is None

        # Set cache
        self.cache.set_chat_response(channel_id, query, response)

        # Get cached response
        cached = self.cache.get_chat_response(channel_id, query)
        assert cached is not None
        assert cached["response"] == "It's sunny"
        assert "_cached_at" in cached

    def test_chat_cache_case_insensitive_query(self):
        """Test that cache keys are case-insensitive for queries."""
        channel_id = "test-channel"
        response = {"response": "Answer", "sources": []}

        self.cache.set_chat_response(channel_id, "Hello World", response)

        # Should match with different case
        cached = self.cache.get_chat_response(channel_id, "hello world")
        assert cached is not None
        assert cached["response"] == "Answer"

    def test_chat_cache_invalidation(self):
        """Test invalidating chat cache."""
        channel_id = "test-channel"
        self.cache.set_chat_response(channel_id, "query1", {"response": "r1"})
        self.cache.set_chat_response(channel_id, "query2", {"response": "r2"})

        # Invalidate
        count = self.cache.invalidate_chat_cache(channel_id)
        assert count > 0

        # Cache should be empty
        assert self.cache.get_chat_response(channel_id, "query1") is None

    # ========== Document List Cache Tests ==========

    def test_document_cache_set_and_get(self):
        """Test setting and getting document list from cache."""
        channel_id = "test-channel"
        documents = [
            {"id": "doc1", "filename": "test.pdf"},
            {"id": "doc2", "filename": "test2.pdf"},
        ]

        # Initially not cached
        assert self.cache.get_document_list(channel_id) is None

        # Set cache
        self.cache.set_document_list(channel_id, documents)

        # Get cached list
        cached = self.cache.get_document_list(channel_id)
        assert cached is not None
        assert len(cached) == 2
        assert cached[0]["filename"] == "test.pdf"

    def test_document_cache_invalidation(self):
        """Test invalidating document cache."""
        channel_id = "test-channel"
        self.cache.set_document_list(channel_id, [{"id": "doc1"}])

        # Invalidate
        result = self.cache.invalidate_document_cache(channel_id)
        assert result is True

        # Cache should be empty
        assert self.cache.get_document_list(channel_id) is None

        # Invalidating non-existent key returns False
        result = self.cache.invalidate_document_cache("non-existent")
        assert result is False

    # ========== Channel Info Cache Tests ==========

    def test_channel_cache_set_and_get(self):
        """Test setting and getting channel info from cache."""
        channel_id = "test-channel"
        info = {"id": channel_id, "name": "Test Channel", "file_count": 5}

        # Initially not cached
        assert self.cache.get_channel_info(channel_id) is None

        # Set cache
        self.cache.set_channel_info(channel_id, info)

        # Get cached info
        cached = self.cache.get_channel_info(channel_id)
        assert cached is not None
        assert cached["name"] == "Test Channel"
        assert cached["file_count"] == 5

    def test_channel_cache_invalidation(self):
        """Test invalidating channel cache."""
        channel_id = "test-channel"
        self.cache.set_channel_info(channel_id, {"id": channel_id})

        # Invalidate
        result = self.cache.invalidate_channel_cache(channel_id)
        assert result is True

        # Cache should be empty
        assert self.cache.get_channel_info(channel_id) is None

    # ========== Store List Cache Tests ==========

    def test_store_cache_set_and_get(self):
        """Test setting and getting store list from cache."""
        stores = [
            {"name": "store1", "display_name": "Store 1"},
            {"name": "store2", "display_name": "Store 2"},
        ]

        # Initially not cached
        assert self.cache.get_store_list() is None

        # Set cache
        self.cache.set_store_list(stores)

        # Get cached list
        cached = self.cache.get_store_list()
        assert cached is not None
        assert len(cached) == 2

    def test_store_cache_invalidation(self):
        """Test invalidating store cache."""
        self.cache.set_store_list([{"name": "store1"}])

        # Invalidate
        result = self.cache.invalidate_store_cache()
        assert result is True

        # Cache should be empty
        assert self.cache.get_store_list() is None

    # ========== Combined Invalidation Tests ==========

    def test_invalidate_channel_all_caches(self):
        """Test invalidating all caches for a channel."""
        channel_id = "test-channel"

        # Set various caches
        self.cache.set_chat_response(channel_id, "query", {"response": "answer"})
        self.cache.set_document_list(channel_id, [{"id": "doc1"}])
        self.cache.set_channel_info(channel_id, {"id": channel_id})
        self.cache.set_store_list([{"name": channel_id}])

        # Invalidate all
        result = self.cache.invalidate_channel(channel_id)

        assert result["chat"] is True
        assert result["document"] is True
        assert result["channel"] is True
        assert result["store"] is True

    def test_clear_all(self):
        """Test clearing all caches."""
        # Set various caches
        self.cache.set_chat_response("ch1", "q1", {"response": "r1"})
        self.cache.set_document_list("ch1", [{"id": "doc1"}])
        self.cache.set_channel_info("ch1", {"id": "ch1"})
        self.cache.set_store_list([{"name": "store1"}])

        # Clear all
        self.cache.clear_all()

        # All caches should be empty
        assert self.cache.get_chat_response("ch1", "q1") is None
        assert self.cache.get_document_list("ch1") is None
        assert self.cache.get_channel_info("ch1") is None
        assert self.cache.get_store_list() is None

    # ========== Statistics Tests ==========

    def test_cache_stats(self):
        """Test cache statistics."""
        channel_id = "test-channel"

        # Generate some hits and misses
        self.cache.get_chat_response(channel_id, "q1")  # miss
        self.cache.set_chat_response(channel_id, "q1", {"response": "r1"})
        self.cache.get_chat_response(channel_id, "q1")  # hit

        stats = self.cache.get_stats()

        assert "chat" in stats
        assert stats["chat"]["hits"] == 1
        assert stats["chat"]["misses"] == 1
        assert stats["chat"]["ttl"] == CacheTTL.CHAT_RESPONSE

    def test_hit_rate(self):
        """Test hit rate calculation."""
        channel_id = "test-channel"

        # Initial hit rate should be 0
        assert self.cache.get_hit_rate("chat") == 0.0

        # Generate stats
        self.cache.get_chat_response(channel_id, "q1")  # miss
        self.cache.set_chat_response(channel_id, "q1", {"response": "r1"})
        self.cache.get_chat_response(channel_id, "q1")  # hit
        self.cache.get_chat_response(channel_id, "q1")  # hit

        # Should be 66.67% (2 hits / 3 total)
        hit_rate = self.cache.get_hit_rate("chat")
        assert abs(hit_rate - 66.67) < 1  # Allow small floating point error


class TestCacheServiceSingleton:
    """Tests for cache service singleton pattern."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_cache_service()

    def teardown_method(self):
        """Clean up after each test."""
        reset_cache_service()

    def test_get_cache_service_singleton(self):
        """Test that get_cache_service returns the same instance."""
        service1 = get_cache_service()
        service2 = get_cache_service()

        assert service1 is service2

    def test_reset_cache_service(self):
        """Test resetting the cache service singleton."""
        service1 = get_cache_service()
        service1.set_chat_response("ch1", "q1", {"response": "r1"})

        reset_cache_service()

        service2 = get_cache_service()
        assert service1 is not service2
        assert service2.get_chat_response("ch1", "q1") is None


class TestCacheTTL:
    """Tests for cache TTL values."""

    def test_ttl_constants(self):
        """Test that TTL constants are properly defined."""
        assert CacheTTL.CHAT_RESPONSE == 3600  # 1 hour
        assert CacheTTL.DOCUMENT_LIST == 300  # 5 minutes
        assert CacheTTL.CHANNEL_INFO == 600  # 10 minutes
        assert CacheTTL.STORE_LIST == 300  # 5 minutes
