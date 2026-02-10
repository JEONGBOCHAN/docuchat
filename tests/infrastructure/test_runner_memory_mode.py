# -*- coding: utf-8 -*-
"""Tests for LangGraphAgentRunner memory_mode support.

Tests the hybrid_default and hybrid_strict memory modes
for conversation context assembly in the runner.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
from src.shared.kernel.contracts.ports.agent_runner import AgentConfig


class TestHistoryToMessages:
    """Tests for _history_to_messages static method."""

    def test_empty_history_returns_query_only(self):
        """Empty history should produce only the user query."""
        messages = LangGraphAgentRunner._history_to_messages([], "Hello")
        assert messages == [("user", "Hello")]

    def test_none_history_returns_query_only(self):
        """None history should produce only the user query."""
        messages = LangGraphAgentRunner._history_to_messages(None, "Hello")
        assert messages == [("user", "Hello")]

    def test_tuple_format_used_as_is(self):
        """Tuple-format history (from memory service) should be used directly."""
        history = [
            ("user", "[Conversation Memory]\nSummary..."),
            ("assistant", "I'll keep this in mind."),
            ("user", "previous question"),
            ("assistant", "previous answer"),
            ("user", "current query"),
        ]
        messages = LangGraphAgentRunner._history_to_messages(history, "current query")
        # Should use history as-is (already includes query)
        assert messages == history
        assert len(messages) == 5

    def test_dict_format_converted_with_query(self):
        """Dict-format history (legacy) should be converted and query appended."""
        history = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "A programming language."},
        ]
        messages = LangGraphAgentRunner._history_to_messages(history, "Tell me more")
        assert messages == [
            ("user", "What is Python?"),
            ("assistant", "A programming language."),
            ("user", "Tell me more"),
        ]

    def test_dict_format_default_role_is_user(self):
        """Dict without role key should default to user."""
        history = [{"content": "hi"}]
        messages = LangGraphAgentRunner._history_to_messages(history, "query")
        assert messages[0] == ("user", "hi")


class TestMemoryModeRun:
    """Tests for memory_mode in the run() method."""

    @pytest.fixture
    def mock_ai_response(self):
        """Create a mock AI response message."""
        msg = Mock()
        msg.type = "ai"
        msg.content = "AI response"
        msg.tool_calls = []
        msg.usage_metadata = None
        return msg

    @pytest.fixture
    def mock_agent(self, mock_ai_response):
        """Create a mock compiled agent."""
        agent = Mock()
        agent.invoke = Mock(return_value={"messages": [mock_ai_response]})
        return agent

    @pytest.fixture
    def runner(self, mock_agent):
        """Create a runner with mocked dependencies."""
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
        )
        with patch.object(runner, "_create_agent", return_value=mock_agent):
            yield runner

    def test_hybrid_strict_always_loads_history(self, runner, mock_agent):
        """hybrid_strict should always use conversation_history, even with checkpoint hit."""
        mock_checkpointer = Mock()
        mock_checkpointer.get_tuple.return_value = Mock()  # Checkpoint exists
        runner._checkpointer = mock_checkpointer

        memory_history = [
            ("user", "[Conversation Memory]\nSummary"),
            ("assistant", "Acknowledged."),
            ("user", "the query"),
        ]
        loader = Mock(return_value=memory_history)

        result = runner.run(
            query="the query",
            config=AgentConfig(),
            context={
                "channel_id": "ch1",
                "conversation_history": loader,
                "thread_id": "thread1",
                "memory_mode": "hybrid_strict",
            },
        )

        loader.assert_called_once()
        # Verify agent was invoked with the memory history (not just query)
        invoke_call = mock_agent.invoke.call_args
        invoked_messages = invoke_call[0][0]["messages"]
        assert len(invoked_messages) == 3
        assert invoked_messages[0] == ("user", "[Conversation Memory]\nSummary")
        # Verify thread_id NOT in invoke config (F-01/F-04)
        invoke_config = invoke_call[1].get("config", invoke_call[0][1] if len(invoke_call[0]) > 1 else {})
        assert "configurable" not in invoke_config

    def test_hybrid_strict_skips_checkpoint_check(self, runner, mock_agent):
        """hybrid_strict should not check checkpoint state."""
        mock_checkpointer = Mock()
        runner._checkpointer = mock_checkpointer

        loader = Mock(return_value=[("user", "query")])

        runner.run(
            query="query",
            config=AgentConfig(),
            context={
                "channel_id": "ch1",
                "conversation_history": loader,
                "thread_id": "thread1",
                "memory_mode": "hybrid_strict",
            },
        )

        # Checkpoint should NOT be checked
        mock_checkpointer.get_tuple.assert_not_called()
        # Verify thread_id NOT in invoke config (F-01/F-04)
        invoke_call = mock_agent.invoke.call_args
        invoke_config = invoke_call[1].get("config", invoke_call[0][1] if len(invoke_call[0]) > 1 else {})
        assert "configurable" not in invoke_config

    def test_hybrid_default_checkpoint_hit_query_only(self, runner, mock_agent):
        """hybrid_default with checkpoint hit should use query-only."""
        mock_checkpointer = Mock()
        mock_checkpointer.get_tuple.return_value = Mock()  # Hit
        runner._checkpointer = mock_checkpointer

        loader = Mock(return_value=[("user", "old"), ("user", "query")])

        runner.run(
            query="query",
            config=AgentConfig(),
            context={
                "channel_id": "ch1",
                "conversation_history": loader,
                "thread_id": "thread1",
                "memory_mode": "hybrid_default",
            },
        )

        # History should NOT be loaded on checkpoint hit
        loader.assert_not_called()
        invoke_call = mock_agent.invoke.call_args
        invoked_messages = invoke_call[0][0]["messages"]
        assert invoked_messages == [("user", "query")]

    def test_hybrid_default_checkpoint_miss_loads_history(self, runner, mock_agent):
        """hybrid_default with checkpoint miss should load history."""
        mock_checkpointer = Mock()
        mock_checkpointer.get_tuple.return_value = None  # Miss
        runner._checkpointer = mock_checkpointer

        memory_history = [
            ("user", "summary block"),
            ("assistant", "ack"),
            ("user", "the query"),
        ]
        loader = Mock(return_value=memory_history)

        runner.run(
            query="the query",
            config=AgentConfig(),
            context={
                "channel_id": "ch1",
                "conversation_history": loader,
                "thread_id": "thread1",
                "memory_mode": "hybrid_default",
            },
        )

        loader.assert_called_once()
        invoke_call = mock_agent.invoke.call_args
        invoked_messages = invoke_call[0][0]["messages"]
        assert len(invoked_messages) == 3

    def test_no_memory_mode_backward_compatible(self, runner, mock_agent):
        """No memory_mode should behave as before (dict-based history)."""
        mock_checkpointer = Mock()
        mock_checkpointer.get_tuple.return_value = None  # Miss
        runner._checkpointer = mock_checkpointer

        dict_history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        loader = Mock(return_value=dict_history)

        runner.run(
            query="question",
            config=AgentConfig(),
            context={
                "channel_id": "ch1",
                "conversation_history": loader,
                "thread_id": "thread1",
            },
        )

        loader.assert_called_once()
        invoke_call = mock_agent.invoke.call_args
        invoked_messages = invoke_call[0][0]["messages"]
        assert invoked_messages == [
            ("user", "hi"),
            ("assistant", "hello"),
            ("user", "question"),
        ]


class TestMemoryModeRunStream:
    """Tests for memory_mode in the run_stream() method."""

    @pytest.fixture
    def mock_ai_chunk(self):
        """Create a mock AI message chunk."""
        msg = Mock()
        msg.type = "ai"
        msg.content = "streamed response"
        msg.tool_calls = None
        msg.usage_metadata = None
        return msg

    @pytest.fixture
    def mock_agent(self, mock_ai_chunk):
        """Create a mock streaming agent."""
        agent = Mock()
        agent.stream = Mock(return_value=iter([(mock_ai_chunk, {})]))
        return agent

    @pytest.fixture
    def runner(self, mock_agent):
        """Create a runner with mocked dependencies."""
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
        )
        with patch.object(runner, "_create_agent", return_value=mock_agent):
            yield runner

    def _consume_stream(self, gen):
        """Consume a stream generator, returning events and final result."""
        events = []
        result = None
        try:
            while True:
                events.append(next(gen))
        except StopIteration as e:
            result = e.value
        return events, result

    def test_stream_hybrid_strict_loads_history(self, runner, mock_agent):
        """hybrid_strict in streaming should use conversation_history."""
        mock_checkpointer = Mock()
        mock_checkpointer.get_tuple.return_value = Mock()  # Hit
        runner._checkpointer = mock_checkpointer

        memory_history = [
            ("user", "summary"),
            ("assistant", "ack"),
            ("user", "query"),
        ]
        loader = Mock(return_value=memory_history)

        gen = runner.run_stream(
            query="query",
            config=AgentConfig(),
            context={
                "channel_id": "ch1",
                "conversation_history": loader,
                "thread_id": "thread1",
                "memory_mode": "hybrid_strict",
            },
        )
        self._consume_stream(gen)

        loader.assert_called_once()
        mock_checkpointer.get_tuple.assert_not_called()

        stream_call = mock_agent.stream.call_args
        streamed_messages = stream_call[0][0]["messages"]
        assert len(streamed_messages) == 3
        # Verify thread_id NOT in stream config (F-01/F-04)
        stream_config = stream_call[1].get("config", stream_call[0][1] if len(stream_call[0]) > 1 else {})
        assert "configurable" not in stream_config

    def test_stream_hybrid_default_hit_query_only(self, runner, mock_agent):
        """hybrid_default stream with checkpoint hit should be query-only."""
        mock_checkpointer = Mock()
        mock_checkpointer.get_tuple.return_value = Mock()  # Hit
        runner._checkpointer = mock_checkpointer

        loader = Mock(return_value=[("user", "old"), ("user", "query")])

        gen = runner.run_stream(
            query="query",
            config=AgentConfig(),
            context={
                "channel_id": "ch1",
                "conversation_history": loader,
                "thread_id": "thread1",
                "memory_mode": "hybrid_default",
            },
        )
        self._consume_stream(gen)

        loader.assert_not_called()
        stream_call = mock_agent.stream.call_args
        streamed_messages = stream_call[0][0]["messages"]
        assert streamed_messages == [("user", "query")]
