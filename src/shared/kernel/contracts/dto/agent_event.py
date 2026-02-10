# -*- coding: utf-8 -*-
"""
Agent Event DTOs.

These are data transfer objects for agent execution events.
Events are observability/operational concerns, not core business rules,
so they live in the application layer (not domain).
"""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any
import uuid


class EventType(Enum):
    """Types of agent execution events."""

    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"


@dataclass
class AgentEvent:
    """Base class for all agent events.

    Attributes:
        event_type: The type of event
        timestamp: When the event occurred
        session_id: Unique identifier for this agent execution session
        data: Additional event-specific data
    """

    event_type: EventType
    session_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class AgentStartedEvent(AgentEvent):
    """Event emitted when an agent starts processing a query."""

    event_type: EventType = field(default=EventType.AGENT_STARTED, init=False)
    query: str = ""
    channel_id: str = ""

    def __post_init__(self):
        self.data = {
            "query": self.query,
            "channel_id": self.channel_id,
        }


@dataclass
class AgentCompletedEvent(AgentEvent):
    """Event emitted when an agent completes successfully."""

    event_type: EventType = field(default=EventType.AGENT_COMPLETED, init=False)
    response: str = ""
    sources: list[dict] = field(default_factory=list)
    iterations: int = 0

    def __post_init__(self):
        self.data = {
            "response": self.response,
            "sources": self.sources,
            "iterations": self.iterations,
        }


@dataclass
class AgentErrorEvent(AgentEvent):
    """Event emitted when an agent encounters an error."""

    event_type: EventType = field(default=EventType.AGENT_ERROR, init=False)
    error: str = ""
    error_type: str = ""

    def __post_init__(self):
        self.data = {
            "error": self.error,
            "error_type": self.error_type,
        }


@dataclass
class ToolStartedEvent(AgentEvent):
    """Event emitted when a tool starts executing."""

    event_type: EventType = field(default=EventType.TOOL_STARTED, init=False)
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.data = {
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
        }


@dataclass
class ToolCompletedEvent(AgentEvent):
    """Event emitted when a tool completes execution."""

    event_type: EventType = field(default=EventType.TOOL_COMPLETED, init=False)
    tool_name: str = ""
    tool_output: Any = None
    duration_ms: float = 0.0

    def __post_init__(self):
        self.data = {
            "tool_name": self.tool_name,
            "tool_output": self.tool_output,
            "duration_ms": self.duration_ms,
        }


def generate_session_id() -> str:
    """Generate a unique session ID for an agent execution."""
    return str(uuid.uuid4())
