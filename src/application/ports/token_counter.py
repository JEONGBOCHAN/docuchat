# -*- coding: utf-8 -*-
"""
Token Counter Port.

Defines the interface for token counting operations.
This port allows for real-time token counting during LLM streaming.
"""

from abc import ABC, abstractmethod


class TokenCounterPort(ABC):
    """Abstract port for token counting operations.

    This port enables real-time token counting during LLM streaming.
    Implementations can use various tokenizers (Gemini, tiktoken, etc.).

    Example:
        >>> counter = GeminiTokenCounterAdapter()
        >>> count = counter.count_tokens("Hello, world!")
        >>> print(count)  # e.g., 4
    """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in the given text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens in the text.
        """
        pass

    @abstractmethod
    def count_tokens_incremental(self, new_text: str, previous_count: int) -> int:
        """Count tokens incrementally for streaming scenarios.

        This method adds the token count of new_text to the previous count.
        Useful for accumulating token counts during streaming.

        Args:
            new_text: The new text chunk to count.
            previous_count: The previously accumulated token count.

        Returns:
            The updated total token count.
        """
        pass
