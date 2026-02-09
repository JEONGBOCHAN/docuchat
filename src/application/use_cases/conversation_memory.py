# -*- coding: utf-8 -*-
"""Conversation Memory Service.

Assembles LangGraph invoke messages from:
  L3: rolling summary (compressed older context)
  L2: recent raw turns from DB
  L0: current user query

Provides token-budget-based trimming and triggers summary compaction
when enough new turns have accumulated.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.ports.persistence import (
        ChatHistoryRepositoryPort,
        ChatSessionMemoryRepositoryPort,
    )
    from src.application.ports.conversation_summary import ConversationSummaryPort
    from src.application.ports.token_counter import TokenCounterPort

logger = logging.getLogger(__name__)

# Rough token-per-character ratio for estimation when no counter is available
_CHARS_PER_TOKEN = 4


class ConversationMemoryService:
    """Assembles context messages for LangGraph invoke using hybrid memory.

    Memory layers:
      L1: LangGraph checkpointer (managed externally)
      L2: Session raw message log (ChatHistoryRepositoryPort)
      L3: Rolling summary (ChatSessionMemoryRepositoryPort)
    """

    def __init__(
        self,
        chat_history_repo: ChatHistoryRepositoryPort,
        session_memory_repo: ChatSessionMemoryRepositoryPort,
        summary_port: ConversationSummaryPort,
        token_counter: TokenCounterPort | None = None,
        compaction_trigger_turns: int = 30,
        compaction_target_tokens: int = 1200,
    ):
        self._chat_history = chat_history_repo
        self._session_memory = session_memory_repo
        self._summary_port = summary_port
        self._token_counter = token_counter
        self._compaction_trigger_turns = compaction_trigger_turns
        self._compaction_target_tokens = compaction_target_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_context_messages(
        self,
        session_id: str,
        query: str,
        budget: int = 12000,
        recent_turns: int = 80,
    ) -> list[tuple[str, str]]:
        """Build messages list for LangGraph invoke.

        Returns:
            List of (role, content) tuples ready for invoke({"messages": ...}).
        """
        # 1. Load rolling summary (L3)
        memory_dto = self._session_memory.get_by_session_id(session_id)
        summary = memory_dto.rolling_summary if memory_dto else ""

        # 2. Load recent raw messages (L2)
        raw_messages = self._chat_history.get_session_history(
            session_id, limit=recent_turns
        )
        recent = [{"role": msg.role, "content": msg.content} for msg in raw_messages]

        # 3. Assemble: summary block + recent turns + current query
        messages: list[tuple[str, str]] = []

        # Add summary as a system-style context block
        if summary:
            messages.append((
                "user",
                f"[Conversation Memory]\n{summary}\n[End of Conversation Memory]"
            ))
            messages.append((
                "assistant",
                "I'll keep this conversation context in mind."
            ))

        # Add recent messages
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(("user", content))
            else:
                messages.append(("assistant", content))

        # Add current query
        messages.append(("user", query))

        # 4. Trim from oldest recent messages if over budget
        messages = self._trim_to_budget(messages, budget, has_summary=bool(summary))

        return messages

    def maybe_compact(self, session_id: str) -> None:
        """Trigger compaction if enough new turns have accumulated.

        Compaction takes un-summarized older turns and feeds them to
        the summary port to produce an updated rolling summary.
        """
        memory_dto = self._session_memory.get_by_session_id(session_id)
        last_compacted_id = (
            memory_dto.last_compacted_message_id if memory_dto else None
        )
        previous_summary = memory_dto.rolling_summary if memory_dto else ""

        # Get all session messages (limit=0 bypasses context_window default)
        all_messages = self._chat_history.get_session_history(session_id, limit=0)
        if not all_messages:
            return

        # Find un-compacted messages
        if last_compacted_id is not None:
            new_messages = [m for m in all_messages if m.id > last_compacted_id]
        else:
            new_messages = list(all_messages)

        # Check trigger threshold
        if len(new_messages) < self._compaction_trigger_turns:
            return

        logger.info(
            "Compacting session %s: %d new messages (threshold=%d)",
            session_id, len(new_messages), self._compaction_trigger_turns,
        )

        # Build turns for summarization
        new_turns = [
            {"role": msg.role, "content": msg.content}
            for msg in new_messages
        ]

        # Generate updated summary
        updated_summary = self._summary_port.summarize_incremental(
            previous_summary=previous_summary,
            new_turns=new_turns,
            max_tokens=self._compaction_target_tokens,
        )

        # Persist
        last_id = new_messages[-1].id if new_messages else last_compacted_id
        self._session_memory.upsert(
            session_id=session_id,
            rolling_summary=updated_summary,
            last_compacted_message_id=last_id,
            increment_compaction=True,
        )

        logger.info(
            "Compaction complete for session %s: summary length=%d chars, last_id=%s",
            session_id, len(updated_summary), last_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        if self._token_counter:
            return self._token_counter.count_tokens(text)
        return max(1, len(text) // _CHARS_PER_TOKEN)

    def _messages_token_count(self, messages: list[tuple[str, str]]) -> int:
        """Count total tokens across all messages."""
        return sum(self._estimate_tokens(content) for _, content in messages)

    def _trim_to_budget(
        self,
        messages: list[tuple[str, str]],
        budget: int,
        has_summary: bool,
    ) -> list[tuple[str, str]]:
        """Trim oldest recent messages to fit within token budget.

        Preserves: summary block (first 2 msgs if has_summary) + current query (last msg).
        Trims: recent messages from the oldest end.
        """
        total_tokens = self._messages_token_count(messages)
        if total_tokens <= budget:
            return messages

        # Separate protected and trimmable sections
        protected_start = 2 if has_summary else 0
        protected_end = 1  # current query (last message)

        head = messages[:protected_start]
        middle = messages[protected_start:-protected_end] if protected_end else messages[protected_start:]
        tail = messages[-protected_end:] if protected_end else []

        # Remove from the front of middle (oldest messages)
        while middle and self._messages_token_count(head + middle + tail) > budget:
            middle.pop(0)

        return head + middle + tail
