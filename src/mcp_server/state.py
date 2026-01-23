# -*- coding: utf-8 -*-
"""
Global state store for MCP Apps dashboard.

Provides a centralized state store that integrates with DashboardMiddleware
and allows MCP tools to query and update agent execution state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Callable


class AgentStatus(str, Enum):
    """Overall status of the agent."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class NodeStatus(str, Enum):
    """Status of a pipeline node."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


# Pipeline node definitions for visualization
PIPELINE_NODES = [
    {"id": "retrieve", "name": "Retrieve", "type": "tool"},
    {"id": "rerank", "name": "Rerank", "type": "tool"},
    {"id": "cite_map", "name": "Cite Map", "type": "tool"},
    {"id": "draft", "name": "Draft", "type": "model"},
    {"id": "reflect", "name": "Reflect", "type": "model"},
    {"id": "revise", "name": "Revise", "type": "model"},
    {"id": "verify", "name": "Verify", "type": "tool"},
]


@dataclass
class StepRecord:
    """Record of a single execution step."""

    node: str
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float | None = None
    data: dict[str, Any] = field(default_factory=dict)


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
class AgentState:
    """Complete agent execution state.

    This is the main state structure that gets serialized and sent to the
    MCP Apps dashboard for real-time visualization.
    """

    status: AgentStatus = AgentStatus.IDLE
    current_node: str | None = None
    current_query: str | None = None
    steps: list[StepRecord] = field(default_factory=list)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)
    last_error: str | None = None
    pipeline_nodes: list[dict] = field(default_factory=lambda: PIPELINE_NODES.copy())

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        # Calculate node statuses based on steps
        node_statuses = {}
        for step in self.steps:
            node_statuses[step.node.lower()] = step.status

        return {
            "status": self.status.value,
            "current_node": self.current_node,
            "current_query": self.current_query,
            "steps": [
                {
                    "node": step.node,
                    "status": step.status,
                    "timestamp": step.timestamp,
                    "duration_ms": step.duration_ms,
                    "data": step.data,
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
            "last_error": self.last_error,
            "pipeline_nodes": [
                {
                    **node,
                    "status": node_statuses.get(node["id"], "pending"),
                }
                for node in self.pipeline_nodes
            ],
        }


class AgentStateStore:
    """Thread-safe global state store for agent execution.

    This class provides a centralized location for storing and updating
    agent execution state. It can be used as a state_updater callback
    for DashboardMiddleware.

    Attributes:
        state: The current agent state.
        subscribers: List of callback functions to notify on state changes.

    Example:
        >>> store = AgentStateStore()
        >>> middleware = DashboardMiddleware(state_updater=store.update)
        >>> # State is automatically updated during agent execution
        >>> print(store.get_state())
    """

    def __init__(self) -> None:
        """Initialize the state store."""
        self._state = AgentState()
        self._lock = Lock()
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []

    @property
    def state(self) -> AgentState:
        """Get the current state."""
        with self._lock:
            return self._state

    def get_state(self) -> dict[str, Any]:
        """Get the current state as a dictionary."""
        with self._lock:
            return self._state.to_dict()

    def reset(self) -> None:
        """Reset the state to initial values."""
        with self._lock:
            self._state = AgentState()

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Subscribe to state changes.

        Args:
            callback: Function to call when state changes.
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Unsubscribe from state changes.

        Args:
            callback: Function to remove from subscribers.
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify_subscribers(self) -> None:
        """Notify all subscribers of state change."""
        state_dict = self._state.to_dict()
        for callback in self._subscribers:
            try:
                callback(state_dict)
            except Exception:
                # Don't let subscriber errors break the state update
                pass

    def update(self, event: dict[str, Any]) -> None:
        """Update state based on an event from DashboardMiddleware.

        This method is designed to be used as the state_updater callback
        for DashboardMiddleware.

        Args:
            event: Event dictionary from DashboardMiddleware.
        """
        with self._lock:
            event_type = event.get("event", "")

            # Handle agent lifecycle events
            if event_type == "agent_start":
                self._state.status = AgentStatus.RUNNING
                self._state.metrics.start_time = event.get("timestamp")
                query = event.get("data", {}).get("query")
                if query:
                    self._state.current_query = query

            elif event_type == "agent_complete":
                self._state.status = AgentStatus.COMPLETE
                self._state.metrics.end_time = event.get("timestamp")
                self._state.current_node = None
                # Calculate total duration
                if self._state.metrics.start_time and self._state.metrics.end_time:
                    start = datetime.fromisoformat(self._state.metrics.start_time)
                    end = datetime.fromisoformat(self._state.metrics.end_time)
                    self._state.metrics.total_duration_ms = (
                        end - start
                    ).total_seconds() * 1000

            elif event_type == "agent_error":
                self._state.status = AgentStatus.ERROR
                self._state.metrics.end_time = event.get("timestamp")
                self._state.last_error = event.get("error")
                self._state.current_node = None

            # Handle model events
            elif event_type == "model_start":
                node = event.get("node", "unknown")
                self._state.current_node = node
                self._state.metrics.model_calls += 1
                self._state.metrics.total_steps += 1
                self._state.steps.append(
                    StepRecord(
                        node=node,
                        status=NodeStatus.RUNNING.value,
                        timestamp=event.get("timestamp", datetime.now().isoformat()),
                        data=event.get("data", {}),
                    )
                )

            elif event_type == "model_complete":
                node = event.get("node", "unknown")
                duration = event.get("data", {}).get("duration_ms")
                # Update the last step for this node
                for step in reversed(self._state.steps):
                    if step.node == node and step.status == NodeStatus.RUNNING.value:
                        step.status = NodeStatus.COMPLETE.value
                        step.duration_ms = duration
                        break

            # Handle tool events
            elif event_type == "tool_start":
                node = event.get("node", "unknown")
                self._state.current_node = node
                self._state.metrics.tool_calls += 1
                self._state.metrics.total_steps += 1
                self._state.steps.append(
                    StepRecord(
                        node=node,
                        status=NodeStatus.RUNNING.value,
                        timestamp=event.get("timestamp", datetime.now().isoformat()),
                        data=event.get("data", {}),
                    )
                )

            elif event_type == "tool_complete":
                node = event.get("node", "unknown")
                duration = event.get("data", {}).get("duration_ms")
                # Update the last step for this node
                for step in reversed(self._state.steps):
                    if step.node == node and step.status == NodeStatus.RUNNING.value:
                        step.status = NodeStatus.COMPLETE.value
                        step.duration_ms = duration
                        if event.get("data", {}).get("result_preview"):
                            step.data["result_preview"] = event["data"]["result_preview"]
                        break

            elif event_type == "tool_error":
                node = event.get("node", "unknown")
                error = event.get("error")
                duration = event.get("data", {}).get("duration_ms")
                # Update the last step for this node
                for step in reversed(self._state.steps):
                    if step.node == node and step.status == NodeStatus.RUNNING.value:
                        step.status = NodeStatus.ERROR.value
                        step.duration_ms = duration
                        step.data["error"] = error
                        break

        # Notify subscribers outside the lock
        self._notify_subscribers()


# Global state store instance
_global_state_store: AgentStateStore | None = None
_global_lock = Lock()


def get_global_state_store() -> AgentStateStore:
    """Get or create the global state store singleton.

    Returns:
        The global AgentStateStore instance.
    """
    global _global_state_store
    with _global_lock:
        if _global_state_store is None:
            _global_state_store = AgentStateStore()
        return _global_state_store


def reset_global_state_store() -> None:
    """Reset the global state store.

    Useful for testing or when starting a new agent session.
    """
    global _global_state_store
    with _global_lock:
        if _global_state_store is not None:
            _global_state_store.reset()
