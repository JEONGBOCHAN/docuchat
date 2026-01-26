# -*- coding: utf-8 -*-
"""Tests for the DashboardMiddleware implementation."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.agents.middlewares.dashboard import (
    DashboardMiddleware,
    DashboardState,
    StepRecord,
    AgentMetrics,
    NodeStatus,
    AgentStatus,
    EventType,
)


class TestNodeStatus:
    """Tests for NodeStatus enum."""

    def test_status_values(self):
        """Test that NodeStatus has expected values."""
        assert NodeStatus.IDLE.value == "idle"
        assert NodeStatus.RUNNING.value == "running"
        assert NodeStatus.COMPLETE.value == "complete"
        assert NodeStatus.ERROR.value == "error"


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_status_values(self):
        """Test that AgentStatus has expected values."""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.COMPLETE.value == "complete"
        assert AgentStatus.ERROR.value == "error"


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self):
        """Test that EventType has expected values."""
        assert EventType.AGENT_START.value == "agent_start"
        assert EventType.AGENT_COMPLETE.value == "agent_complete"
        assert EventType.AGENT_ERROR.value == "agent_error"
        assert EventType.NODE_START.value == "node_start"
        assert EventType.NODE_COMPLETE.value == "node_complete"
        assert EventType.NODE_ERROR.value == "node_error"
        assert EventType.MODEL_START.value == "model_start"
        assert EventType.MODEL_COMPLETE.value == "model_complete"
        assert EventType.TOOL_START.value == "tool_start"
        assert EventType.TOOL_COMPLETE.value == "tool_complete"
        assert EventType.TOOL_ERROR.value == "tool_error"


class TestStepRecord:
    """Tests for StepRecord dataclass."""

    def test_step_record_defaults(self):
        """Test StepRecord default values."""
        step = StepRecord(node="test_node", status=NodeStatus.RUNNING)

        assert step.node == "test_node"
        assert step.status == NodeStatus.RUNNING
        assert step.data == {}
        assert step.timestamp is not None
        assert step.duration_ms is None

    def test_step_record_with_data(self):
        """Test StepRecord with custom data."""
        step = StepRecord(
            node="search",
            status=NodeStatus.COMPLETE,
            data={"query": "test query"},
            duration_ms=150.5,
        )

        assert step.node == "search"
        assert step.status == NodeStatus.COMPLETE
        assert step.data == {"query": "test query"}
        assert step.duration_ms == 150.5


class TestAgentMetrics:
    """Tests for AgentMetrics dataclass."""

    def test_metrics_defaults(self):
        """Test AgentMetrics default values."""
        metrics = AgentMetrics()

        assert metrics.total_steps == 0
        assert metrics.model_calls == 0
        assert metrics.tool_calls == 0
        assert metrics.start_time is None
        assert metrics.end_time is None
        assert metrics.total_duration_ms is None

    def test_metrics_with_values(self):
        """Test AgentMetrics with custom values."""
        metrics = AgentMetrics(
            total_steps=5,
            model_calls=2,
            tool_calls=3,
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:00:10",
            total_duration_ms=10000,
        )

        assert metrics.total_steps == 5
        assert metrics.model_calls == 2
        assert metrics.tool_calls == 3
        assert metrics.total_duration_ms == 10000


class TestDashboardState:
    """Tests for DashboardState dataclass."""

    def test_state_defaults(self):
        """Test DashboardState default values."""
        state = DashboardState()

        assert state.status == AgentStatus.IDLE
        assert state.current_node is None
        assert state.steps == []
        assert isinstance(state.metrics, AgentMetrics)

    def test_state_to_dict(self):
        """Test DashboardState serialization to dict."""
        step = StepRecord(
            node="Draft",
            status=NodeStatus.COMPLETE,
            data={"test": "value"},
            duration_ms=100,
        )
        state = DashboardState(
            status=AgentStatus.RUNNING,
            current_node="Reflect",
            steps=[step],
        )
        state.metrics.total_steps = 1

        result = state.to_dict()

        assert result["status"] == "running"
        assert result["current_node"] == "Reflect"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["node"] == "Draft"
        assert result["steps"][0]["status"] == "complete"
        assert result["steps"][0]["data"] == {"test": "value"}
        assert result["metrics"]["total_steps"] == 1


class TestDashboardMiddleware:
    """Tests for DashboardMiddleware class."""

    def test_init_default(self):
        """Test middleware initialization with defaults."""
        middleware = DashboardMiddleware()

        assert middleware.name == "dashboard_middleware"
        assert middleware._state_updater is None
        assert middleware.state.status == AgentStatus.IDLE

    def test_init_with_state_updater(self):
        """Test middleware initialization with state_updater."""
        updater = Mock()
        middleware = DashboardMiddleware(state_updater=updater, name="custom_name")

        assert middleware.name == "custom_name"
        assert middleware._state_updater == updater

    def test_reset(self):
        """Test middleware reset functionality."""
        middleware = DashboardMiddleware()
        middleware._state.status = AgentStatus.RUNNING
        middleware._state.steps.append(
            StepRecord(node="test", status=NodeStatus.COMPLETE)
        )

        middleware.reset()

        assert middleware.state.status == AgentStatus.IDLE
        assert middleware.state.steps == []
        assert middleware._current_model_node is None

    def test_get_state_dict(self):
        """Test get_state_dict method."""
        middleware = DashboardMiddleware()
        middleware._state.status = AgentStatus.RUNNING

        result = middleware.get_state_dict()

        assert isinstance(result, dict)
        assert result["status"] == "running"


class TestDashboardMiddlewareBeforeAgent:
    """Tests for before_agent hook."""

    def test_before_agent_initializes_state(self):
        """Test that before_agent initializes state correctly."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        state = {"messages": [{"role": "user", "content": "Hello world"}]}
        result = middleware.before_agent(state, Mock())

        assert result is None
        assert middleware.state.status == AgentStatus.RUNNING
        assert middleware.state.metrics.start_time is not None

    def test_before_agent_publishes_event(self):
        """Test that before_agent publishes agent_start event."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        state = {"messages": [{"role": "user", "content": "Test query"}]}
        middleware.before_agent(state, Mock())

        assert len(events) == 1
        assert events[0]["event"] == "agent_start"
        assert "timestamp" in events[0]
        assert events[0]["data"]["query"] == "Test query"

    def test_before_agent_extracts_query_from_message_object(self):
        """Test query extraction from message object."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        mock_message = Mock()
        mock_message.content = "Query from message object"
        state = {"messages": [mock_message]}

        middleware.before_agent(state, Mock())

        assert events[0]["data"]["query"] == "Query from message object"


class TestDashboardMiddlewareAfterAgent:
    """Tests for after_agent hook."""

    def test_after_agent_success(self):
        """Test after_agent on successful completion."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        # Simulate agent start
        middleware.before_agent({"messages": []}, Mock())
        events.clear()

        # Simulate completion
        mock_message = Mock()
        mock_message.content = "Final response"
        state = {"messages": [mock_message]}

        result = middleware.after_agent(state, Mock())

        assert result is None
        assert middleware.state.status == AgentStatus.COMPLETE
        assert middleware.state.metrics.end_time is not None
        assert len(events) == 1
        assert events[0]["event"] == "agent_complete"
        assert events[0]["data"]["response_preview"] == "Final response"

    def test_after_agent_error(self):
        """Test after_agent with error state."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        # Simulate agent start
        middleware.before_agent({"messages": []}, Mock())
        events.clear()

        # Simulate error
        state = {"error": "Something went wrong", "messages": []}
        middleware.after_agent(state, Mock())

        assert middleware.state.status == AgentStatus.ERROR
        assert len(events) == 1
        assert events[0]["event"] == "agent_error"
        assert events[0]["error"] == "Something went wrong"

    def test_after_agent_calculates_duration(self):
        """Test that after_agent calculates total duration."""
        middleware = DashboardMiddleware()

        # Simulate start with a known time
        middleware.before_agent({"messages": []}, Mock())

        # Simulate completion
        middleware.after_agent({"messages": []}, Mock())

        assert middleware.state.metrics.total_duration_ms is not None
        assert middleware.state.metrics.total_duration_ms >= 0


class TestDashboardMiddlewareModelHooks:
    """Tests for before_model and after_model hooks."""

    def test_before_model_first_call_is_draft(self):
        """Test that first model call is detected as Draft."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        result = middleware.before_model({"messages": []}, Mock())

        assert result is None
        assert middleware.state.current_node == "Draft"
        assert middleware.state.metrics.model_calls == 1
        assert middleware.state.metrics.total_steps == 1

    def test_before_model_second_call_is_reflect(self):
        """Test that second model call is detected as Reflect."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        # First call
        middleware.before_model({"messages": []}, Mock())
        middleware.after_model({"messages": []}, Mock())

        # Second call
        middleware.before_model({"messages": []}, Mock())

        assert middleware.state.current_node == "Reflect"
        assert middleware.state.metrics.model_calls == 2

    def test_before_model_third_call_is_revise(self):
        """Test that third+ model call is detected as Revise."""
        middleware = DashboardMiddleware()

        # First and second calls
        middleware.before_model({"messages": []}, Mock())
        middleware.after_model({"messages": []}, Mock())
        middleware.before_model({"messages": []}, Mock())
        middleware.after_model({"messages": []}, Mock())

        # Third call
        middleware.before_model({"messages": []}, Mock())

        assert middleware.state.current_node == "Revise"
        assert middleware.state.metrics.model_calls == 3

    def test_after_model_completes_step(self):
        """Test that after_model marks step as complete."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.before_model({"messages": []}, Mock())
        middleware.after_model({"messages": []}, Mock())

        # Find the Draft step
        draft_steps = [s for s in middleware.state.steps if s.node == "Draft"]
        assert len(draft_steps) == 1
        assert draft_steps[0].status == NodeStatus.COMPLETE
        assert draft_steps[0].duration_ms is not None

    def test_before_model_publishes_event(self):
        """Test that before_model publishes model_start event."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.before_model({"messages": []}, Mock())

        assert len(events) == 1
        assert events[0]["event"] == "model_start"
        assert events[0]["node"] == "Draft"
        assert events[0]["data"]["type"] == "model"

    def test_after_model_publishes_event(self):
        """Test that after_model publishes model_complete event."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.before_model({"messages": []}, Mock())
        events.clear()
        middleware.after_model({"messages": []}, Mock())

        assert len(events) == 1
        assert events[0]["event"] == "model_complete"
        assert events[0]["node"] == "Draft"
        assert "duration_ms" in events[0]["data"]


class TestDashboardMiddlewareToolHooks:
    """Tests for wrap_tool_call hook."""

    def _create_mock_request(self, tool_name: str, args: dict) -> Mock:
        """Create a mock ToolCallRequest."""
        request = Mock()
        request.tool_call = {"name": tool_name, "args": args}
        return request

    def test_wrap_tool_call_success(self):
        """Test successful tool call wrapping."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        request = self._create_mock_request("search_documents", {"query": "test"})
        mock_result = Mock()
        mock_result.content = "Search results here"
        handler = Mock(return_value=mock_result)

        result = middleware.wrap_tool_call(request, handler)

        assert result == mock_result
        handler.assert_called_once_with(request)

        # Check events
        assert len(events) == 2
        assert events[0]["event"] == "tool_start"
        assert events[0]["node"] == "search_documents"
        assert events[1]["event"] == "tool_complete"
        assert events[1]["node"] == "search_documents"

    def test_wrap_tool_call_error(self):
        """Test tool call wrapping with error."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        request = self._create_mock_request("search_documents", {"query": "test"})
        handler = Mock(side_effect=ValueError("Tool error"))

        with pytest.raises(ValueError, match="Tool error"):
            middleware.wrap_tool_call(request, handler)

        # Check events
        assert len(events) == 2
        assert events[0]["event"] == "tool_start"
        assert events[1]["event"] == "tool_error"
        assert events[1]["error"] == "Tool error"

    def test_wrap_tool_call_updates_metrics(self):
        """Test that wrap_tool_call updates metrics."""
        middleware = DashboardMiddleware()

        request = self._create_mock_request("search_documents", {})
        handler = Mock(return_value=Mock(content="result"))

        middleware.wrap_tool_call(request, handler)

        assert middleware.state.metrics.tool_calls == 1
        assert middleware.state.metrics.total_steps == 1

    def test_wrap_tool_call_records_step(self):
        """Test that wrap_tool_call creates a step record."""
        middleware = DashboardMiddleware()

        request = self._create_mock_request("finish", {"answer": "Final answer"})
        handler = Mock(return_value=Mock(content="Final answer"))

        middleware.wrap_tool_call(request, handler)

        finish_steps = [s for s in middleware.state.steps if s.node == "finish"]
        assert len(finish_steps) == 1
        assert finish_steps[0].status == NodeStatus.COMPLETE
        assert finish_steps[0].duration_ms is not None

    def test_wrap_tool_call_error_marks_step(self):
        """Test that tool error marks step with error status."""
        middleware = DashboardMiddleware()

        request = self._create_mock_request("search_documents", {})
        handler = Mock(side_effect=RuntimeError("API Error"))

        with pytest.raises(RuntimeError):
            middleware.wrap_tool_call(request, handler)

        error_steps = [s for s in middleware.state.steps if s.status == NodeStatus.ERROR]
        assert len(error_steps) == 1
        assert error_steps[0].node == "search_documents"
        assert error_steps[0].data.get("error") == "API Error"


class TestDashboardMiddlewareIntegration:
    """Integration tests for the middleware lifecycle."""

    def test_full_agent_lifecycle(self):
        """Test a complete agent execution lifecycle."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        # 1. Agent starts
        middleware.before_agent({"messages": [{"content": "What is X?"}]}, Mock())

        # 2. First model call (Draft)
        middleware.before_model({"messages": []}, Mock())
        middleware.after_model({"messages": []}, Mock())

        # 3. Tool call (search)
        search_request = Mock()
        search_request.tool_call = {"name": "search_documents", "args": {"query": "X"}}
        middleware.wrap_tool_call(
            search_request,
            Mock(return_value=Mock(content="Found info about X"))
        )

        # 4. Second model call (Reflect)
        middleware.before_model({"messages": []}, Mock())
        middleware.after_model({"messages": []}, Mock())

        # 5. Tool call (finish)
        finish_request = Mock()
        finish_request.tool_call = {"name": "finish", "args": {"answer": "X is..."}}
        middleware.wrap_tool_call(
            finish_request,
            Mock(return_value=Mock(content="X is..."))
        )

        # 6. Agent completes
        middleware.after_agent({"messages": [Mock(content="X is...")]}, Mock())

        # Verify final state
        assert middleware.state.status == AgentStatus.COMPLETE
        assert middleware.state.metrics.model_calls == 2
        assert middleware.state.metrics.tool_calls == 2
        assert middleware.state.metrics.total_steps == 4
        assert middleware.state.metrics.total_duration_ms is not None

        # Verify events
        event_types = [e["event"] for e in events]
        assert "agent_start" in event_types
        assert "model_start" in event_types
        assert "model_complete" in event_types
        assert "tool_start" in event_types
        assert "tool_complete" in event_types
        assert "agent_complete" in event_types

    def test_error_recovery_scenario(self):
        """Test middleware behavior during an error scenario."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        # Agent starts
        middleware.before_agent({"messages": []}, Mock())

        # Model call succeeds
        middleware.before_model({"messages": []}, Mock())
        middleware.after_model({"messages": []}, Mock())

        # Tool call fails
        request = Mock()
        request.tool_call = {"name": "search_documents", "args": {}}
        with pytest.raises(Exception):
            middleware.wrap_tool_call(request, Mock(side_effect=Exception("API down")))

        # Agent completes with error
        middleware.after_agent({"error": "API down", "messages": []}, Mock())

        # Verify error state
        assert middleware.state.status == AgentStatus.ERROR

        # Check that tool error was recorded
        error_events = [e for e in events if e["event"] == "tool_error"]
        assert len(error_events) == 1

    def test_multiple_tool_calls(self):
        """Test middleware with multiple consecutive tool calls."""
        middleware = DashboardMiddleware()

        middleware.before_agent({"messages": []}, Mock())

        # Multiple search calls
        for i in range(3):
            request = Mock()
            request.tool_call = {"name": f"search_{i}", "args": {"query": f"query_{i}"}}
            middleware.wrap_tool_call(
                request, Mock(return_value=Mock(content=f"result_{i}"))
            )

        assert middleware.state.metrics.tool_calls == 3
        assert len(middleware.state.steps) == 3

    def test_state_dict_serialization_throughout_lifecycle(self):
        """Test that state can be serialized at any point."""
        middleware = DashboardMiddleware()

        # Before anything
        state1 = middleware.get_state_dict()
        assert state1["status"] == "idle"

        # After start
        middleware.before_agent({"messages": []}, Mock())
        state2 = middleware.get_state_dict()
        assert state2["status"] == "running"

        # After model call
        middleware.before_model({"messages": []}, Mock())
        state3 = middleware.get_state_dict()
        assert state3["current_node"] == "Draft"

        # All states should be valid dicts
        for state in [state1, state2, state3]:
            assert isinstance(state, dict)
            assert "status" in state
            assert "current_node" in state
            assert "steps" in state
            assert "metrics" in state


class TestDashboardMiddlewareLLMHooks:
    """Tests for on_llm_start and on_llm_end hooks."""

    def test_on_llm_start_updates_state(self):
        """Test that on_llm_start correctly updates middleware state."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.on_llm_start("llm_draft", {"prompt_length": 100})

        assert middleware.state.current_node == "llm_draft"
        assert middleware.state.metrics.model_calls == 1
        assert middleware.state.metrics.total_steps == 1

        # Check step was recorded
        assert len(middleware.state.steps) == 1
        step = middleware.state.steps[0]
        assert step.node == "llm_draft"
        assert step.status == NodeStatus.RUNNING
        assert step.data["type"] == "llm"
        assert step.data["prompt_length"] == 100

    def test_on_llm_end_completes_step(self):
        """Test that on_llm_end marks step as complete with duration."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_reflect")
        middleware.on_llm_end("llm_reflect", {"response_length": 500})

        step = middleware.state.steps[0]
        assert step.status == NodeStatus.COMPLETE
        assert step.duration_ms is not None
        assert step.duration_ms >= 0

    def test_on_llm_start_publishes_event(self):
        """Test that on_llm_start publishes LLM_START event."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.on_llm_start("llm_draft")

        assert len(events) == 1
        assert events[0]["event"] == "llm_start"
        assert events[0]["node"] == "llm_draft"
        assert events[0]["data"]["type"] == "llm"

    def test_on_llm_end_publishes_event(self):
        """Test that on_llm_end publishes LLM_COMPLETE event."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.on_llm_start("llm_revise")
        events.clear()
        middleware.on_llm_end("llm_revise")

        assert len(events) == 1
        assert events[0]["event"] == "llm_complete"
        assert events[0]["node"] == "llm_revise"
        assert "duration_ms" in events[0]["data"]
        assert events[0]["data"]["type"] == "llm"

    def test_multiple_llm_calls_sequence(self):
        """Test sequence of LLM calls (draft -> reflect -> revise)."""
        middleware = DashboardMiddleware()

        # Draft
        middleware.on_llm_start("llm_draft")
        middleware.on_llm_end("llm_draft")

        # Reflect
        middleware.on_llm_start("llm_reflect")
        middleware.on_llm_end("llm_reflect")

        # Revise
        middleware.on_llm_start("llm_revise")
        middleware.on_llm_end("llm_revise")

        assert middleware.state.metrics.model_calls == 3
        assert middleware.state.metrics.total_steps == 3
        assert len(middleware.state.steps) == 3

        # Verify all steps completed
        for step in middleware.state.steps:
            assert step.status == NodeStatus.COMPLETE
            assert step.data["type"] == "llm"

    def test_llm_and_tool_calls_mixed(self):
        """Test LLM calls mixed with tool calls."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        # LLM call
        middleware.on_llm_start("llm_draft")
        middleware.on_llm_end("llm_draft")

        # Tool call
        middleware.on_tool_start("search_documents", {"query": "test"})
        middleware.on_tool_end("search_documents", {"results": 5})

        # Another LLM call
        middleware.on_llm_start("llm_reflect")
        middleware.on_llm_end("llm_reflect")

        assert middleware.state.metrics.model_calls == 2
        assert middleware.state.metrics.tool_calls == 1
        assert middleware.state.metrics.total_steps == 3

        # Verify step types
        llm_steps = [s for s in middleware.state.steps if s.data.get("type") == "llm"]
        tool_steps = [s for s in middleware.state.steps if s.data.get("type") == "tool"]
        assert len(llm_steps) == 2
        assert len(tool_steps) == 1

    def test_on_llm_start_with_no_data(self):
        """Test on_llm_start works with no additional data."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_draft")

        step = middleware.state.steps[0]
        assert step.data["type"] == "llm"

    def test_on_llm_end_with_no_data(self):
        """Test on_llm_end works with no additional data."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_draft")
        middleware.on_llm_end("llm_draft")

        step = middleware.state.steps[0]
        assert step.status == NodeStatus.COMPLETE

    def test_llm_event_type_values(self):
        """Test that LLM event types have expected values."""
        assert EventType.LLM_START.value == "llm_start"
        assert EventType.LLM_COMPLETE.value == "llm_complete"


class TestDashboardMiddlewareLLMIntegration:
    """Integration tests for LLM callbacks with full agent lifecycle."""

    def test_full_lifecycle_with_llm_callbacks(self):
        """Test complete agent execution using on_llm_start/on_llm_end."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        # 1. Agent starts
        middleware.on_agent_start({"query": "What is AI?"})

        # 2. LLM Draft
        middleware.on_llm_start("llm_draft", {"prompt_length": 50})
        middleware.on_llm_end("llm_draft", {"response_length": 200})

        # 3. Tool call
        middleware.on_tool_start("search_documents", {"query": "AI"})
        middleware.on_tool_end("search_documents", {"results": 3})

        # 4. LLM Reflect
        middleware.on_llm_start("llm_reflect", {"prompt_length": 300})
        middleware.on_llm_end("llm_reflect", {"response_length": 150})

        # 5. LLM Revise
        middleware.on_llm_start("llm_revise", {"prompt_length": 450})
        middleware.on_llm_end("llm_revise", {"response_length": 500})

        # 6. Agent completes
        middleware.on_agent_end({"response": "AI is..."})

        # Verify final state
        assert middleware.state.status == AgentStatus.COMPLETE
        assert middleware.state.metrics.model_calls == 3
        assert middleware.state.metrics.tool_calls == 1
        assert middleware.state.metrics.total_steps == 4

        # Verify events include llm_start and llm_complete
        event_types = [e["event"] for e in events]
        assert "agent_start" in event_types
        assert "llm_start" in event_types
        assert "llm_complete" in event_types
        assert "tool_start" in event_types
        assert "tool_complete" in event_types
        assert "agent_complete" in event_types

        # Count LLM events
        llm_start_events = [e for e in events if e["event"] == "llm_start"]
        llm_complete_events = [e for e in events if e["event"] == "llm_complete"]
        assert len(llm_start_events) == 3
        assert len(llm_complete_events) == 3

    def test_llm_step_distinguishable_from_tool(self):
        """Test that LLM steps are distinguishable from tool steps in state dict."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_draft")
        middleware.on_llm_end("llm_draft")
        middleware.on_tool_start("search", {"query": "test"})
        middleware.on_tool_end("search", {})

        state_dict = middleware.get_state_dict()

        # Verify steps have type field
        llm_step = state_dict["steps"][0]
        tool_step = state_dict["steps"][1]

        assert llm_step["data"]["type"] == "llm"
        assert tool_step["data"]["type"] == "tool"


class TestDashboardMiddlewareLLMTokens:
    """Tests for LLM token usage tracking in on_llm_end."""

    def test_on_llm_end_with_tokens(self):
        """Test that on_llm_end records token usage."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_draft")
        middleware.on_llm_end("llm_draft", tokens=1500)

        step = middleware.state.steps[0]
        assert step.status == NodeStatus.COMPLETE
        assert step.data.get("tokens") == 1500

    def test_on_llm_end_without_tokens(self):
        """Test that on_llm_end works when tokens is None."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_draft")
        middleware.on_llm_end("llm_draft", tokens=None)

        step = middleware.state.steps[0]
        assert step.status == NodeStatus.COMPLETE
        assert "tokens" not in step.data

    def test_on_llm_end_tokens_in_event(self):
        """Test that tokens are included in LLM_COMPLETE event data."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.on_llm_start("llm_response")
        events.clear()
        middleware.on_llm_end("llm_response", tokens=2500)

        assert len(events) == 1
        assert events[0]["event"] == "llm_complete"
        assert events[0]["data"]["tokens"] == 2500

    def test_on_llm_end_tokens_not_in_event_when_none(self):
        """Test that tokens are not in event when None."""
        events = []
        middleware = DashboardMiddleware(state_updater=lambda e: events.append(e))

        middleware.on_llm_start("llm_response")
        events.clear()
        middleware.on_llm_end("llm_response", tokens=None)

        assert len(events) == 1
        assert events[0]["event"] == "llm_complete"
        assert "tokens" not in events[0]["data"]

    def test_on_llm_end_with_data_and_tokens(self):
        """Test that tokens work alongside other data."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_reflect", {"prompt_length": 100})
        middleware.on_llm_end("llm_reflect", {"response_length": 200}, tokens=850)

        step = middleware.state.steps[0]
        assert step.data["type"] == "llm"
        assert step.data["prompt_length"] == 100
        assert step.data["tokens"] == 850

    def test_multiple_llm_calls_with_different_tokens(self):
        """Test multiple LLM calls each with different token counts."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_reasoning")
        middleware.on_llm_end("llm_reasoning", tokens=500)

        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=1200)

        assert middleware.state.steps[0].data.get("tokens") == 500
        assert middleware.state.steps[1].data.get("tokens") == 1200

    def test_state_dict_includes_tokens(self):
        """Test that tokens are serialized in state dict."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_draft")
        middleware.on_llm_end("llm_draft", tokens=3500)

        state_dict = middleware.get_state_dict()

        assert state_dict["steps"][0]["data"]["tokens"] == 3500


class TestDashboardMiddlewareUpdateStepTokens:
    """Tests for update_step_tokens method (post-streaming token update)."""

    def test_update_step_tokens_adds_tokens(self):
        """Test that update_step_tokens adds tokens to existing step."""
        middleware = DashboardMiddleware()

        # Create and complete a step without tokens
        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=None)

        # Verify no tokens initially
        step = middleware.state.steps[0]
        assert "tokens" not in step.data

        # Update with tokens
        middleware.update_step_tokens("llm_response", 1500)

        assert step.data.get("tokens") == 1500

    def test_update_step_tokens_updates_most_recent(self):
        """Test that update_step_tokens updates the most recent matching step."""
        middleware = DashboardMiddleware()

        # Create multiple llm_response steps
        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=None)
        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=None)

        # Update should affect the most recent (second) step
        middleware.update_step_tokens("llm_response", 2000)

        assert middleware.state.steps[0].data.get("tokens") is None
        assert middleware.state.steps[1].data.get("tokens") == 2000

    def test_update_step_tokens_with_none_does_nothing(self):
        """Test that update_step_tokens with None does not modify step."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_reasoning")
        middleware.on_llm_end("llm_reasoning", tokens=None)

        middleware.update_step_tokens("llm_reasoning", None)

        step = middleware.state.steps[0]
        assert "tokens" not in step.data

    def test_update_step_tokens_different_roles(self):
        """Test updating tokens for different LLM roles."""
        middleware = DashboardMiddleware()

        # Create multiple steps with different roles
        middleware.on_llm_start("llm_reasoning")
        middleware.on_llm_end("llm_reasoning", tokens=None)
        middleware.on_llm_start("llm_observation")
        middleware.on_llm_end("llm_observation", tokens=None)
        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=None)

        # Update each role
        middleware.update_step_tokens("llm_reasoning", 500)
        middleware.update_step_tokens("llm_observation", 800)
        middleware.update_step_tokens("llm_response", 1200)

        reasoning = [s for s in middleware.state.steps if s.node == "llm_reasoning"][0]
        observation = [s for s in middleware.state.steps if s.node == "llm_observation"][0]
        response = [s for s in middleware.state.steps if s.node == "llm_response"][0]

        assert reasoning.data.get("tokens") == 500
        assert observation.data.get("tokens") == 800
        assert response.data.get("tokens") == 1200

    def test_update_step_tokens_nonexistent_role(self):
        """Test that updating tokens for nonexistent role does nothing."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=None)

        # Should not raise an error
        middleware.update_step_tokens("llm_nonexistent", 1000)

        # Original step should be unchanged
        assert "tokens" not in middleware.state.steps[0].data

    def test_update_step_tokens_state_dict_serialization(self):
        """Test that updated tokens appear in state dict."""
        middleware = DashboardMiddleware()

        middleware.on_llm_start("llm_response")
        middleware.on_llm_end("llm_response", tokens=None)
        middleware.update_step_tokens("llm_response", 2500)

        state_dict = middleware.get_state_dict()
        assert state_dict["steps"][0]["data"]["tokens"] == 2500


class TestDashboardMiddlewareRealtimeTokens:
    """Tests for update_realtime_tokens method."""

    def test_token_update_event_type_exists(self):
        """Test that TOKEN_UPDATE event type is defined."""
        assert EventType.TOKEN_UPDATE.value == "token_update"

    def test_update_realtime_tokens_with_state_store(self):
        """Test update_realtime_tokens publishes event to state_store."""
        mock_state_store = Mock()
        mock_state_store.update = Mock()
        middleware = DashboardMiddleware(state_store=mock_state_store)

        middleware.update_realtime_tokens(100, {"channel_id": "test-channel"})

        mock_state_store.update.assert_called_once()
        event = mock_state_store.update.call_args[0][0]
        assert event["event"] == "token_update"
        assert event["tokens"] == 100
        assert event["data"]["channel_id"] == "test-channel"
        assert "timestamp" in event

    def test_update_realtime_tokens_without_state_store(self):
        """Test update_realtime_tokens does nothing without state_store."""
        middleware = DashboardMiddleware()

        # Should not raise an error
        middleware.update_realtime_tokens(100, {"channel_id": "test-channel"})

    def test_update_realtime_tokens_empty_data(self):
        """Test update_realtime_tokens with no data."""
        mock_state_store = Mock()
        mock_state_store.update = Mock()
        middleware = DashboardMiddleware(state_store=mock_state_store)

        middleware.update_realtime_tokens(200)

        event = mock_state_store.update.call_args[0][0]
        assert event["tokens"] == 200
        assert event["data"] == {}

    def test_update_realtime_tokens_zero_tokens(self):
        """Test update_realtime_tokens with zero tokens."""
        mock_state_store = Mock()
        mock_state_store.update = Mock()
        middleware = DashboardMiddleware(state_store=mock_state_store)

        middleware.update_realtime_tokens(0, {"channel_id": "test"})

        event = mock_state_store.update.call_args[0][0]
        assert event["tokens"] == 0

    def test_update_realtime_tokens_multiple_calls(self):
        """Test multiple update_realtime_tokens calls accumulate correctly."""
        mock_state_store = Mock()
        mock_state_store.update = Mock()
        middleware = DashboardMiddleware(state_store=mock_state_store)

        middleware.update_realtime_tokens(50)
        middleware.update_realtime_tokens(150)
        middleware.update_realtime_tokens(300)

        assert mock_state_store.update.call_count == 3

        # Last call should have 300 tokens
        last_event = mock_state_store.update.call_args_list[2][0][0]
        assert last_event["tokens"] == 300
