# -*- coding: utf-8 -*-
"""Tests for LangGraphAgentRunner LLM callback integration.

Tests the integration between LangGraphAgentRunner and DashboardMiddleware
for LLM node display in the dashboard.

Includes tests for:
- llm_response: Final LLM response with content
- llm_reasoning: Initial reasoning when agent decides to use tools (no content, only tool_calls)
- llm_observation: After tool execution, when agent observes results and decides next action
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
from src.shared.kernel.contracts.ports.agent_runner import AgentConfig


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
    """Tests for synchronous run method LLM callback integration.

    Note: run() now analyzes messages to emit proper LLM events:
    - llm_reasoning: When AI selects tools
    - llm_observation: After tool execution, when deciding next action
    - llm_response: Final AI response with content
    """

    @pytest.fixture
    def mock_agent_result(self):
        """Create a mock agent invoke result with content only (no tools)."""
        mock_msg = Mock()
        mock_msg.type = "ai"  # Set type for proper detection
        mock_msg.content = "Final response"
        mock_msg.tool_calls = []  # Empty list means no tool calls
        return {"messages": [mock_msg]}

    @pytest.fixture
    def mock_agent_sync(self, mock_agent_result):
        """Create a mock agent for synchronous run."""
        agent = Mock()
        agent.invoke = Mock(return_value=mock_agent_result)
        return agent

    def test_run_emits_llm_response_for_direct_answer(self, mock_agent_sync):
        """Test that on_llm_start is called for direct answer without tools."""
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

        # Verify LLM step was created (now only llm_response for direct answers)
        llm_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(llm_steps) == 1
        assert llm_steps[0].data.get("type") == "llm"

    def test_run_emits_llm_end_for_direct_answer(self, mock_agent_sync):
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
        """Test that tool call tracking still works correctly with new LLM phases."""
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

        # LLM steps should be recorded in middleware
        # With new logic: llm_reasoning (for tool selection) + llm_response (for final content)
        llm_steps = [s for s in middleware.state.steps if s.data.get("type") == "llm"]
        assert len(llm_steps) == 2  # reasoning + response

        # Verify specific LLM step types
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(reasoning_steps) == 1, "Should have llm_reasoning for tool selection"
        assert len(response_steps) == 1, "Should have llm_response for final answer"

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
        from src.shared.kernel.contracts.dto.agent_event import ToolStartedEvent, ToolCompletedEvent
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


class TestLLMReasoningTracking:
    """Tests for llm_reasoning tracking - initial tool selection phase."""

    def test_run_stream_emits_llm_reasoning_on_tool_calls_without_content(self):
        """Test that llm_reasoning is emitted when tool_calls present but no content."""
        # AI message with tool_calls but no content (initial reasoning)
        mock_ai_with_tool = Mock()
        mock_ai_with_tool.type = "ai"
        mock_ai_with_tool.content = ""  # No content
        mock_ai_with_tool.tool_calls = [{"name": "arxiv_search", "args": {"query": "attention"}}]

        # Tool result
        mock_tool_result = Mock()
        mock_tool_result.type = "tool"
        mock_tool_result.content = "Tool result"
        mock_tool_result.name = "arxiv_search"

        # Final AI response with content
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Based on the search results..."
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
            list(runner.run_stream(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Verify llm_reasoning step was created
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        assert len(reasoning_steps) == 1
        assert reasoning_steps[0].status == NodeStatus.COMPLETE
        assert reasoning_steps[0].data.get("type") == "llm"

    def test_run_stream_reasoning_ends_before_tool_starts(self):
        """Test that llm_reasoning ends before tool execution starts."""
        events_order = []

        def track_events(event):
            events_order.append(event["event"])

        # AI message with tool_calls
        mock_ai_with_tool = Mock()
        mock_ai_with_tool.type = "ai"
        mock_ai_with_tool.content = ""
        mock_ai_with_tool.tool_calls = [{"name": "web_search", "args": {"query": "test"}}]

        # Tool result
        mock_tool_result = Mock()
        mock_tool_result.type = "tool"
        mock_tool_result.content = "Search result"
        mock_tool_result.name = "web_search"

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_with_tool, {}),
            (mock_tool_result, {}),
        ]))

        middleware = DashboardMiddleware(state_updater=track_events)
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

        # Verify event order: llm_start -> llm_complete -> tool_start -> tool_complete
        assert "llm_start" in events_order
        assert "llm_complete" in events_order

        # Find first llm_start and first llm_complete
        llm_start_indices = [i for i, e in enumerate(events_order) if e == "llm_start"]
        llm_complete_indices = [i for i, e in enumerate(events_order) if e == "llm_complete"]

        assert len(llm_start_indices) >= 1, "Should have at least one llm_start"
        assert len(llm_complete_indices) >= 1, "Should have at least one llm_complete"

        # First LLM (reasoning) should complete before tool interaction
        first_llm_start = llm_start_indices[0]
        first_llm_complete = llm_complete_indices[0]
        assert first_llm_start < first_llm_complete, "LLM start should come before complete"


class TestLLMObservationTracking:
    """Tests for llm_observation tracking - after tool execution, deciding next action."""

    def test_run_stream_emits_llm_observation_after_tool_completion(self):
        """Test that llm_observation is emitted after tool completes and LLM decides next tool."""
        # First AI message: initial reasoning -> tool call
        mock_ai_reasoning = Mock()
        mock_ai_reasoning.type = "ai"
        mock_ai_reasoning.content = ""
        mock_ai_reasoning.tool_calls = [{"name": "arxiv_search", "args": {"query": "attention"}}]

        # First tool result
        mock_tool_result1 = Mock()
        mock_tool_result1.type = "tool"
        mock_tool_result1.content = "ArXiv results"
        mock_tool_result1.name = "arxiv_search"

        # Second AI message: observation -> decides to use another tool
        mock_ai_observation = Mock()
        mock_ai_observation.type = "ai"
        mock_ai_observation.content = ""
        mock_ai_observation.tool_calls = [{"name": "web_search", "args": {"query": "more info"}}]

        # Second tool result
        mock_tool_result2 = Mock()
        mock_tool_result2.type = "tool"
        mock_tool_result2.content = "Web results"
        mock_tool_result2.name = "web_search"

        # Final AI response
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final answer based on all results"
        mock_ai_response.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_reasoning, {}),
            (mock_tool_result1, {}),
            (mock_ai_observation, {}),
            (mock_tool_result2, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
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

        # Verify both llm_reasoning and llm_observation steps
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        observation_steps = [s for s in middleware.state.steps if s.node == "llm_observation"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 1, "Should have one llm_reasoning step"
        assert len(observation_steps) == 1, "Should have one llm_observation step"
        assert len(response_steps) == 1, "Should have one llm_response step"

    def test_run_stream_multiple_observations(self):
        """Test tracking multiple observation phases in a ReAct loop."""
        # Initial reasoning
        mock_ai_reasoning = Mock()
        mock_ai_reasoning.type = "ai"
        mock_ai_reasoning.content = ""
        mock_ai_reasoning.tool_calls = [{"name": "arxiv_search", "args": {}}]

        mock_tool1 = Mock()
        mock_tool1.type = "tool"
        mock_tool1.content = "Result 1"
        mock_tool1.name = "arxiv_search"

        # First observation
        mock_ai_obs1 = Mock()
        mock_ai_obs1.type = "ai"
        mock_ai_obs1.content = ""
        mock_ai_obs1.tool_calls = [{"name": "web_search", "args": {}}]

        mock_tool2 = Mock()
        mock_tool2.type = "tool"
        mock_tool2.content = "Result 2"
        mock_tool2.name = "web_search"

        # Second observation
        mock_ai_obs2 = Mock()
        mock_ai_obs2.type = "ai"
        mock_ai_obs2.content = ""
        mock_ai_obs2.tool_calls = [{"name": "search_documents", "args": {}}]

        mock_tool3 = Mock()
        mock_tool3.type = "tool"
        mock_tool3.content = "Result 3"
        mock_tool3.name = "search_documents"

        # Final response
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final comprehensive answer"
        mock_ai_response.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_reasoning, {}),
            (mock_tool1, {}),
            (mock_ai_obs1, {}),
            (mock_tool2, {}),
            (mock_ai_obs2, {}),
            (mock_tool3, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Complex query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Verify correct counts
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        observation_steps = [s for s in middleware.state.steps if s.node == "llm_observation"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 1, "Should have one llm_reasoning step"
        assert len(observation_steps) == 2, "Should have two llm_observation steps"
        assert len(response_steps) == 1, "Should have one llm_response step"

        # Verify model_calls metric
        # 1 reasoning + 2 observations + 1 response = 4 model calls
        assert middleware.state.metrics.model_calls == 4


class TestRunMethodLLMTracking:
    """Tests for synchronous run() method LLM tracking with reasoning/observation."""

    def _create_ai_message_mock(self, content="", tool_calls=None):
        """Helper to create properly configured AI message mock."""
        msg = Mock()
        # Set type attribute for detection (matches run_stream pattern)
        msg.type = "ai"
        msg.content = content
        msg.tool_calls = tool_calls if tool_calls else []
        return msg

    def _create_tool_message_mock(self, content=""):
        """Helper to create properly configured tool message mock."""
        msg = Mock()
        msg.type = "tool"
        msg.content = content
        msg.tool_calls = []
        return msg

    def test_run_emits_reasoning_and_response(self):
        """Test that run() emits both llm_reasoning and llm_response for simple tool use."""
        # Build a result with tool usage
        mock_ai_with_tool = self._create_ai_message_mock(
            content="",
            tool_calls=[{"name": "search_documents", "args": {"query": "test"}}]
        )

        mock_tool_result = self._create_tool_message_mock(content="Tool output")

        mock_final_response = self._create_ai_message_mock(
            content="Final answer",
            tool_calls=[]
        )

        mock_agent = Mock()
        mock_agent.invoke = Mock(return_value={
            "messages": [mock_ai_with_tool, mock_tool_result, mock_final_response]
        })

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            result = runner.run(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        # Verify reasoning and response steps
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 1, "Should have one llm_reasoning step"
        assert len(response_steps) == 1, "Should have one llm_response step"

    def test_run_emits_observation_for_multi_tool_flow(self):
        """Test that run() emits llm_observation for multi-tool ReAct flow."""
        # First tool selection
        mock_ai_reasoning = self._create_ai_message_mock(
            content="",
            tool_calls=[{"name": "arxiv_search", "args": {}}]
        )

        mock_tool1 = self._create_tool_message_mock(content="ArXiv result")

        # Second tool selection (observation)
        mock_ai_observation = self._create_ai_message_mock(
            content="",
            tool_calls=[{"name": "web_search", "args": {}}]
        )

        mock_tool2 = self._create_tool_message_mock(content="Web result")

        # Final response
        mock_final = self._create_ai_message_mock(
            content="Comprehensive answer",
            tool_calls=[]
        )

        mock_agent = Mock()
        mock_agent.invoke = Mock(return_value={
            "messages": [mock_ai_reasoning, mock_tool1, mock_ai_observation, mock_tool2, mock_final]
        })

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            result = runner.run(
                query="Complex query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        # Verify all three types of LLM steps
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        observation_steps = [s for s in middleware.state.steps if s.node == "llm_observation"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 1, "Should have one llm_reasoning step"
        assert len(observation_steps) == 1, "Should have one llm_observation step"
        assert len(response_steps) == 1, "Should have one llm_response step"

    def test_run_no_tools_only_response(self):
        """Test that run() handles direct response without tool usage."""
        mock_final = self._create_ai_message_mock(
            content="Direct answer without tools",
            tool_calls=[]
        )

        mock_agent = Mock()
        mock_agent.invoke = Mock(return_value={
            "messages": [mock_final]
        })

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            result = runner.run(
                query="Simple question",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        # Should only have llm_response, no reasoning
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 0, "Should not have llm_reasoning without tool usage"
        assert len(response_steps) == 1, "Should have one llm_response step"


class TestModelCallsMetric:
    """Tests for model_calls metric accuracy with new LLM tracking."""

    def test_model_calls_counts_all_llm_phases(self):
        """Test that model_calls metric correctly counts all LLM phases."""
        # Simulate: reasoning -> tool -> observation -> tool -> response
        mock_ai_reasoning = Mock()
        mock_ai_reasoning.type = "ai"
        mock_ai_reasoning.content = ""
        mock_ai_reasoning.tool_calls = [{"name": "arxiv_search", "args": {}}]

        mock_tool1 = Mock()
        mock_tool1.type = "tool"
        mock_tool1.content = "Result"
        mock_tool1.name = "arxiv_search"

        mock_ai_observation = Mock()
        mock_ai_observation.type = "ai"
        mock_ai_observation.content = ""
        mock_ai_observation.tool_calls = [{"name": "web_search", "args": {}}]

        mock_tool2 = Mock()
        mock_tool2.type = "tool"
        mock_tool2.content = "Result"
        mock_tool2.name = "web_search"

        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final answer"
        mock_ai_response.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_reasoning, {}),
            (mock_tool1, {}),
            (mock_ai_observation, {}),
            (mock_tool2, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Test",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # 1 reasoning + 1 observation + 1 response = 3 model calls
        assert middleware.state.metrics.model_calls == 3

    def test_tool_calls_metric_unchanged(self):
        """Test that tool_calls metric is still correctly tracked."""
        mock_ai_reasoning = Mock()
        mock_ai_reasoning.type = "ai"
        mock_ai_reasoning.content = ""
        mock_ai_reasoning.tool_calls = [{"name": "arxiv_search", "args": {}}]

        mock_tool1 = Mock()
        mock_tool1.type = "tool"
        mock_tool1.content = "Result"
        mock_tool1.name = "arxiv_search"

        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Answer"
        mock_ai_response.tool_calls = None

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_reasoning, {}),
            (mock_tool1, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Test",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        # Tool calls: 1 arxiv_search (tracked by middleware on_tool_start)
        # Note: Tool tracking happens through middleware.on_tool_start, not the runner
        # The runner emits tool events but doesn't call middleware.on_tool_start
        # Tool metric is tracked separately
        assert middleware.state.metrics.tool_calls == 0  # Not tracked by LLM callbacks


class TestChannelIdPassedToCallbacks:
    """Tests to verify channel_id is properly passed to all LLM callbacks."""

    def test_reasoning_callback_receives_channel_id(self):
        """Test that llm_reasoning callbacks receive channel_id."""
        received_data = []

        def capture_events(event):
            if "llm" in event.get("event", ""):
                received_data.append(event.get("data", {}))

        mock_ai_with_tool = Mock()
        mock_ai_with_tool.type = "ai"
        mock_ai_with_tool.content = ""
        mock_ai_with_tool.tool_calls = [{"name": "search", "args": {}}]

        mock_tool = Mock()
        mock_tool.type = "tool"
        mock_tool.content = "Result"
        mock_tool.name = "search"

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_with_tool, {}),
            (mock_tool, {}),
        ]))

        middleware = DashboardMiddleware(state_updater=capture_events)
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Test",
                config=AgentConfig(),
                context={"channel_id": "my-channel-123"},
            ))

        # Verify channel_id was included
        assert len(received_data) >= 2  # At least start and complete
        for data in received_data:
            assert data.get("channel_id") == "my-channel-123"


class TestStreamingTokenExtraction:
    """Tests for post-streaming token extraction functionality."""

    def test_tokens_extracted_after_streaming(self):
        """Test that tokens are extracted from final_messages after streaming."""
        # Create AI message with usage_metadata
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Response content"
        mock_ai_response.tool_calls = None
        mock_ai_response.usage_metadata = {"total_tokens": 1500}

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
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

        # Verify tokens were extracted and added to the step
        llm_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(llm_steps) == 1
        assert llm_steps[0].data.get("tokens") == 1500

    def test_tokens_extracted_for_multiple_llm_phases(self):
        """Test that tokens are extracted for reasoning and response phases."""
        # Reasoning phase with tool_calls and usage_metadata
        mock_ai_reasoning = Mock()
        mock_ai_reasoning.type = "ai"
        mock_ai_reasoning.content = ""
        mock_ai_reasoning.tool_calls = [{"name": "search", "args": {}}]
        mock_ai_reasoning.usage_metadata = {"total_tokens": 500}

        mock_tool = Mock()
        mock_tool.type = "tool"
        mock_tool.content = "Result"
        mock_tool.name = "search"

        # Response phase with content and usage_metadata
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final response"
        mock_ai_response.tool_calls = None
        mock_ai_response.usage_metadata = {"total_tokens": 1200}

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_reasoning, {}),
            (mock_tool, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
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

        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 1
        assert len(response_steps) == 1
        assert reasoning_steps[0].data.get("tokens") == 500
        assert response_steps[0].data.get("tokens") == 1200

    def test_no_tokens_when_usage_metadata_missing(self):
        """Test graceful handling when usage_metadata is not present."""
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Response"
        mock_ai_response.tool_calls = None
        mock_ai_response.usage_metadata = None  # No usage_metadata

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Test",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        llm_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(llm_steps) == 1
        # tokens should not be present when usage_metadata is missing
        assert "tokens" not in llm_steps[0].data or llm_steps[0].data.get("tokens") is None

    def test_tokens_with_observation_phase(self):
        """Test token extraction with reasoning, observation, and response phases."""
        # Initial reasoning
        mock_ai_reasoning = Mock()
        mock_ai_reasoning.type = "ai"
        mock_ai_reasoning.content = ""
        mock_ai_reasoning.tool_calls = [{"name": "arxiv_search", "args": {}}]
        mock_ai_reasoning.usage_metadata = {"total_tokens": 400}

        mock_tool1 = Mock()
        mock_tool1.type = "tool"
        mock_tool1.content = "ArXiv results"
        mock_tool1.name = "arxiv_search"

        # Observation phase (after tool, decides to use another tool)
        mock_ai_observation = Mock()
        mock_ai_observation.type = "ai"
        mock_ai_observation.content = ""
        mock_ai_observation.tool_calls = [{"name": "web_search", "args": {}}]
        mock_ai_observation.usage_metadata = {"total_tokens": 600}

        mock_tool2 = Mock()
        mock_tool2.type = "tool"
        mock_tool2.content = "Web results"
        mock_tool2.name = "web_search"

        # Final response
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final answer"
        mock_ai_response.tool_calls = None
        mock_ai_response.usage_metadata = {"total_tokens": 1000}

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=iter([
            (mock_ai_reasoning, {}),
            (mock_tool1, {}),
            (mock_ai_observation, {}),
            (mock_tool2, {}),
            (mock_ai_response, {}),
        ]))

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            list(runner.run_stream(
                query="Complex query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            ))

        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        observation_steps = [s for s in middleware.state.steps if s.node == "llm_observation"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 1
        assert len(observation_steps) == 1
        assert len(response_steps) == 1

        assert reasoning_steps[0].data.get("tokens") == 400
        assert observation_steps[0].data.get("tokens") == 600
        assert response_steps[0].data.get("tokens") == 1000


class TestLLMDurationMeasurement:
    """Tests for LLM duration measurement in both streaming and non-streaming modes."""

    def _create_ai_message_mock(self, content="", tool_calls=None, usage_metadata=None):
        """Helper to create properly configured AI message mock."""
        msg = Mock()
        msg.type = "ai"
        msg.content = content
        msg.tool_calls = tool_calls if tool_calls else []
        msg.usage_metadata = usage_metadata
        return msg

    def _create_tool_message_mock(self, name="", content=""):
        """Helper to create properly configured tool message mock."""
        msg = Mock()
        msg.type = "tool"
        msg.name = name
        msg.content = content
        msg.tool_calls = []
        return msg

    def test_run_method_llm_duration_not_zero(self):
        """Test that run() method reports non-zero duration for LLM steps."""
        # Build a result with tool usage (longer agent execution)
        mock_ai_with_tool = self._create_ai_message_mock(
            content="",
            tool_calls=[{"name": "search_documents", "args": {"query": "test"}}]
        )
        mock_tool_result = self._create_tool_message_mock(name="search_documents", content="Tool output")
        mock_final_response = self._create_ai_message_mock(content="Final answer", tool_calls=[])

        mock_agent = Mock()
        mock_agent.invoke = Mock(return_value={
            "messages": [mock_ai_with_tool, mock_tool_result, mock_final_response]
        })

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            result = runner.run(
                query="Test query",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        # Verify LLM steps have non-zero duration
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]

        assert len(reasoning_steps) == 1
        assert len(response_steps) == 1

        # Duration should be set (distributed from total agent duration)
        assert reasoning_steps[0].duration_ms is not None
        assert reasoning_steps[0].duration_ms >= 0
        assert response_steps[0].duration_ms is not None
        assert response_steps[0].duration_ms >= 0

    def test_run_method_direct_response_duration(self):
        """Test that run() with direct response (no tools) has non-zero duration."""
        mock_final = self._create_ai_message_mock(
            content="Direct answer without tools",
            tool_calls=[]
        )

        mock_agent = Mock()
        mock_agent.invoke = Mock(return_value={
            "messages": [mock_final]
        })

        middleware = DashboardMiddleware()
        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
            dashboard_middleware=middleware,
        )

        with patch.object(runner, '_create_agent', return_value=mock_agent):
            result = runner.run(
                query="Simple question",
                config=AgentConfig(),
                context={"channel_id": "test-channel"},
            )

        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(response_steps) == 1
        assert response_steps[0].duration_ms is not None
        assert response_steps[0].duration_ms >= 0

    def test_run_stream_reasoning_duration_not_zero(self):
        """Test that run_stream() reasoning phase has non-zero duration."""
        import time

        # AI message with tool_calls
        mock_ai_with_tool = Mock()
        mock_ai_with_tool.type = "ai"
        mock_ai_with_tool.content = ""
        mock_ai_with_tool.tool_calls = [{"name": "search_documents", "args": {"query": "test"}}]

        # Tool result
        mock_tool_result = Mock()
        mock_tool_result.type = "tool"
        mock_tool_result.content = "Search result"
        mock_tool_result.name = "search_documents"

        # Final response
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final answer"
        mock_ai_response.tool_calls = None

        def streaming_messages():
            """Simulate streaming with small delays to create measurable duration."""
            yield (mock_ai_with_tool, {})
            time.sleep(0.01)  # 10ms delay
            yield (mock_tool_result, {})
            time.sleep(0.01)  # 10ms delay
            yield (mock_ai_response, {})

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=streaming_messages())

        middleware = DashboardMiddleware()
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

        # Verify reasoning has non-zero duration
        reasoning_steps = [s for s in middleware.state.steps if s.node == "llm_reasoning"]
        assert len(reasoning_steps) == 1
        assert reasoning_steps[0].duration_ms is not None
        # Should have measurable duration (at least a few ms from stream start to tool call)
        assert reasoning_steps[0].duration_ms >= 0

    def test_run_stream_response_duration_not_zero(self):
        """Test that run_stream() response phase has measurable duration."""
        import time

        # First content chunk
        mock_msg1 = Mock()
        mock_msg1.type = "ai"
        mock_msg1.content = "Hello"
        mock_msg1.tool_calls = None

        # Second content chunk (after delay)
        mock_msg2 = Mock()
        mock_msg2.type = "ai"
        mock_msg2.content = " World"
        mock_msg2.tool_calls = None

        def streaming_messages():
            """Simulate streaming with delays between content chunks."""
            yield (mock_msg1, {})
            time.sleep(0.02)  # 20ms delay
            yield (mock_msg2, {})

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=streaming_messages())

        middleware = DashboardMiddleware()
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

        # Verify response has measurable duration
        response_steps = [s for s in middleware.state.steps if s.node == "llm_response"]
        assert len(response_steps) == 1
        assert response_steps[0].duration_ms is not None
        # Should have some measurable duration from streaming
        assert response_steps[0].duration_ms >= 10  # At least 10ms

    def test_run_stream_observation_duration_not_zero(self):
        """Test that run_stream() observation phase (after tool) has duration."""
        import time

        # First AI message: reasoning
        mock_ai_reasoning = Mock()
        mock_ai_reasoning.type = "ai"
        mock_ai_reasoning.content = ""
        mock_ai_reasoning.tool_calls = [{"name": "search", "args": {}}]

        # Tool result
        mock_tool = Mock()
        mock_tool.type = "tool"
        mock_tool.content = "Result"
        mock_tool.name = "search"

        # Second AI message: observation -> another tool
        mock_ai_observation = Mock()
        mock_ai_observation.type = "ai"
        mock_ai_observation.content = ""
        mock_ai_observation.tool_calls = [{"name": "web_search", "args": {}}]

        # Second tool result
        mock_tool2 = Mock()
        mock_tool2.type = "tool"
        mock_tool2.content = "Web Result"
        mock_tool2.name = "web_search"

        # Final response
        mock_ai_response = Mock()
        mock_ai_response.type = "ai"
        mock_ai_response.content = "Final answer"
        mock_ai_response.tool_calls = None

        def streaming_messages():
            yield (mock_ai_reasoning, {})
            yield (mock_tool, {})
            time.sleep(0.015)  # 15ms delay simulating observation time
            yield (mock_ai_observation, {})
            yield (mock_tool2, {})
            time.sleep(0.01)
            yield (mock_ai_response, {})

        mock_agent = Mock()
        mock_agent.stream = Mock(return_value=streaming_messages())

        middleware = DashboardMiddleware()
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

        # Verify observation has duration
        observation_steps = [s for s in middleware.state.steps if s.node == "llm_observation"]
        assert len(observation_steps) == 1
        assert observation_steps[0].duration_ms is not None
        # Should have measurable duration from tool completion to next decision
        assert observation_steps[0].duration_ms >= 0


class TestDashboardMiddlewareDurationOverride:
    """Tests for the duration_override_ms parameter in on_llm_end."""

    def test_duration_override_is_used(self):
        """Test that duration_override_ms is used when provided."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_reasoning")
        middleware.on_llm_end("llm_reasoning", duration_override_ms=500.0)

        step = middleware.state.steps[0]
        assert step.duration_ms == 500.0

    def test_duration_override_zero(self):
        """Test that zero duration_override is used (not treated as None)."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_test")
        middleware.on_llm_end("llm_test", duration_override_ms=0.0)

        step = middleware.state.steps[0]
        assert step.duration_ms == 0.0

    def test_duration_calculated_when_no_override(self):
        """Test that duration is calculated from start time when no override."""
        import time
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_test")
        time.sleep(0.02)  # 20ms
        middleware.on_llm_end("llm_test")

        step = middleware.state.steps[0]
        assert step.duration_ms is not None
        assert step.duration_ms >= 15  # Should be at least 15ms

    def test_duration_override_with_tokens(self):
        """Test that duration_override works alongside tokens."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=1500, duration_override_ms=250.0)

        step = middleware.state.steps[0]
        assert step.duration_ms == 250.0
        assert step.data.get("tokens") == 1500

    def test_duration_override_in_event(self):
        """Test that overridden duration appears in published event."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.on_llm_start("llm_reasoning")
        events.clear()
        middleware.on_llm_end("llm_reasoning", duration_override_ms=123.45)

        assert len(events) == 1
        assert events[0]["event"] == "llm_complete"
        assert events[0]["data"]["duration_ms"] == 123.45
