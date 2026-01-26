# -*- coding: utf-8 -*-
"""Tests for LangGraphAgentRunner LLM callback integration.

Tests the integration between LangGraphAgentRunner and DashboardMiddleware
for LLM node display in the dashboard.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
from src.agents.middlewares.dashboard import (
    DashboardMiddleware,
    AgentStatus,
    NodeStatus,
)
from src.application.ports.agent_runner import AgentConfig


class TestLangGraphAgentRunnerInit:
    """Tests for LangGraphAgentRunner initialization with dashboard_middleware."""

    def test_init_without_dashboard_middleware(self):
        """Test that runner initializes correctly without dashboard_middleware."""
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
        )

        assert runner._dashboard_middleware is None

    def test_init_with_dashboard_middleware(self):
        """Test that runner initializes correctly with dashboard_middleware."""
        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        assert runner._dashboard_middleware is middleware


class TestLangGraphAgentRunnerRunStreamLLMCallbacks:
    """Tests for run_stream method LLM callback integration."""

    @pytest.fixture
    def mock_agent_response(self):
        """Create a mock agent response with content."""
        # Mock AIMessageChunk with content
        mock_msg = Mock()
        mock_msg.type = "ai"
        mock_msg.content = "Hello, this is a response"
        mock_msg.tool_calls = None
        return mock_msg

    @pytest.fixture
    def mock_agent(self, mock_agent_response):
        """Create a mock agent that yields streaming messages."""
        agent = Mock()
        # Yield a single AI message chunk with content
        agent.stream = Mock(return_value=iter([
            (mock_agent_response, {}),
        ]))
        return agent

    @pytest.fixture
    def runner_with_middleware(self, mock_agent):
        """Create a runner with dashboard middleware and mocked agent."""
        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        # Patch _create_agent to return our mock
        with patch.object(runner, '_create_agent', return_value=mock_agent):
            yield runner, middleware

    def test_run_stream_emits_llm_start_on_first_content(self, runner_with_middleware):
        """Test that on_llm_start is called when first content is received."""
        runner, middleware = runner_with_middleware

        # Consume the generator
        events = list(runner.run_stream(
            query="Test query",
            config=AgentConfig(),
            context={"channel_id": "test-channel"},
        ))

        # Verify LLM step was created
        llm_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(llm_steps) == 1
        assert llm_steps[0].data.get("type") == "llm"

    def test_run_stream_emits_llm_end_after_loop(self, runner_with_middleware):
        """Test that on_llm_end is called after streaming completes."""
        runner, middleware = runner_with_middleware

        # Consume the generator
        events = list(runner.run_stream(
            query="Test query",
            config=AgentConfig(),
            context={"channel_id": "test-channel"},
        ))

        # Verify LLM step was completed
        llm_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(llm_steps) == 1
        assert llm_steps[0].status == NodeStatus.COMPLETE
        assert llm_steps[0].duration_ms is not None

    def test_run_stream_no_llm_events_without_content(self):
        """Test that no LLM events are emitted if no content is received."""
        # Create a mock that returns only a tool message
        mock_tool_msg = Mock()
        mock_tool_msg.type = "tool"
        mock_tool_msg.content = "Tool result"
        mock_tool_msg.name = "search_documents"

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_tool_msg, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            events = list(runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Verify no LLM steps were created
        llm_steps = [s for s in middleware.state.steps if s.data.get("type") == "llm"]
        assert len(llm_steps) == 0

    def test_run_stream_llm_events_published_to_state_updater(self):
        """Test that LLM events are published through state_updater."""
        events_received = []
        middleware = DashboardMiddleware(state_updater=lambda e: events_received.append(e))

        mock_msg = Mock()
        mock_msg.type = "ai"
        mock_msg.content = "Response content"
        mock_msg.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_msg, {}),
        ]))

        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Verify LLM events were published
        event_types = [e["event"] for e in events_received]
        assert "llm_start" in event_types
        assert "llm_complete" in event_types

    def test_run_stream_without_middleware_works_normally(self):
        """Test that run_stream works correctly without dashboard_middleware."""
        mock_msg = Mock()
        mock_msg.type = "ai"
        mock_msg.content = "Response content"
        mock_msg.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_msg, {}),
        ]))

        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=None,  # No middleware
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            events = list(runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Should not raise any errors
        content_events = [e for e in events if e.get("event") == "content"]
        assert len(content_events) >= 1


class TestLangGraphAgentRunnerRunLLMCallbacks:
    """Tests for synchronous run method LLM callback integration."""

    @pytest.fixture
    def mock_agent_result(self):
        """Create a mock agent invoke result."""
        mock_msg = Mock()
        mock_msg.content = "Final response"
        mock_msg.tool_calls = []
        return {"messages": [mock_msg]}

    @pytest.fixture
    def mock_agent_sync(self, mock_agent_result):
        """Create a mock agent for synchronous run."""
        agent = Mock()
        agent.invoke = Mock(return_value=mock_agent_result)
        return agent

    def test_run_emits_llm_start_before_invoke(self, mock_agent_sync):
        """Test that on_llm_start is called before agent.invoke."""
        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent_sync):
            result = runner.run(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        # Verify LLM step was created
        llm_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(llm_steps) == 1
        assert llm_steps[0].data.get("type") == "llm"

    def test_run_emits_llm_end_after_invoke(self, mock_agent_sync):
        """Test that on_llm_end is called after agent.invoke completes."""
        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent_sync):
            result = runner.run(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        # Verify LLM step was completed
        llm_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(llm_steps) == 1
        assert llm_steps[0].status == NodeStatus.COMPLETE
        assert llm_steps[0].duration_ms is not None

    def test_run_without_middleware_works_normally(self, mock_agent_sync):
        """Test that run works correctly without dashboard_middleware."""
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=None,  # No middleware
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent_sync):
            result = runner.run(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        # Should not raise any errors
        assert result is not None
        assert result.response == "Final response"


class TestLangGraphAgentRunnerToolCallsNotAffected:
    """Tests to verify existing tool tracking is not affected."""

    def test_run_stream_tool_tracking_still_works(self):
        """Test that tool call tracking still works correctly."""
        # Create message sequence: AI with tool_call -> Tool result -> AI response
        mock_ai_with_tool = Mock()
        mock_ai_with_tool.type = "ai"
        mock_ai_with_tool.content = ""
        mock_ai_with_tool.tool_calls = [{"name": "search_documents", "args": {"query": "test"}}]

        mock_tool_result = Mock()
        mock_tool_result.type = "tool"
        mock_tool_result.content = "Tool result"
        mock_tool_result.name = "search_documents"

        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final response based on search"
        mock_ai_response.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_with_tool, {}),
            (mock_tool_result, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            events = list(runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Verify both tool and LLM steps are present
        tool_events = [e for e in events if e.get("event") in ("tool_started", "tool_completed")]
        content_events = [e for e in events if e.get("event") == "content"]

        # Tool started and completed events should be present
        assert len(tool_events) == 2

        # Content should be yielded
        assert len(content_events) >= 1

        # LLM step should be recorded in middleware
        llm_steps = [s for s in middleware.state.steps if s.data.get("type") == "llm"]
        assert len(llm_steps) == 1

    def test_run_stream_event_sink_tool_events_still_emitted(self):
        """Test that event_sink still receives tool events."""
        events_emitted = []
        mock_event_sink = Mock()
        mock_event_sink.emit = Mock(side_effect=lambda e: events_emitted.append(e))

        mock_ai_with_tool = Mock()
        mock_ai_with_tool.type = "ai"
        mock_ai_with_tool.content = ""
        mock_ai_with_tool.tool_calls = [{"name": "web_search", "args": {"query": "test"}}]

        mock_tool_result = Mock()
        mock_tool_result.type = "tool"
        mock_tool_result.content = "Search result"
        mock_tool_result.name = "web_search"

        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Response"
        mock_ai_response.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_with_tool, {}),
            (mock_tool_result, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=mock_event_sink,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Verify tool events were emitted to event_sink
        from src.application.dto.agent_event import ToolStartedEvent, ToolCompletedEvent
        tool_started = [e for e in events_emitted if isinstance(e, ToolStartedEvent)]
        tool_completed = [e for e in events_emitted if isinstance(e, ToolCompletedEvent)]

        assert len(tool_started) == 1
        assert len(tool_completed) == 1
        assert tool_started[0].tool_name == "web_search"


class TestLangGraphAgentRunnerStreamingNotAffected:
    """Tests to verify streaming functionality is not affected."""

    def test_content_events_still_yielded(self):
        """Test that content events are still yielded correctly."""
        mock_msg1 = Mock()
        mock_msg1.type = "ai"
        mock_msg1.content = "Hello"
        mock_msg1.tool_calls = None

        mock_msg2 = Mock()
        mock_msg2.type = "ai"
        mock_msg2.content = " World"
        mock_msg2.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_msg1, {}),
            (mock_msg2, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            events = list(runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Verify content events
        content_events = [e for e in events if e.get("event") == "content"]
        assert len(content_events) == 2
        assert content_events[0]["content"] == "Hello"
        assert content_events[1]["content"] == " World"

    def test_final_response_still_accumulated(self):
        """Test that final response is still correctly accumulated."""
        mock_msg1 = Mock()
        mock_msg1.type = "ai"
        mock_msg1.content = "Part 1 "
        mock_msg1.tool_calls = None

        mock_msg2 = Mock()
        mock_msg2.type = "ai"
        mock_msg2.content = "Part 2"
        mock_msg2.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_msg1, {}),
            (mock_msg2, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            gen = runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )
            # Consume and get return value
            events = []
            try:
                while True:
                    events.append(next(gen))
            except StopIteration as e:
                result = e.value

        # Verify final response
        assert result.response == "Part 1 Part 2"
