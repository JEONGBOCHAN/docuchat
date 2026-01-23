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
