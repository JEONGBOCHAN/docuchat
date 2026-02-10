# -*- coding: utf-8 -*-
"""
Gemini Token Counter Adapter.

Implements TokenCounterPort using Google Gemini's tokenizer.
Falls back to character-based estimation if local tokenizer is unavailable.
"""

import logging
from typing import Any

from src.application.ports.token_counter import TokenCounterPort
from src.core.config import get_settings, GeminiModels

logger = logging.getLogger(__name__)


class GeminiTokenCounterAdapter(TokenCounterPort):
    """Token counter adapter using Gemini's tokenizer.

    Uses google.genai's count_tokens method for accurate token counting.
    Falls back to character-based estimation if the API is unavailable.

    Example:
        >>> counter = GeminiTokenCounterAdapter()
        >>> count = counter.count_tokens("Hello, world!")
        >>> print(count)  # e.g., 4
    """

    def __init__(
        self,
        model_name: str = GeminiModels.DEFAULT,
        use_api: bool = False,
    ) -> None:
        """Initialize the token counter.

        Args:
            model_name: The Gemini model to use for tokenization.
            use_api: If True, use API-based counting (slower but accurate).
                    If False, use character-based estimation (faster).
        """
        self._model_name = model_name
        self._use_api = use_api
        self._client: Any = None
        self._settings = get_settings()

        # Character-to-token ratio for estimation
        # Gemini models typically have ~4 characters per token for English text
        self._chars_per_token = 4

        # Client initialization is deferred to first API call (lazy init)

    def _init_client(self) -> None:
        """Initialize the Gemini client for API-based token counting."""
        try:
            from google import genai
            self._client = genai.Client(api_key=self._settings.google_api_key)
            logger.debug("Gemini client initialized for token counting")
        except ImportError:
            logger.warning(
                "google-genai not available, falling back to estimation"
            )
            self._use_api = False
        except Exception as e:
            logger.warning(
                f"Failed to initialize Gemini client: {e}, "
                "falling back to estimation"
            )
            self._use_api = False

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text.

        Uses API-based counting if enabled and available,
        otherwise falls back to character-based estimation.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens in the text.
        """
        if not text:
            return 0

        if self._use_api:
            return self._count_tokens_api(text)
        return self._estimate_tokens(text)

    def _count_tokens_api(self, text: str) -> int:
        """Count tokens using the Gemini API.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens according to the API.
        """
        if self._client is None:
            self._init_client()
        if not self._use_api or self._client is None:
            return self._estimate_tokens(text)
        try:
            result = self._client.models.count_tokens(
                model=self._model_name,
                contents=text,
            )
            return result.total_tokens
        except Exception as e:
            logger.warning(
                f"API token counting failed: {e}, using estimation"
            )
            return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count based on character count.

        This is a simple heuristic that works reasonably well for
        mixed English/code content. The ratio of ~4 characters per
        token is typical for Gemini models.

        Args:
            text: The text to estimate tokens for.

        Returns:
            Estimated number of tokens.
        """
        return max(1, len(text) // self._chars_per_token)

    def count_tokens_incremental(self, new_text: str, previous_count: int) -> int:
        """Count tokens incrementally for streaming scenarios.

        Args:
            new_text: The new text chunk to count.
            previous_count: The previously accumulated token count.

        Returns:
            The updated total token count.
        """
        new_tokens = self.count_tokens(new_text)
        return previous_count + new_tokens
