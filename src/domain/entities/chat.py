# -*- coding: utf-8 -*-
"""
Chat Domain Entities.

Pure Python representations of chat-related business concepts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ChatMessage:
    """A single message in a conversation.

    Attributes:
        role: Who sent the message (user, assistant, system)
        content: The message text
        created_at: When the message was created
        sources: References to source documents (for RAG responses)
        metadata: Additional message metadata
    """

    role: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    sources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"

    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"


@dataclass
class Conversation:
    """A conversation consisting of multiple messages.

    Attributes:
        id: Unique conversation identifier
        channel_id: The channel this conversation belongs to
        messages: List of messages in chronological order
        created_at: When the conversation started
        metadata: Additional conversation metadata
    """

    id: str
    channel_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)

    def get_history(self, limit: int | None = None) -> list[ChatMessage]:
        """Get conversation history.

        Args:
            limit: Maximum number of recent messages to return

        Returns:
            List of messages (most recent last)
        """
        if limit is None:
            return list(self.messages)
        return list(self.messages[-limit:])

    def to_dict_list(self) -> list[dict[str, str]]:
        """Convert to list of dicts for LLM context."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
