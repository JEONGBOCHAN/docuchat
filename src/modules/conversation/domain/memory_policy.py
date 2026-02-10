# -*- coding: utf-8 -*-
"""Conversation memory compaction domain policy.

Pure functions for deciding when to compact conversation history.
No external dependencies — only stdlib.
"""


def should_compact(
    new_message_count: int,
    trigger_turns: int = 30,
) -> bool:
    """Determine whether conversation compaction should trigger.

    Compaction fires when the number of un-summarized messages reaches
    or exceeds the trigger threshold.

    Args:
        new_message_count: Number of messages accumulated since last compaction.
        trigger_turns: Threshold number of turns to trigger compaction.

    Returns:
        True if compaction should run.
    """
    return new_message_count >= trigger_turns


# Rough token-per-character ratio for fallback estimation
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str, exact_count: int | None = None) -> int:
    """Estimate token count for a piece of text.

    Uses exact count if provided (from a real tokenizer), otherwise
    falls back to a character-based heuristic.

    Args:
        text: The text to count tokens for.
        exact_count: Pre-computed exact token count, if available.

    Returns:
        Estimated token count (at least 1).
    """
    if exact_count is not None:
        return exact_count
    return max(1, len(text) // CHARS_PER_TOKEN)
