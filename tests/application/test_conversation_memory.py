# -*- coding: utf-8 -*-
"""Tests for ConversationMemoryService."""

from dataclasses import dataclass
from datetime import datetime, UTC
from unittest.mock import MagicMock

import pytest

from src.shared.kernel.contracts.ports.conversation_summary import SummaryResult
from src.modules.conversation.application.use_cases.conversation_memory import ConversationMemoryService


@dataclass
class FakeMessageDTO:
    """Minimal message DTO for testing."""
    id: int
    role: str
    content: str
    channel_id: int = 1
    session_id: int | None = None
    sources: list = None
    created_at: datetime = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = []
        if self.created_at is None:
            self.created_at = datetime.now(UTC)


@dataclass
class FakeMemoryDTO:
    """Minimal session memory DTO for testing."""
    id: int = 1
    session_id: int = 1
    rolling_summary: str = ""
    last_compacted_message_id: int | None = None
    total_compactions: int = 0
    updated_at: datetime = None
    version: int = 1

    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = datetime.now(UTC)


@pytest.fixture
def chat_history_repo():
    return MagicMock()


@pytest.fixture
def session_memory_repo():
    return MagicMock()


@pytest.fixture
def summary_port():
    return MagicMock()


@pytest.fixture
def token_counter():
    counter = MagicMock()
    # Simulate ~1 token per 4 chars
    counter.count_tokens.side_effect = lambda text: max(1, len(text) // 4)
    return counter


@pytest.fixture
def service(chat_history_repo, session_memory_repo, summary_port, token_counter):
    return ConversationMemoryService(
        chat_history_repo=chat_history_repo,
        session_memory_repo=session_memory_repo,
        summary_port=summary_port,
        token_counter=token_counter,
        compaction_trigger_turns=5,
        compaction_target_tokens=200,
    )


class TestBuildContextMessages:
    """Tests for build_context_messages."""

    def test_basic_no_summary_no_history(self, service, session_memory_repo, chat_history_repo):
        """With no summary and no history, returns just the query."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_session_history.return_value = []

        messages = service.build_context_messages("sess_1", "Hello", budget=5000)

        assert len(messages) == 1
        assert messages[0] == ("user", "Hello")

    def test_with_history_no_summary(self, service, session_memory_repo, chat_history_repo):
        """History messages are included before query."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_session_history.return_value = [
            FakeMessageDTO(id=1, role="user", content="What is Python?"),
            FakeMessageDTO(id=2, role="assistant", content="A programming language."),
        ]

        messages = service.build_context_messages("sess_1", "Tell me more", budget=50000)

        assert len(messages) == 3
        assert messages[0] == ("user", "What is Python?")
        assert messages[1] == ("assistant", "A programming language.")
        assert messages[2] == ("user", "Tell me more")

    def test_with_summary_and_history(self, service, session_memory_repo, chat_history_repo):
        """Summary is prepended as context block."""
        session_memory_repo.get_by_session_id.return_value = FakeMemoryDTO(
            rolling_summary="### Facts\n- User wants Python tutorials"
        )
        chat_history_repo.get_session_history.return_value = [
            FakeMessageDTO(id=5, role="user", content="Show me examples"),
        ]

        messages = service.build_context_messages("sess_1", "More examples?", budget=50000)

        # summary block (2) + history (1) + query (1) = 4
        assert len(messages) == 4
        assert "Conversation Memory" in messages[0][1]
        assert messages[1] == ("assistant", "I'll keep this conversation context in mind.")
        assert messages[2] == ("user", "Show me examples")
        assert messages[3] == ("user", "More examples?")

    def test_budget_trimming(self, service, session_memory_repo, chat_history_repo, token_counter):
        """Messages exceeding budget are trimmed from oldest."""
        session_memory_repo.get_by_session_id.return_value = None
        # Create many messages that exceed budget
        history = [
            FakeMessageDTO(id=i, role="user" if i % 2 == 0 else "assistant", content="x" * 200)
            for i in range(20)
        ]
        chat_history_repo.get_session_history.return_value = history

        messages = service.build_context_messages("sess_1", "final query", budget=100)

        # Should be trimmed
        assert len(messages) < 21
        # Last message should always be the query
        assert messages[-1] == ("user", "final query")

    def test_budget_trimming_preserves_summary(self, service, session_memory_repo, chat_history_repo, token_counter):
        """When trimming, summary block is preserved."""
        session_memory_repo.get_by_session_id.return_value = FakeMemoryDTO(
            rolling_summary="Important context"
        )
        history = [
            FakeMessageDTO(id=i, role="user", content="x" * 200)
            for i in range(20)
        ]
        chat_history_repo.get_session_history.return_value = history

        messages = service.build_context_messages("sess_1", "query", budget=200)

        # Summary block should be preserved
        assert "Conversation Memory" in messages[0][1]
        assert messages[-1] == ("user", "query")

    def test_empty_summary_not_included(self, service, session_memory_repo, chat_history_repo):
        """Empty string summary should not produce summary block."""
        session_memory_repo.get_by_session_id.return_value = FakeMemoryDTO(
            rolling_summary=""
        )
        chat_history_repo.get_session_history.return_value = []

        messages = service.build_context_messages("sess_1", "Hello")
        assert len(messages) == 1
        assert messages[0] == ("user", "Hello")

    def test_recent_turns_passed_to_history_repo(self, service, session_memory_repo, chat_history_repo):
        """recent_turns parameter should be forwarded to get_session_history as limit."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_session_history.return_value = []

        service.build_context_messages("sess_1", "query", recent_turns=42)

        chat_history_repo.get_session_history.assert_called_once_with("sess_1", limit=42)

    def test_custom_budget_trims_correctly(self, service, session_memory_repo, chat_history_repo, token_counter):
        """A small budget should trim more aggressively."""
        session_memory_repo.get_by_session_id.return_value = None
        history = [
            FakeMessageDTO(id=i, role="user", content="x" * 100)
            for i in range(10)
        ]
        chat_history_repo.get_session_history.return_value = history

        messages_small = service.build_context_messages("sess_1", "q", budget=50)
        chat_history_repo.get_session_history.return_value = history
        session_memory_repo.get_by_session_id.return_value = None
        messages_large = service.build_context_messages("sess_1", "q", budget=50000)

        assert len(messages_small) < len(messages_large)
        # Query is always preserved
        assert messages_small[-1] == ("user", "q")
        assert messages_large[-1] == ("user", "q")


class TestMaybeCompact:
    """Tests for maybe_compact."""

    def test_no_messages_does_nothing(self, service, session_memory_repo, chat_history_repo, summary_port):
        """No messages should not trigger compaction."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_full_session_history.return_value = []

        service.maybe_compact("sess_1")

        summary_port.summarize_incremental.assert_not_called()
        session_memory_repo.upsert.assert_not_called()

    def test_below_threshold_does_nothing(self, service, session_memory_repo, chat_history_repo, summary_port):
        """Messages below threshold should not trigger compaction."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_full_session_history.return_value = [
            FakeMessageDTO(id=i, role="user", content=f"msg {i}")
            for i in range(3)  # below threshold of 5
        ]

        service.maybe_compact("sess_1")

        summary_port.summarize_incremental.assert_not_called()

    def test_compaction_triggered_at_threshold(self, service, session_memory_repo, chat_history_repo, summary_port):
        """At threshold, compaction should be triggered."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_full_session_history.return_value = [
            FakeMessageDTO(id=i, role="user", content=f"msg {i}")
            for i in range(1, 6)  # exactly 5, meets threshold
        ]
        summary_port.summarize_incremental.return_value = SummaryResult(summary="New summary", success=True)

        service.maybe_compact("sess_1")

        summary_port.summarize_incremental.assert_called_once()
        session_memory_repo.upsert.assert_called_once()
        call_kwargs = session_memory_repo.upsert.call_args.kwargs
        assert call_kwargs["rolling_summary"] == "New summary"
        assert call_kwargs["last_compacted_message_id"] == 5

    def test_compaction_only_new_messages(self, service, session_memory_repo, chat_history_repo, summary_port):
        """Only un-compacted messages should be summarized."""
        session_memory_repo.get_by_session_id.return_value = FakeMemoryDTO(
            rolling_summary="Old summary",
            last_compacted_message_id=3,
        )
        chat_history_repo.get_full_session_history.return_value = [
            FakeMessageDTO(id=i, role="user", content=f"msg {i}")
            for i in range(1, 10)  # messages 1-9
        ]
        # Messages 4-9 are new (6 messages, above threshold of 5)
        summary_port.summarize_incremental.return_value = SummaryResult(summary="Updated summary", success=True)

        service.maybe_compact("sess_1")

        summary_port.summarize_incremental.assert_called_once()
        call_args = summary_port.summarize_incremental.call_args
        assert call_args.kwargs["previous_summary"] == "Old summary"
        # new_turns should only include messages with id > 3
        new_turns = call_args.kwargs["new_turns"]
        assert len(new_turns) == 6  # ids 4,5,6,7,8,9

    def test_compaction_below_threshold_with_previous(self, service, session_memory_repo, chat_history_repo, summary_port):
        """Below threshold even with previous compaction should not trigger."""
        session_memory_repo.get_by_session_id.return_value = FakeMemoryDTO(
            rolling_summary="Previous",
            last_compacted_message_id=8,
        )
        chat_history_repo.get_full_session_history.return_value = [
            FakeMessageDTO(id=i, role="user", content=f"msg {i}")
            for i in range(1, 12)  # 11 messages total
        ]
        # Only messages 9,10,11 are new (3 messages, below threshold of 5)

        service.maybe_compact("sess_1")

        summary_port.summarize_incremental.assert_not_called()

    def test_compaction_reads_full_history_via_explicit_method(self, service, session_memory_repo, chat_history_repo, summary_port):
        """Compaction should use get_full_session_history (not get_session_history with limit)."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_full_session_history.return_value = [
            FakeMessageDTO(id=i, role="user", content=f"msg {i}")
            for i in range(1, 6)
        ]
        summary_port.summarize_incremental.return_value = SummaryResult(summary="summary", success=True)

        service.maybe_compact("sess_1")

        # Verify explicit full-history method is used
        chat_history_repo.get_full_session_history.assert_called_once_with("sess_1")

    def test_summary_failure_does_not_advance_cursor(self, service, session_memory_repo, chat_history_repo, summary_port):
        """When summary generation fails, cursor should NOT advance."""
        session_memory_repo.get_by_session_id.return_value = None
        chat_history_repo.get_full_session_history.return_value = [
            FakeMessageDTO(id=i, role="user", content=f"msg {i}")
            for i in range(1, 6)  # 5 messages, meets threshold
        ]
        summary_port.summarize_incremental.return_value = SummaryResult(
            summary="", success=False, error="API timeout",
        )

        service.maybe_compact("sess_1")

        summary_port.summarize_incremental.assert_called_once()
        # Cursor must NOT advance on failure
        session_memory_repo.upsert.assert_not_called()

    def test_summary_failure_retries_on_next_trigger(self, service, session_memory_repo, chat_history_repo, summary_port):
        """After summary failure, same messages should be retried on next compaction trigger."""
        session_memory_repo.get_by_session_id.return_value = FakeMemoryDTO(
            rolling_summary="Old", last_compacted_message_id=3,
        )
        chat_history_repo.get_full_session_history.return_value = [
            FakeMessageDTO(id=i, role="user", content=f"msg {i}")
            for i in range(1, 10)  # ids 1-9, new = 4-9 (6 msgs, above threshold)
        ]
        # First call fails
        summary_port.summarize_incremental.return_value = SummaryResult(
            summary="Old", success=False, error="timeout",
        )
        service.maybe_compact("sess_1")
        session_memory_repo.upsert.assert_not_called()

        # Second call succeeds — same messages should be eligible
        summary_port.summarize_incremental.return_value = SummaryResult(
            summary="Updated", success=True,
        )
        service.maybe_compact("sess_1")
        session_memory_repo.upsert.assert_called_once()
        assert session_memory_repo.upsert.call_args.kwargs["rolling_summary"] == "Updated"
