# -*- coding: utf-8 -*-
"""
Tests for ProcessQueryUseCase.

Tests the Clean Architecture use case for processing user queries.
"""

import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

from src.application.use_cases.process_query import ProcessQueryUseCase, QueryResult
from src.application.ports import AgentRunnerPort, AgentConfig, AgentEventSinkPort
from src.application.ports.agent_runner import AgentResult


class TestProcessQueryUseCase:
    """Tests for ProcessQueryUseCase."""

    def test_execute_success(self):
        """Test successful query execution."""
        # Mock agent runner
        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run.return_value = AgentResult(
            response="This is the answer.",
            sources=[{"source": "doc1.pdf", "content": "..."}],
            tool_calls=[{"tool": "search_documents"}],
            iterations=2,
            session_id="test-session",
            metadata={"channel_id": "test-channel"},
        )

        # Create use case
        use_case = ProcessQueryUseCase(agent_runner=mock_runner)

        # Execute
        result = use_case.execute(
            query="What is AI?",
            channel_id="test-channel",
        )

        # Verify result
        assert result.response == "This is the answer."
        assert len(result.sources) == 1
        assert result.sources[0]["source"] == "doc1.pdf"
        assert result.iterations == 2
        assert result.error is None

        # Verify runner was called
        mock_runner.run.assert_called_once()

    def test_execute_with_event_sink(self):
        """Test query execution with event sink."""
        # Mock dependencies
        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run.return_value = AgentResult(
            response="Answer",
            sources=[],
            tool_calls=[],
            iterations=1,
        )

        mock_event_sink = Mock(spec=AgentEventSinkPort)

        # Create use case
        use_case = ProcessQueryUseCase(
            agent_runner=mock_runner,
            event_sink=mock_event_sink,
        )

        # Execute
        result = use_case.execute(
            query="Test query",
            channel_id="test-channel",
        )

        # Verify events were emitted
        assert mock_event_sink.emit.call_count >= 2  # start and complete

    def test_execute_with_conversation_history(self):
        """Test query execution with conversation history."""
        # Mock runner
        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run.return_value = AgentResult(
            response="Follow-up answer",
            sources=[],
            tool_calls=[],
            iterations=1,
        )

        use_case = ProcessQueryUseCase(agent_runner=mock_runner)

        # Execute with history
        history = [
            {"role": "user", "content": "What is AI?"},
            {"role": "assistant", "content": "AI is..."},
        ]

        result = use_case.execute(
            query="Tell me more",
            channel_id="test-channel",
            conversation_history=history,
        )

        # Verify history was passed to runner
        call_args = mock_runner.run.call_args
        assert call_args[1]["context"]["conversation_history"] == history

    def test_execute_error_handling(self):
        """Test error handling during query execution."""
        # Mock runner that raises exception
        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run.side_effect = Exception("Agent failed")

        use_case = ProcessQueryUseCase(agent_runner=mock_runner)

        # Execute
        result = use_case.execute(
            query="Test query",
            channel_id="test-channel",
        )

        # Verify error is captured
        assert result.error is not None
        assert "Agent failed" in result.error
        assert "Error" in result.response


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_query_result_defaults(self):
        """Test QueryResult with defaults."""
        result = QueryResult(response="Test")

        assert result.response == "Test"
        assert result.sources == []
        assert result.session_id is None
        assert result.iterations == 0
        assert result.tools_used == []
        assert result.metadata == {}
        assert result.error is None

    def test_query_result_with_values(self):
        """Test QueryResult with all values."""
        result = QueryResult(
            response="Answer",
            sources=[{"source": "doc.pdf"}],
            session_id="session-123",
            iterations=3,
            tools_used=["search", "finish"],
            metadata={"key": "value"},
            error=None,
        )

        assert result.response == "Answer"
        assert len(result.sources) == 1
        assert result.session_id == "session-123"
        assert result.iterations == 3
        assert len(result.tools_used) == 2
        assert result.metadata["key"] == "value"


class TestProcessQueryUseCaseStreaming:
    """Tests for ProcessQueryUseCase.execute_stream()."""

    def _create_mock_stream_generator(self, events: list, final_result: AgentResult):
        """Helper to create a mock streaming generator."""
        def generator():
            for event in events:
                yield event
            return final_result
        return generator()

    def test_execute_stream_success(self):
        """Test successful streaming query execution."""
        # Mock events
        events = [
            {"event": "agent_started", "session_id": "test-session"},
            {"event": "tool_started", "tool": "search_documents"},
            {"event": "content", "content": "Processing..."},
            {"event": "tool_completed", "tool": "search_documents"},
            {"event": "agent_completed", "response": "Final answer"},
        ]

        final_result = AgentResult(
            response="Final answer",
            sources=[{"source": "doc1.pdf"}],
            tool_calls=[{"tool": "search_documents"}],
            iterations=2,
            session_id="test-session",
            metadata={"channel_id": "test-channel"},
        )

        # Mock runner with streaming
        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run_stream.return_value = self._create_mock_stream_generator(
            events, final_result
        )

        use_case = ProcessQueryUseCase(agent_runner=mock_runner)

        # Execute streaming
        stream_gen = use_case.execute_stream(
            query="What is AI?",
            channel_id="test-channel",
        )

        # Collect yielded events
        yielded_events = []
        result = None
        try:
            while True:
                event = next(stream_gen)
                yielded_events.append(event)
        except StopIteration as e:
            result = e.value

        # Verify events were yielded
        assert len(yielded_events) == 5
        assert yielded_events[0]["event"] == "agent_started"
        assert yielded_events[-1]["event"] == "agent_completed"

        # Verify final result
        assert result is not None
        assert result.response == "Final answer"
        assert len(result.sources) == 1
        assert result.iterations == 2

    def test_execute_stream_with_session_id(self):
        """Test streaming with provided session ID."""
        events = [{"event": "agent_started", "session_id": "custom-session"}]
        final_result = AgentResult(
            response="Answer",
            sources=[],
            tool_calls=[],
            iterations=1,
        )

        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run_stream.return_value = self._create_mock_stream_generator(
            events, final_result
        )

        use_case = ProcessQueryUseCase(agent_runner=mock_runner)

        stream_gen = use_case.execute_stream(
            query="Test",
            channel_id="test-channel",
            session_id="custom-session",
        )

        # Consume generator
        try:
            while True:
                next(stream_gen)
        except StopIteration as e:
            result = e.value

        # Verify session_id was passed to runner
        call_args = mock_runner.run_stream.call_args
        assert call_args[1]["context"]["session_id"] == "custom-session"

    def test_execute_stream_with_conversation_history(self):
        """Test streaming with conversation history."""
        events = [{"event": "agent_started"}]
        final_result = AgentResult(
            response="Follow-up answer",
            sources=[],
            tool_calls=[],
            iterations=1,
        )

        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run_stream.return_value = self._create_mock_stream_generator(
            events, final_result
        )

        use_case = ProcessQueryUseCase(agent_runner=mock_runner)

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        stream_gen = use_case.execute_stream(
            query="Follow up",
            channel_id="test-channel",
            conversation_history=history,
        )

        # Consume generator
        try:
            while True:
                next(stream_gen)
        except StopIteration:
            pass

        # Verify history was passed to runner
        call_args = mock_runner.run_stream.call_args
        assert call_args[1]["context"]["conversation_history"] == history

    def test_execute_stream_error_handling(self):
        """Test error handling during streaming."""
        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run_stream.side_effect = Exception("Stream failed")

        mock_event_sink = Mock(spec=AgentEventSinkPort)

        use_case = ProcessQueryUseCase(
            agent_runner=mock_runner,
            event_sink=mock_event_sink,
        )

        stream_gen = use_case.execute_stream(
            query="Test",
            channel_id="test-channel",
        )

        # Collect events
        yielded_events = []
        result = None
        try:
            while True:
                event = next(stream_gen)
                yielded_events.append(event)
        except StopIteration as e:
            result = e.value

        # Verify error event was yielded
        assert len(yielded_events) == 1
        assert yielded_events[0]["event"] == "error"
        assert "Stream failed" in yielded_events[0]["error"]

        # Verify result contains error
        assert result.error is not None
        assert "Stream failed" in result.error

        # Verify error event was emitted to sink
        mock_event_sink.emit.assert_called()

    def test_execute_stream_yields_content_events(self):
        """Test that content events are properly yielded."""
        events = [
            {"event": "agent_started"},
            {"event": "content", "content": "First chunk"},
            {"event": "content", "content": "Second chunk"},
            {"event": "content", "content": "Final chunk"},
            {"event": "agent_completed"},
        ]

        final_result = AgentResult(
            response="Complete response",
            sources=[],
            tool_calls=[],
            iterations=1,
        )

        mock_runner = Mock(spec=AgentRunnerPort)
        mock_runner.run_stream.return_value = self._create_mock_stream_generator(
            events, final_result
        )

        use_case = ProcessQueryUseCase(agent_runner=mock_runner)

        stream_gen = use_case.execute_stream(
            query="Test",
            channel_id="test-channel",
        )

        # Collect content events
        content_events = []
        try:
            while True:
                event = next(stream_gen)
                if event.get("event") == "content":
                    content_events.append(event["content"])
        except StopIteration:
            pass

        # Verify content events
        assert len(content_events) == 3
        assert "First chunk" in content_events
        assert "Second chunk" in content_events
        assert "Final chunk" in content_events
