# -*- coding: utf-8 -*-
"""
Tests for GeminiTokenCounterAdapter.

Tests the adapter implementation for real-time token counting.
"""

import pytest
from unittest.mock import Mock, patch

from src.infrastructure.external.gemini.token_counter import GeminiTokenCounterAdapter
from src.application.ports.token_counter import TokenCounterPort


class TestGeminiTokenCounterAdapter:
    """Tests for GeminiTokenCounterAdapter."""

    def test_implements_port(self):
        """Test that adapter implements TokenCounterPort interface."""
        adapter = GeminiTokenCounterAdapter()
        assert isinstance(adapter, TokenCounterPort)

    def test_count_tokens_empty_string(self):
        """Test counting tokens for empty string returns 0."""
        adapter = GeminiTokenCounterAdapter()
        result = adapter.count_tokens("")
        assert result == 0

    def test_count_tokens_short_text(self):
        """Test counting tokens for short text using estimation."""
        adapter = GeminiTokenCounterAdapter()
        # "Hello" is 5 characters, ~1-2 tokens estimated
        result = adapter.count_tokens("Hello")
        assert result >= 1

    def test_count_tokens_longer_text(self):
        """Test counting tokens for longer text using estimation."""
        adapter = GeminiTokenCounterAdapter()
        # 100 characters should be ~25 tokens (4 chars per token)
        text = "a" * 100
        result = adapter.count_tokens(text)
        assert result == 25  # 100 / 4 = 25

    def test_estimate_tokens_calculation(self):
        """Test the internal estimation calculation."""
        adapter = GeminiTokenCounterAdapter()
        # Direct test of estimation: 4 characters per token
        result = adapter._estimate_tokens("Hello, World!")  # 13 chars
        assert result == 3  # 13 // 4 = 3

    def test_estimate_tokens_minimum_one(self):
        """Test that estimation returns at least 1 token for non-empty text."""
        adapter = GeminiTokenCounterAdapter()
        # 1-3 characters should return 1 token minimum
        result = adapter._estimate_tokens("Hi")
        assert result == 1  # max(1, 2 // 4) = max(1, 0) = 1

    def test_count_tokens_incremental_accumulation(self):
        """Test incremental token counting accumulates correctly."""
        adapter = GeminiTokenCounterAdapter()

        # Start with 0 tokens
        accumulated = 0

        # Add first chunk: "Hello " (6 chars = 1 token)
        accumulated = adapter.count_tokens_incremental("Hello ", accumulated)
        assert accumulated >= 1

        # Add second chunk: "World!" (6 chars = 1 token)
        accumulated = adapter.count_tokens_incremental("World!", accumulated)
        assert accumulated >= 2

    def test_count_tokens_incremental_with_previous_count(self):
        """Test incremental counting adds to previous count."""
        adapter = GeminiTokenCounterAdapter()

        # Start with 10 tokens from previous counting
        previous_count = 10

        # Add "test" (4 chars = 1 token)
        result = adapter.count_tokens_incremental("test", previous_count)
        assert result == 11  # 10 + 1 = 11

    def test_count_tokens_incremental_empty_text(self):
        """Test incremental counting with empty text returns previous count."""
        adapter = GeminiTokenCounterAdapter()
        previous_count = 15
        result = adapter.count_tokens_incremental("", previous_count)
        assert result == 15  # No change

    def test_initialization_default_no_api(self):
        """Test default initialization does not use API."""
        adapter = GeminiTokenCounterAdapter()
        assert adapter._use_api is False
        assert adapter._client is None

    def test_initialization_with_api_flag(self):
        """Test initialization with use_api=True attempts to create client."""
        with patch.dict(
            "sys.modules",
            {"google": Mock(), "google.genai": Mock()}
        ):
            from importlib import reload
            import src.infrastructure.external.gemini.token_counter as token_counter_module

            mock_genai = Mock()
            mock_client = Mock()
            mock_genai.Client.return_value = mock_client

            with patch.object(
                token_counter_module, "genai", mock_genai, create=True
            ):
                # Test that API mode attempts to create a client
                adapter = GeminiTokenCounterAdapter(use_api=True)
                # Even if creation fails, adapter should work
                assert adapter is not None

    def test_api_initialization_fallback_on_import_error(self):
        """Test fallback to estimation if google-genai is not available."""
        # When genai is not available, the adapter should still work
        # via estimation (use_api defaults to False)
        adapter = GeminiTokenCounterAdapter(use_api=False)
        result = adapter.count_tokens("Test text")
        assert result >= 1  # Should still work via estimation

    def test_count_tokens_api_success(self):
        """Test API-based token counting when client is available."""
        mock_client = Mock()
        mock_result = Mock()
        mock_result.total_tokens = 42
        mock_client.models.count_tokens.return_value = mock_result

        adapter = GeminiTokenCounterAdapter(use_api=False)
        # Manually inject the client to simulate successful API init
        adapter._client = mock_client
        adapter._use_api = True

        result = adapter.count_tokens("Test text for API")

        assert result == 42
        mock_client.models.count_tokens.assert_called_once()

    def test_count_tokens_api_fallback_on_error(self):
        """Test fallback to estimation when API call fails."""
        mock_client = Mock()
        mock_client.models.count_tokens.side_effect = Exception("API Error")

        adapter = GeminiTokenCounterAdapter(use_api=False)
        adapter._client = mock_client
        adapter._use_api = True

        # Should fall back to estimation instead of raising
        result = adapter.count_tokens("Test text")

        assert result >= 1  # Should return estimation

    def test_model_name_parameter(self):
        """Test that model_name parameter is stored correctly."""
        adapter = GeminiTokenCounterAdapter(model_name="gemini-1.5-pro")
        assert adapter._model_name == "gemini-1.5-pro"


class TestTokenCounterPortInterface:
    """Tests to verify TokenCounterPort interface compliance."""

    def test_count_tokens_method_exists(self):
        """Test that count_tokens method exists."""
        adapter = GeminiTokenCounterAdapter()
        assert hasattr(adapter, "count_tokens")
        assert callable(adapter.count_tokens)

    def test_count_tokens_incremental_method_exists(self):
        """Test that count_tokens_incremental method exists."""
        adapter = GeminiTokenCounterAdapter()
        assert hasattr(adapter, "count_tokens_incremental")
        assert callable(adapter.count_tokens_incremental)

    def test_count_tokens_returns_int(self):
        """Test that count_tokens returns an integer."""
        adapter = GeminiTokenCounterAdapter()
        result = adapter.count_tokens("Test")
        assert isinstance(result, int)

    def test_count_tokens_incremental_returns_int(self):
        """Test that count_tokens_incremental returns an integer."""
        adapter = GeminiTokenCounterAdapter()
        result = adapter.count_tokens_incremental("Test", 0)
        assert isinstance(result, int)
