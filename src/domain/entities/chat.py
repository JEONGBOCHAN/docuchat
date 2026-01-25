# -*- coding: utf-8 -*-
"""
Chat Domain Entities.

Pure Python representations of chat-related business concepts with business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.exceptions import InvalidRoleError, MessageContentError


# Valid message roles
VALID_ROLES = frozenset({"user", "assistant", "system"})

# Validation constants
MAX_MESSAGE_LENGTH = 100_000  # 100KB of text


@dataclass
class MessageSource:
    """A source reference in a chat message.

    Attributes:
        source: Source document name or identifier
        content: Excerpt or summary from the source
        page: Optional page number
    """

    source: str
    content: str
    page: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"source": self.source, "content": self.content}
        if self.page is not None:
            result["page"] = self.page
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageSource":
        """Create from dictionary."""
        return cls(
            source=data.get("source", ""),
            content=data.get("content", ""),
            page=data.get("page"),
        )


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

    def __post_init__(self) -> None:
        """Validate message after initialization."""
        self._validate_role(self.role)
        self._validate_content(self.content)

    # =========================================================================
    # Validation Methods
    # =========================================================================

    @staticmethod
    def _validate_role(role: str) -> None:
        """Validate message role.

        Args:
            role: Role to validate

        Raises:
            InvalidRoleError: If role is invalid
        """
        if role not in VALID_ROLES:
            raise InvalidRoleError(
                f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}"
            )

    @staticmethod
    def _validate_content(content: str) -> None:
        """Validate message content.

        Args:
            content: Content to validate

        Raises:
            MessageContentError: If content is invalid
        """
        if len(content) > MAX_MESSAGE_LENGTH:
            raise MessageContentError(
                f"Message content cannot exceed {MAX_MESSAGE_LENGTH} characters"
            )

    # =========================================================================
    # Query Methods
    # =========================================================================

    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"

    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"

    def is_system_message(self) -> bool:
        """Check if this is a system message."""
        return self.role == "system"

    def has_sources(self) -> bool:
        """Check if message has any sources."""
        return len(self.sources) > 0

    def source_count(self) -> int:
        """Get the number of sources."""
        return len(self.sources)

    def word_count(self) -> int:
        """Get approximate word count of content."""
        return len(self.content.split())

    def is_empty(self) -> bool:
        """Check if message content is effectively empty."""
        return not self.content.strip()

    # =========================================================================
    # Factory Methods
    # =========================================================================

    @classmethod
    def user(cls, content: str, **kwargs) -> "ChatMessage":
        """Create a user message.

        Args:
            content: Message content
            **kwargs: Additional message attributes

        Returns:
            New ChatMessage with role='user'
        """
        return cls(role="user", content=content, **kwargs)

    @classmethod
    def assistant(
        cls,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> "ChatMessage":
        """Create an assistant message.

        Args:
            content: Message content
            sources: Optional source references
            **kwargs: Additional message attributes

        Returns:
            New ChatMessage with role='assistant'
        """
        return cls(
            role="assistant",
            content=content,
            sources=sources or [],
            **kwargs,
        )

    @classmethod
    def system(cls, content: str, **kwargs) -> "ChatMessage":
        """Create a system message.

        Args:
            content: Message content
            **kwargs: Additional message attributes

        Returns:
            New ChatMessage with role='system'
        """
        return cls(role="system", content=content, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary.

        Returns:
            Dictionary representation of the message
        """
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sources": self.sources,
            "metadata": self.metadata,
        }

    def to_llm_dict(self) -> dict[str, str]:
        """Convert to dictionary for LLM context.

        Returns:
            Simple dictionary with role and content only
        """
        return {"role": self.role, "content": self.content}


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

    def add_user_message(self, content: str) -> ChatMessage:
        """Add a user message to the conversation.

        Args:
            content: Message content

        Returns:
            The created ChatMessage
        """
        msg = ChatMessage.user(content)
        self.messages.append(msg)
        return msg

    def add_assistant_message(
        self,
        content: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Add an assistant message to the conversation.

        Args:
            content: Message content
            sources: Optional source references

        Returns:
            The created ChatMessage
        """
        msg = ChatMessage.assistant(content, sources=sources)
        self.messages.append(msg)
        return msg

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

    def get_last_message(self) -> ChatMessage | None:
        """Get the last message in the conversation.

        Returns:
            Last message or None if empty
        """
        return self.messages[-1] if self.messages else None

    def get_last_user_message(self) -> ChatMessage | None:
        """Get the last user message in the conversation.

        Returns:
            Last user message or None if none found
        """
        for msg in reversed(self.messages):
            if msg.is_user_message():
                return msg
        return None

    def get_last_assistant_message(self) -> ChatMessage | None:
        """Get the last assistant message in the conversation.

        Returns:
            Last assistant message or None if none found
        """
        for msg in reversed(self.messages):
            if msg.is_assistant_message():
                return msg
        return None

    def message_count(self) -> int:
        """Get the number of messages in the conversation."""
        return len(self.messages)

    def is_empty(self) -> bool:
        """Check if conversation has no messages."""
        return len(self.messages) == 0

    def clear(self) -> None:
        """Clear all messages from the conversation."""
        self.messages = []

    def to_dict_list(self) -> list[dict[str, str]]:
        """Convert to list of dicts for LLM context."""
        return [msg.to_llm_dict() for msg in self.messages]

    def total_word_count(self) -> int:
        """Get total word count across all messages."""
        return sum(msg.word_count() for msg in self.messages)
