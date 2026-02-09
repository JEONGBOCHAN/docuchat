# -*- coding: utf-8 -*-
"""Conversation Summary Port.

Defines the interface for generating incremental conversation summaries.
Used by the hybrid memory system to compress older conversation turns
into a rolling summary.
"""

from abc import ABC, abstractmethod


class ConversationSummaryPort(ABC):
    """Abstract port for conversation summary generation."""

    @abstractmethod
    def summarize_incremental(
        self,
        previous_summary: str,
        new_turns: list[dict[str, str]],
        max_tokens: int = 1200,
    ) -> str:
        """Generate an incremental summary by merging previous summary with new turns.

        Args:
            previous_summary: The existing rolling summary (empty string if first compaction).
            new_turns: List of new conversation turns [{"role": "user"/"assistant", "content": "..."}].
            max_tokens: Target maximum token count for the output summary.

        Returns:
            Updated rolling summary string.
        """
        ...
