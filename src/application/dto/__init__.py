# -*- coding: utf-8 -*-
"""Data Transfer Objects for the application layer."""

from src.application.dto.agent_event import (
    AgentEvent,
    EventType,
    AgentStartedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    ToolStartedEvent,
    ToolCompletedEvent,
)

from src.application.dto.enums import (
    AudioStatus,
    VoiceType,
    TrashItemType,
)

__all__ = [
    "AgentEvent",
    "EventType",
    "AgentStartedEvent",
    "AgentCompletedEvent",
    "AgentErrorEvent",
    "ToolStartedEvent",
    "ToolCompletedEvent",
    "AudioStatus",
    "VoiceType",
    "TrashItemType",
]
