# -*- coding: utf-8 -*-
"""Unit tests for ChatMessage and Conversation domain entities."""

import pytest
from datetime import datetime

from src.domain.entities.chat import (
    ChatMessage,
    Conversation,
    MessageSource,
    VALID_ROLES,
    MAX_MESSAGE_LENGTH,
)
from src.domain.exceptions import InvalidRoleError, MessageContentError


class TestMessageSource:
    """Tests for MessageSource dataclass."""

    def test_create_basic_source(self):
        """Test creating a basic message source."""
        source = MessageSource(source="doc.pdf", content="Some content")

        assert source.source == "doc.pdf"
        assert source.content == "Some content"
        assert source.page is None

    def test_create_source_with_page(self):
        """Test creating a source with page number."""
        source = MessageSource(source="doc.pdf", content="Content", page=42)

        assert source.page == 42

    def test_to_dict_without_page(self):
        """Test to_dict without page."""
        source = MessageSource(source="doc.pdf", content="Content")

        result = source.to_dict()

        assert result == {"source": "doc.pdf", "content": "Content"}
        assert "page" not in result

    def test_to_dict_with_page(self):
        """Test to_dict with page."""
        source = MessageSource(source="doc.pdf", content="Content", page=5)

        result = source.to_dict()

        assert result == {"source": "doc.pdf", "content": "Content", "page": 5}

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {"source": "test.pdf", "content": "Test content", "page": 10}

        source = MessageSource.from_dict(data)

        assert source.source == "test.pdf"
        assert source.content == "Test content"
        assert source.page == 10

    def test_from_dict_without_page(self):
        """Test creating from dictionary without page."""
        data = {"source": "test.pdf", "content": "Content"}

        source = MessageSource.from_dict(data)

        assert source.page is None

    def test_from_dict_empty(self):
        """Test creating from empty dictionary."""
        source = MessageSource.from_dict({})

        assert source.source == ""
        assert source.content == ""
        assert source.page is None


class TestChatMessageValidation:
    """Tests for ChatMessage validation."""

    def test_valid_user_role(self):
        """Test valid user role."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"

    def test_valid_assistant_role(self):
        """Test valid assistant role."""
        msg = ChatMessage(role="assistant", content="Hi there")
        assert msg.role == "assistant"

    def test_valid_system_role(self):
        """Test valid system role."""
        msg = ChatMessage(role="system", content="You are helpful")
        assert msg.role == "system"

    def test_invalid_role_raises_error(self):
        """Test invalid role raises InvalidRoleError."""
        with pytest.raises(InvalidRoleError) as exc_info:
            ChatMessage(role="admin", content="Test")

        assert "Invalid role 'admin'" in str(exc_info.value)
        assert "assistant" in str(exc_info.value)

    def test_content_at_max_length(self):
        """Test content at maximum length is valid."""
        content = "a" * MAX_MESSAGE_LENGTH
        msg = ChatMessage(role="user", content=content)
        assert len(msg.content) == MAX_MESSAGE_LENGTH

    def test_content_exceeds_max_length_raises_error(self):
        """Test content exceeding max length raises MessageContentError."""
        content = "a" * (MAX_MESSAGE_LENGTH + 1)

        with pytest.raises(MessageContentError) as exc_info:
            ChatMessage(role="user", content=content)

        assert "cannot exceed" in str(exc_info.value)

    def test_empty_content_is_valid(self):
        """Test empty content is technically valid."""
        msg = ChatMessage(role="user", content="")
        assert msg.content == ""


class TestChatMessageQueryMethods:
    """Tests for ChatMessage query methods."""

    def test_is_user_message(self):
        """Test is_user_message."""
        user_msg = ChatMessage(role="user", content="Hi")
        assistant_msg = ChatMessage(role="assistant", content="Hello")

        assert user_msg.is_user_message() is True
        assert assistant_msg.is_user_message() is False

    def test_is_assistant_message(self):
        """Test is_assistant_message."""
        user_msg = ChatMessage(role="user", content="Hi")
        assistant_msg = ChatMessage(role="assistant", content="Hello")

        assert assistant_msg.is_assistant_message() is True
        assert user_msg.is_assistant_message() is False

    def test_is_system_message(self):
        """Test is_system_message."""
        system_msg = ChatMessage(role="system", content="Be helpful")
        user_msg = ChatMessage(role="user", content="Hi")

        assert system_msg.is_system_message() is True
        assert user_msg.is_system_message() is False

    def test_has_sources_true(self):
        """Test has_sources returns True when sources exist."""
        msg = ChatMessage(
            role="assistant",
            content="Based on the document...",
            sources=[{"source": "doc.pdf", "content": "excerpt"}],
        )

        assert msg.has_sources() is True

    def test_has_sources_false(self):
        """Test has_sources returns False when no sources."""
        msg = ChatMessage(role="assistant", content="Hello")

        assert msg.has_sources() is False

    def test_source_count(self):
        """Test source_count."""
        msg = ChatMessage(
            role="assistant",
            content="Based on docs...",
            sources=[
                {"source": "doc1.pdf", "content": "a"},
                {"source": "doc2.pdf", "content": "b"},
            ],
        )

        assert msg.source_count() == 2

    def test_word_count(self):
        """Test word_count."""
        msg = ChatMessage(role="user", content="Hello world how are you")

        assert msg.word_count() == 5

    def test_word_count_empty(self):
        """Test word_count with empty content."""
        msg = ChatMessage(role="user", content="")

        assert msg.word_count() == 0

    def test_is_empty_true(self):
        """Test is_empty returns True for whitespace-only content."""
        msg = ChatMessage(role="user", content="   ")

        assert msg.is_empty() is True

    def test_is_empty_false(self):
        """Test is_empty returns False for content with text."""
        msg = ChatMessage(role="user", content="Hello")

        assert msg.is_empty() is False


class TestChatMessageFactoryMethods:
    """Tests for ChatMessage factory methods."""

    def test_user_factory(self):
        """Test ChatMessage.user factory method."""
        msg = ChatMessage.user("Hello there")

        assert msg.role == "user"
        assert msg.content == "Hello there"
        assert msg.sources == []

    def test_user_factory_with_metadata(self):
        """Test ChatMessage.user with metadata."""
        msg = ChatMessage.user("Hi", metadata={"key": "value"})

        assert msg.metadata == {"key": "value"}

    def test_assistant_factory(self):
        """Test ChatMessage.assistant factory method."""
        msg = ChatMessage.assistant("Hello!")

        assert msg.role == "assistant"
        assert msg.content == "Hello!"
        assert msg.sources == []

    def test_assistant_factory_with_sources(self):
        """Test ChatMessage.assistant with sources."""
        sources = [{"source": "doc.pdf", "content": "excerpt"}]
        msg = ChatMessage.assistant("Based on...", sources=sources)

        assert msg.sources == sources

    def test_system_factory(self):
        """Test ChatMessage.system factory method."""
        msg = ChatMessage.system("You are a helpful assistant")

        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant"

    def test_factory_sets_created_at(self):
        """Test factory methods set created_at."""
        before = datetime.now()
        msg = ChatMessage.user("Test")
        after = datetime.now()

        assert before <= msg.created_at <= after


class TestChatMessageSerialization:
    """Tests for ChatMessage serialization."""

    def test_to_dict(self):
        """Test to_dict conversion."""
        msg = ChatMessage(
            role="assistant",
            content="Hello",
            sources=[{"source": "doc.pdf", "content": "text"}],
            metadata={"key": "value"},
        )

        result = msg.to_dict()

        assert result["role"] == "assistant"
        assert result["content"] == "Hello"
        assert result["sources"] == [{"source": "doc.pdf", "content": "text"}]
        assert result["metadata"] == {"key": "value"}
        assert "created_at" in result

    def test_to_llm_dict(self):
        """Test to_llm_dict returns only role and content."""
        msg = ChatMessage(
            role="user",
            content="Question?",
            sources=[{"source": "doc.pdf", "content": "text"}],
            metadata={"key": "value"},
        )

        result = msg.to_llm_dict()

        assert result == {"role": "user", "content": "Question?"}
        assert "sources" not in result
        assert "metadata" not in result


class TestConversation:
    """Tests for Conversation entity."""

    def test_create_conversation(self):
        """Test creating a conversation."""
        conv = Conversation(id="conv-1", channel_id="chan-1")

        assert conv.id == "conv-1"
        assert conv.channel_id == "chan-1"
        assert conv.messages == []
        assert conv.metadata == {}

    def test_add_message(self):
        """Test adding a message."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        msg = ChatMessage.user("Hello")

        conv.add_message(msg)

        assert len(conv.messages) == 1
        assert conv.messages[0] is msg

    def test_add_user_message(self):
        """Test add_user_message convenience method."""
        conv = Conversation(id="conv-1", channel_id="chan-1")

        result = conv.add_user_message("Hello")

        assert len(conv.messages) == 1
        assert result.role == "user"
        assert result.content == "Hello"

    def test_add_assistant_message(self):
        """Test add_assistant_message convenience method."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        sources = [{"source": "doc.pdf", "content": "text"}]

        result = conv.add_assistant_message("Response", sources=sources)

        assert len(conv.messages) == 1
        assert result.role == "assistant"
        assert result.sources == sources

    def test_get_history_all(self):
        """Test get_history returns all messages."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Q1")
        conv.add_assistant_message("A1")
        conv.add_user_message("Q2")

        history = conv.get_history()

        assert len(history) == 3

    def test_get_history_limited(self):
        """Test get_history with limit."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Q1")
        conv.add_assistant_message("A1")
        conv.add_user_message("Q2")

        history = conv.get_history(limit=2)

        assert len(history) == 2
        assert history[0].content == "A1"
        assert history[1].content == "Q2"

    def test_get_last_message(self):
        """Test get_last_message."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("First")
        conv.add_assistant_message("Last")

        result = conv.get_last_message()

        assert result.content == "Last"

    def test_get_last_message_empty(self):
        """Test get_last_message when empty."""
        conv = Conversation(id="conv-1", channel_id="chan-1")

        result = conv.get_last_message()

        assert result is None

    def test_get_last_user_message(self):
        """Test get_last_user_message."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Q1")
        conv.add_assistant_message("A1")
        conv.add_user_message("Q2")
        conv.add_assistant_message("A2")

        result = conv.get_last_user_message()

        assert result.content == "Q2"

    def test_get_last_user_message_none(self):
        """Test get_last_user_message when no user messages."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_assistant_message("Hello")

        result = conv.get_last_user_message()

        assert result is None

    def test_get_last_assistant_message(self):
        """Test get_last_assistant_message."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Q1")
        conv.add_assistant_message("A1")
        conv.add_user_message("Q2")

        result = conv.get_last_assistant_message()

        assert result.content == "A1"

    def test_get_last_assistant_message_none(self):
        """Test get_last_assistant_message when no assistant messages."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Hello")

        result = conv.get_last_assistant_message()

        assert result is None

    def test_message_count(self):
        """Test message_count."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Q1")
        conv.add_assistant_message("A1")

        assert conv.message_count() == 2

    def test_is_empty_true(self):
        """Test is_empty returns True for empty conversation."""
        conv = Conversation(id="conv-1", channel_id="chan-1")

        assert conv.is_empty() is True

    def test_is_empty_false(self):
        """Test is_empty returns False for non-empty conversation."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Hello")

        assert conv.is_empty() is False

    def test_clear(self):
        """Test clear removes all messages."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Q1")
        conv.add_assistant_message("A1")

        conv.clear()

        assert conv.is_empty() is True
        assert conv.messages == []

    def test_to_dict_list(self):
        """Test to_dict_list for LLM context."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Hello")
        conv.add_assistant_message("Hi there!")

        result = conv.to_dict_list()

        assert result == [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

    def test_total_word_count(self):
        """Test total_word_count across all messages."""
        conv = Conversation(id="conv-1", channel_id="chan-1")
        conv.add_user_message("Hello world")  # 2 words
        conv.add_assistant_message("Hi there friend")  # 3 words

        assert conv.total_word_count() == 5


class TestValidRoles:
    """Tests for VALID_ROLES constant."""

    def test_valid_roles_contains_user(self):
        """Test VALID_ROLES contains user."""
        assert "user" in VALID_ROLES

    def test_valid_roles_contains_assistant(self):
        """Test VALID_ROLES contains assistant."""
        assert "assistant" in VALID_ROLES

    def test_valid_roles_contains_system(self):
        """Test VALID_ROLES contains system."""
        assert "system" in VALID_ROLES

    def test_valid_roles_is_frozen(self):
        """Test VALID_ROLES is immutable."""
        assert isinstance(VALID_ROLES, frozenset)
