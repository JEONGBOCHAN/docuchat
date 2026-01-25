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
    channel_id: str | None = None
    current_node: str | None = None
    current_query: str | None = None
    steps: list[StepRecord] = field(default_factory=list)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "channel_id": self.channel_id,
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
        }


class AgentStateStore:
    """Thread-safe state store for per-channel agent execution.

    This class provides a centralized location for storing and updating
    agent execution state per channel. It can be used as a state_updater
    callback for DashboardMiddleware.

    Attributes:
        _states: Dictionary mapping channel_id to AgentState.
        _subscribers: List of callback functions to notify on state changes.

    Example:
        >>> store = AgentStateStore()
        >>> middleware = DashboardMiddleware(state_updater=store.update)
        >>> # State is automatically updated during agent execution
        >>> print(store.get_state("channel-123"))
    """

    def __init__(self) -> None:
        """Initialize the state store."""
        self._states: dict[str, AgentState] = {}
        self._lock = Lock()
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []

    def _get_or_create_state(self, channel_id: str) -> AgentState:
        """Get or create state for a channel (must be called with lock held)."""
        if channel_id not in self._states:
            self._states[channel_id] = AgentState(channel_id=channel_id)
        return self._states[channel_id]

    def get_state(self, channel_id: str | None = None) -> dict[str, Any]:
        """Get the state for a specific channel as a dictionary.

        Args:
            channel_id: The channel ID to get state for. If None, returns idle state.

        Returns:
            State dictionary for the channel.
        """
        with self._lock:
            if channel_id is None:
                # Return idle state if no channel specified
                return AgentState().to_dict()
            if channel_id not in self._states:
                # Return idle state for unknown channel
                return AgentState(channel_id=channel_id).to_dict()
            return self._states[channel_id].to_dict()

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Get all channel states (for debugging)."""
        with self._lock:
            return {cid: state.to_dict() for cid, state in self._states.items()}

    def reset(self, channel_id: str | None = None) -> None:
        """Reset the state for a specific channel or all channels.

        Args:
            channel_id: The channel to reset. If None, resets all channels.
        """
        with self._lock:
            if channel_id is None:
                self._states.clear()
            elif channel_id in self._states:
                self._states[channel_id] = AgentState(channel_id=channel_id)

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

    def _notify_subscribers(self, channel_id: str) -> None:
        """Notify all subscribers of state change for a channel."""
        if channel_id not in self._states:
            return
        state_dict = self._states[channel_id].to_dict()
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
                   Must include 'channel_id' in event or event['data'].
        """
        # Extract channel_id from event
        channel_id = event.get("channel_id") or event.get("data", {}).get("channel_id")
        if not channel_id:
            # Fallback: use a default channel if none specified
            channel_id = "_default"

        with self._lock:
            state = self._get_or_create_state(channel_id)
            event_type = event.get("event", "")

            # Handle agent lifecycle events
            if event_type == "agent_start":
                # Reset state for new agent run
                self._states[channel_id] = AgentState(channel_id=channel_id)
                state = self._states[channel_id]
                state.status = AgentStatus.RUNNING
                state.metrics.start_time = event.get("timestamp")
                query = event.get("data", {}).get("query")
                if query:
                    state.current_query = query

            elif event_type == "agent_complete":
                state.status = AgentStatus.COMPLETE
                state.metrics.end_time = event.get("timestamp")
                state.current_node = None
                # Calculate total duration
                if state.metrics.start_time and state.metrics.end_time:
                    start = datetime.fromisoformat(state.metrics.start_time)
                    end = datetime.fromisoformat(state.metrics.end_time)
                    state.metrics.total_duration_ms = (
                        end - start
                    ).total_seconds() * 1000

            elif event_type == "agent_error":
                state.status = AgentStatus.ERROR
                state.metrics.end_time = event.get("timestamp")
                state.last_error = event.get("error")
                state.current_node = None

            # Handle model events
            elif event_type == "model_start":
                node = event.get("node", "unknown")
                state.current_node = node
                state.metrics.model_calls += 1
                state.metrics.total_steps += 1
                state.steps.append(
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
                for step in reversed(state.steps):
                    if step.node == node and step.status == NodeStatus.RUNNING.value:
                        step.status = NodeStatus.COMPLETE.value
                        step.duration_ms = duration
                        break

            # Handle tool events
            elif event_type == "tool_start":
                node = event.get("node", "unknown")
                state.current_node = node
                state.metrics.tool_calls += 1
                state.metrics.total_steps += 1
                state.steps.append(
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
                for step in reversed(state.steps):
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
                for step in reversed(state.steps):
                    if step.node == node and step.status == NodeStatus.RUNNING.value:
                        step.status = NodeStatus.ERROR.value
                        step.duration_ms = duration
                        step.data["error"] = error
                        break

        # Notify subscribers outside the lock
        self._notify_subscribers(channel_id)


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


def reset_global_state_store(channel_id: str | None = None) -> None:
    """Reset the global state store.

    Useful for testing or when starting a new agent session.

    Args:
        channel_id: The channel to reset. If None, resets all channels.
    """
    global _global_state_store
    with _global_lock:
        if _global_state_store is not None:
            _global_state_store.reset(channel_id)
