# -*- coding: utf-8 -*-
"""
Dashboard middleware for agent execution state publishing.

Implements a middleware that tracks agent execution state and publishes events
for real-time visualization in external dashboards (e.g., MCP Apps).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Protocol


class NodeStatus(str, Enum):
    """Status of a node in the agent execution pipeline."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class AgentStatus(str, Enum):
    """Overall status of the agent."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class EventType(str, Enum):
    """Types of events that can be published."""

    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    NODE_ERROR = "node_error"
    MODEL_START = "model_start"
    MODEL_COMPLETE = "model_complete"
    LLM_START = "llm_start"
    LLM_COMPLETE = "llm_complete"
    TOOL_START = "tool_start"
    TOOL_COMPLETE = "tool_complete"
    TOOL_ERROR = "tool_error"


@dataclass
class StepRecord:
    """Record of a single step in the agent execution."""

    node: str
    status: NodeStatus
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float | None = None


@dataclass
class AgentMetrics:
    """Metrics for agent execution."""

    total_steps: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    start_time: str | None = None
    end_time: str | None = None
    total_duration_ms: float | None = None


@dataclass
class DashboardState:
    """Complete state representation for the dashboard.

    This state structure is designed to be serialized and sent to external
    systems like MCP Apps for real-time visualization.
    """

    status: AgentStatus = AgentStatus.IDLE
    current_node: str | None = None
    steps: list[StepRecord] = field(default_factory=list)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "status": self.status.value,
            "current_node": self.current_node,
            "steps": [
                {
                    "node": step.node,
                    "status": step.status.value,
                    "data": step.data,
                    "timestamp": step.timestamp,
                    "duration_ms": step.duration_ms,
                }
                for step in self.steps
            ],
            "metrics": {
                "total_steps": self.metrics.total_steps,
                "model_calls": self.metrics.model_calls,
                "tool_calls": self.metrics.tool_calls,
                "start_time": self.metrics.start_time,
                "end_time": self.metrics.end_time,
                "total_duration_ms": self.metrics.total_duration_ms,
            },
        }


class StateUpdater(Protocol):
    """Protocol for state update callbacks.

    External systems implement this protocol to receive state updates
    from the middleware.
    """

    def __call__(self, event: dict[str, Any]) -> None:
        """Handle a state update event.

        Args:
            event: Dictionary containing event type and state data.
        """
        ...


class DashboardMiddleware:
    """Middleware that publishes agent execution state for dashboard visualization.

    This middleware tracks the execution of an agent through its various stages
    (model calls, tool calls) and publishes events that can be consumed by
    external dashboard systems for real-time visualization.

    Attributes:
        state_store: Optional state store instance to receive state updates.
        state: Current dashboard state.

    Example:
        >>> from src.mcp_server.state import get_global_state_store
        >>> store = get_global_state_store()
        >>> middleware = DashboardMiddleware(state_store=store)
        >>> # Agent runner will call middleware methods
    """

    def __init__(
        self,
        state_updater: StateUpdater | None = None,
        state_store: Any | None = None,
        name: str = "dashboard_middleware",
    ) -> None:
        """Initialize the dashboard middleware.

        Args:
            state_updater: Optional callback to receive state update events.
            state_store: Optional AgentStateStore instance.
            name: Name identifier for this middleware instance.
        """
        self._name = name
        self._state_updater = state_updater
        self._state_store = state_store
        self._state = DashboardState()
        self._current_model_node: str | None = None
        self._step_start_times: dict[str, datetime] = {}

    @property
    def name(self) -> str:
        """Return the middleware name."""
        return self._name

    @property
    def state(self) -> DashboardState:
        """Return the current dashboard state."""
        return self._state

    def get_state_dict(self) -> dict[str, Any]:
        """Return the current state as a dictionary."""
        return self._state.to_dict()

    def reset(self) -> None:
        """Reset the middleware state for a new agent execution."""
        self._state = DashboardState()
        self._current_model_node = None
        self._step_start_times = {}

    def _publish_event(
        self,
        event_type: EventType,
        node: str | None = None,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Publish a state update event.

        Args:
            event_type: Type of the event.
            node: Name of the node involved (if applicable).
            data: Additional data for the event.
            error: Error message (if applicable).
        """
        event = {
            "event": event_type.value,
            "timestamp": datetime.now().isoformat(),
            "node": node,
            "data": data or {},
            "state": self._state.to_dict(),
        }

        if error:
            event["error"] = error

        # Publish to state_updater callback
        if self._state_updater:
            self._state_updater(event)

        # Publish to state_store
        if self._state_store and hasattr(self._state_store, 'update'):
            self._state_store.update(event)

    # =========================================================================
    # Simple callback methods for direct use by agent runners
    # =========================================================================

    def on_agent_start(self, data: dict[str, Any]) -> None:
        """Called when agent execution starts."""
        self.reset()
        self._state.status = AgentStatus.RUNNING
        self._state.metrics.start_time = datetime.now().isoformat()
        self._publish_event(EventType.AGENT_START, data=data)

    def on_agent_end(self, data: dict[str, Any]) -> None:
        """Called when agent execution completes successfully."""
        self._state.status = AgentStatus.COMPLETE
        self._state.current_node = None
        self._state.metrics.end_time = datetime.now().isoformat()

        if self._state.metrics.start_time:
            start = datetime.fromisoformat(self._state.metrics.start_time)
            end = datetime.fromisoformat(self._state.metrics.end_time)
            self._state.metrics.total_duration_ms = (end - start).total_seconds() * 1000

        self._publish_event(EventType.AGENT_COMPLETE, data=data)

    def on_agent_error(self, error: str) -> None:
        """Called when agent execution fails."""
        self._state.status = AgentStatus.ERROR
        self._state.current_node = None
        self._state.metrics.end_time = datetime.now().isoformat()

        if self._state.metrics.start_time:
            start = datetime.fromisoformat(self._state.metrics.start_time)
            end = datetime.fromisoformat(self._state.metrics.end_time)
            self._state.metrics.total_duration_ms = (end - start).total_seconds() * 1000

        self._publish_event(EventType.AGENT_ERROR, error=error)

    def on_tool_start(self, tool_name: str, data: dict[str, Any]) -> None:
        """Called when a tool execution starts."""
        self._state.current_node = tool_name
        self._step_start_times[tool_name] = datetime.now()
        self._state.metrics.tool_calls += 1

        step = StepRecord(
            node=tool_name,
            status=NodeStatus.RUNNING,
            data={"type": "tool", **data},
        )
        self._state.steps.append(step)
        self._state.metrics.total_steps += 1

        self._publish_event(EventType.TOOL_START, node=tool_name, data=data)

    def on_tool_end(self, tool_name: str, data: dict[str, Any]) -> None:
        """Called when a tool execution completes."""
        duration = self._calculate_duration(tool_name)

        for step in reversed(self._state.steps):
            if step.node == tool_name and step.status == NodeStatus.RUNNING:
                step.status = NodeStatus.COMPLETE
                step.duration_ms = duration
                break

        self._publish_event(
            EventType.TOOL_COMPLETE,
            node=tool_name,
            data={"duration_ms": duration, **data},
        )

    def on_llm_start(self, llm_role: str, data: dict[str, Any] | None = None) -> None:
        """Called when an LLM call starts.

        This method provides real-time feedback when an LLM begins processing.
        Use role-based names like llm_draft, llm_reflect, llm_revise for clarity.

        Args:
            llm_role: Role of the LLM (e.g., llm_draft, llm_reflect, llm_revise).
            data: Additional data about the LLM call (e.g., prompt_length).
        """
        data = data or {}
        self._state.current_node = llm_role
        self._step_start_times[llm_role] = datetime.now()
        self._state.metrics.model_calls += 1

        step = StepRecord(
            node=llm_role,
            status=NodeStatus.RUNNING,
            data={"type": "llm", **data},
        )
        self._state.steps.append(step)
        self._state.metrics.total_steps += 1

        self._publish_event(
            EventType.LLM_START,
            node=llm_role,
            data={"type": "llm", **data},
        )

    def on_llm_end(
        self,
        llm_role: str,
        data: dict[str, Any] | None = None,
        tokens: int | None = None,
    ) -> None:
        """Called when an LLM call completes.

        Updates the step record with duration and token usage, and publishes
        an llm_complete event.

        Args:
            llm_role: Role of the LLM that completed.
            data: Additional data about the completion (e.g., response_length).
            tokens: Total token count for this LLM call (optional).
        """
        data = data or {}
        duration = self._calculate_duration(llm_role)

        for step in reversed(self._state.steps):
            if step.node == llm_role and step.status == NodeStatus.RUNNING:
                step.status = NodeStatus.COMPLETE
                step.duration_ms = duration
                if tokens is not None:
                    step.data["tokens"] = tokens
                break

        event_data = {"type": "llm", "duration_ms": duration, **data}
        if tokens is not None:
            event_data["tokens"] = tokens

        self._publish_event(
            EventType.LLM_COMPLETE,
            node=llm_role,
            data=event_data,
        )

    def _calculate_duration(self, node: str) -> float | None:
        """Calculate duration in milliseconds for a node.

        Args:
            node: Name of the node.

        Returns:
            Duration in milliseconds or None if start time not found.
        """
        start_time = self._step_start_times.pop(node, None)
        if start_time:
            delta = datetime.now() - start_time
            return delta.total_seconds() * 1000
        return None

    def update_step_tokens(self, llm_role: str, tokens: int | None) -> None:
        """Update token count for a completed LLM step.

        This is used to retroactively add token information to steps when
        token data becomes available after streaming completes.

        Args:
            llm_role: Role of the LLM step to update (e.g., llm_response).
            tokens: Total token count for this LLM call (optional).
        """
        if tokens is None:
            return

        # Find the most recent step with this role and update tokens
        for step in reversed(self._state.steps):
            if step.node == llm_role:
                step.data["tokens"] = tokens
                break

    def _detect_model_node(self, state: dict[str, Any]) -> str:
        """Detect which model node is being called based on state.

        Uses heuristics to determine if this is a Draft, Reflect, or Revise
        step based on conversation history and state.

        Args:
            state: Current agent state.

        Returns:
            Name of the detected model node.
        """
        messages = state.get("messages", [])

        # Count how many model calls we've seen
        model_call_count = sum(
            1 for step in self._state.steps
            if step.node in ("Draft", "Reflect", "Revise")
        )

        # Simple heuristic: first call is Draft, second is Reflect, third+ is Revise
        if model_call_count == 0:
            return "Draft"
        elif model_call_count == 1:
            return "Reflect"
        else:
            return "Revise"

    def before_agent(
        self,
        state: dict[str, Any],
        runtime: Any,
    ) -> dict[str, Any] | None:
        """Called before agent execution starts.

        Initializes the dashboard state and publishes an agent_start event.

        Args:
            state: Initial agent state.
            runtime: Agent runtime context.

        Returns:
            None (no state modification).
        """
        self.reset()

        self._state.status = AgentStatus.RUNNING
        self._state.metrics.start_time = datetime.now().isoformat()

        # Extract query from messages if available
        messages = state.get("messages", [])
        query = None
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                query = str(last_message.content)[:100]
            elif isinstance(last_message, dict):
                query = str(last_message.get("content", ""))[:100]

        self._publish_event(
            EventType.AGENT_START,
            data={"query": query} if query else {},
        )

        return None

    def after_agent(
        self,
        state: dict[str, Any],
        runtime: Any,
    ) -> dict[str, Any] | None:
        """Called after agent execution completes.

        Finalizes the dashboard state and publishes an agent_complete event.
        Handles both successful completion and error states.

        Args:
            state: Final agent state.
            runtime: Agent runtime context.

        Returns:
            None (no state modification).
        """
        # Check if there was an error
        error = state.get("error")

        if error:
            self._state.status = AgentStatus.ERROR
            self._state.current_node = None
            self._state.metrics.end_time = datetime.now().isoformat()

            if self._state.metrics.start_time:
                start = datetime.fromisoformat(self._state.metrics.start_time)
                end = datetime.fromisoformat(self._state.metrics.end_time)
                self._state.metrics.total_duration_ms = (end - start).total_seconds() * 1000

            self._publish_event(
                EventType.AGENT_ERROR,
                error=str(error),
            )
        else:
            self._state.status = AgentStatus.COMPLETE
            self._state.current_node = None
            self._state.metrics.end_time = datetime.now().isoformat()

            if self._state.metrics.start_time:
                start = datetime.fromisoformat(self._state.metrics.start_time)
                end = datetime.fromisoformat(self._state.metrics.end_time)
                self._state.metrics.total_duration_ms = (end - start).total_seconds() * 1000

            # Extract response preview from final message
            messages = state.get("messages", [])
            response_preview = None
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, "content"):
                    response_preview = str(last_message.content)[:100]
                elif isinstance(last_message, dict):
                    response_preview = str(last_message.get("content", ""))[:100]

            self._publish_event(
                EventType.AGENT_COMPLETE,
                data={"response_preview": response_preview} if response_preview else {},
            )

        return None

    def before_model(
        self,
        state: dict[str, Any],
        runtime: Any,
    ) -> dict[str, Any] | None:
        """Called before a model (LLM) call.

        Detects the model node type and publishes a model_start event.

        Args:
            state: Current agent state.
            runtime: Agent runtime context.

        Returns:
            None (no state modification).
        """
        node = self._detect_model_node(state)
        self._current_model_node = node

        self._state.current_node = node
        self._step_start_times[node] = datetime.now()
        self._state.metrics.model_calls += 1

        step = StepRecord(
            node=node,
            status=NodeStatus.RUNNING,
            data={"type": "model"},
        )
        self._state.steps.append(step)
        self._state.metrics.total_steps += 1

        self._publish_event(
            EventType.MODEL_START,
            node=node,
            data={"type": "model"},
        )

        return None

    def after_model(
        self,
        state: dict[str, Any],
        runtime: Any,
    ) -> dict[str, Any] | None:
        """Called after a model (LLM) call completes.

        Updates the step record and publishes a model_complete event.

        Args:
            state: Current agent state.
            runtime: Agent runtime context.

        Returns:
            None (no state modification).
        """
        node = self._current_model_node or "unknown"
        duration = self._calculate_duration(node)

        # Update the last step record for this node
        for step in reversed(self._state.steps):
            if step.node == node and step.status == NodeStatus.RUNNING:
                step.status = NodeStatus.COMPLETE
                step.duration_ms = duration
                break

        self._publish_event(
            EventType.MODEL_COMPLETE,
            node=node,
            data={
                "type": "model",
                "duration_ms": duration,
            },
        )

        self._current_model_node = None

        return None

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        """Wrap a tool call to track its execution.

        Publishes tool_start, tool_complete, or tool_error events.

        Args:
            request: The tool call request.
            handler: The handler to execute the tool.

        Returns:
            The tool execution result.
        """
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown") if isinstance(tool_call, dict) else getattr(tool_call, "name", "unknown")
        tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})

        # Record start
        self._state.current_node = tool_name
        self._step_start_times[tool_name] = datetime.now()
        self._state.metrics.tool_calls += 1

        step = StepRecord(
            node=tool_name,
            status=NodeStatus.RUNNING,
            data={
                "type": "tool",
                "input_preview": str(tool_args)[:100],
            },
        )
        self._state.steps.append(step)
        self._state.metrics.total_steps += 1

        self._publish_event(
            EventType.TOOL_START,
            node=tool_name,
            data={
                "type": "tool",
                "input_preview": str(tool_args)[:100],
            },
        )

        try:
            result = handler(request)
            duration = self._calculate_duration(tool_name)

            # Update step record
            for s in reversed(self._state.steps):
                if s.node == tool_name and s.status == NodeStatus.RUNNING:
                    s.status = NodeStatus.COMPLETE
                    s.duration_ms = duration

                    # Extract result preview
                    if hasattr(result, "content"):
                        s.data["result_preview"] = str(result.content)[:100]
                    break

            self._publish_event(
                EventType.TOOL_COMPLETE,
                node=tool_name,
                data={
                    "type": "tool",
                    "duration_ms": duration,
                    "result_preview": str(getattr(result, "content", result))[:100],
                },
            )

            return result

        except Exception as e:
            duration = self._calculate_duration(tool_name)

            # Update step record with error
            for s in reversed(self._state.steps):
                if s.node == tool_name and s.status == NodeStatus.RUNNING:
                    s.status = NodeStatus.ERROR
                    s.duration_ms = duration
                    s.data["error"] = str(e)
                    break

            self._publish_event(
                EventType.TOOL_ERROR,
                node=tool_name,
                data={"type": "tool", "duration_ms": duration},
                error=str(e),
            )

            raise
