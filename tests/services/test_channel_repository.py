# -*- coding: utf-8 -*-
"""Tests for channel and chat history repositories."""

import json
from datetime import datetime, timedelta, UTC

import pytest

from src.services.channel_repository import ChannelRepository, ChatHistoryRepository


class TestChannelRepository:
    """Tests for ChannelRepository."""

    def test_create_channel(self, test_db):
        """Test creating a new channel."""
        repo = ChannelRepository(test_db)
        channel = repo.create(
            gemini_store_id="fileSearchStores/test123",
            name="Test Channel",
        )

        assert channel.id is not None
        assert channel.gemini_store_id == "fileSearchStores/test123"
        assert channel.name == "Test Channel"
        assert channel.file_count == 0
        assert channel.total_size_bytes == 0
        assert channel.created_at is not None
        assert channel.last_accessed_at is not None

    def test_get_by_gemini_id(self, test_db):
        """Test getting channel by Gemini store ID."""
        repo = ChannelRepository(test_db)
        repo.create(gemini_store_id="fileSearchStores/abc123", name="Channel A")

        # Found
        channel = repo.get_by_gemini_id("fileSearchStores/abc123")
        assert channel is not None
        assert channel.name == "Channel A"

        # Not found
        not_found = repo.get_by_gemini_id("fileSearchStores/notexist")
        assert not_found is None

    def test_get_all(self, test_db):
        """Test getting all channels."""
        repo = ChannelRepository(test_db)
        repo.create(gemini_store_id="store/1", name="Channel 1")
        repo.create(gemini_store_id="store/2", name="Channel 2")
        repo.create(gemini_store_id="store/3", name="Channel 3")

        channels = repo.get_all()
        assert len(channels) == 3
        names = {c.name for c in channels}
        assert names == {"Channel 1", "Channel 2", "Channel 3"}

    def test_touch(self, test_db):
        """Test updating last accessed time."""
        repo = ChannelRepository(test_db)
        channel = repo.create(gemini_store_id="store/touch", name="Touch Test")
        original_accessed = channel.last_accessed_at

        # Wait a bit and touch
        import time
        time.sleep(0.01)
        updated = repo.touch("store/touch")

        assert updated is not None
        assert updated.last_accessed_at >= original_accessed

    def test_touch_nonexistent(self, test_db):
        """Test touching nonexistent channel returns None."""
        repo = ChannelRepository(test_db)
        result = repo.touch("store/nonexistent")
        assert result is None

    def test_update_stats(self, test_db):
        """Test updating channel statistics."""
        repo = ChannelRepository(test_db)
        repo.create(gemini_store_id="store/stats", name="Stats Test")

        # Update file count only
        updated = repo.update_stats("store/stats", file_count=5)
        assert updated.file_count == 5
        assert updated.total_size_bytes == 0

        # Update size only
        updated = repo.update_stats("store/stats", total_size_bytes=1024)
        assert updated.file_count == 5
        assert updated.total_size_bytes == 1024

        # Update both
        updated = repo.update_stats("store/stats", file_count=10, total_size_bytes=2048)
        assert updated.file_count == 10
        assert updated.total_size_bytes == 2048

    def test_delete(self, test_db):
        """Test deleting a channel."""
        repo = ChannelRepository(test_db)
        repo.create(gemini_store_id="store/delete", name="Delete Test")

        # Delete existing
        result = repo.delete("store/delete")
        assert result is True

        # Verify deleted
        channel = repo.get_by_gemini_id("store/delete")
        assert channel is None

        # Delete nonexistent
        result = repo.delete("store/nonexistent")
        assert result is False

    def test_get_inactive_channels(self, test_db):
        """Test getting inactive channels."""
        repo = ChannelRepository(test_db)

        # Create channels
        channel1 = repo.create(gemini_store_id="store/active", name="Active")
        channel2 = repo.create(gemini_store_id="store/inactive", name="Inactive")

        # Manually set last_accessed_at for inactive channel
        channel2.last_accessed_at = datetime.now(UTC) - timedelta(days=100)
        test_db.commit()

        # Get channels inactive for 90 days
        inactive = repo.get_inactive_channels(inactive_days=90)
        assert len(inactive) == 1
        assert inactive[0].gemini_store_id == "store/inactive"


class TestChatHistoryRepository:
    """Tests for ChatHistoryRepository."""

    def test_add_message(self, test_db):
        """Test adding a chat message."""
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(gemini_store_id="store/chat", name="Chat Test")

        chat_repo = ChatHistoryRepository(test_db)

        # Add user message
        user_msg = chat_repo.add_message(
            channel=channel,
            role="user",
            content="What is the capital of France?",
        )
        assert user_msg.id is not None
        assert user_msg.role == "user"
        assert user_msg.content == "What is the capital of France?"
        assert user_msg.sources_json == "[]"

        # Add assistant message with sources
        sources = [{"source": "doc1.pdf", "content": "Paris is the capital"}]
        assistant_msg = chat_repo.add_message(
            channel=channel,
            role="assistant",
            content="Paris is the capital of France.",
            sources=sources,
        )
        assert assistant_msg.role == "assistant"
        assert json.loads(assistant_msg.sources_json) == sources

    def test_get_history(self, test_db):
        """Test getting chat history."""
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(gemini_store_id="store/history", name="History Test")

        chat_repo = ChatHistoryRepository(test_db)

        # Add messages
        chat_repo.add_message(channel, "user", "Question 1")
        chat_repo.add_message(channel, "assistant", "Answer 1")
        chat_repo.add_message(channel, "user", "Question 2")
        chat_repo.add_message(channel, "assistant", "Answer 2")

        # Get history
        messages = chat_repo.get_history(channel)
        assert len(messages) == 4
        assert messages[0].content == "Question 1"
        assert messages[1].content == "Answer 1"
        assert messages[2].content == "Question 2"
        assert messages[3].content == "Answer 2"

    def test_get_history_with_limit(self, test_db):
        """Test getting limited chat history."""
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(gemini_store_id="store/limit", name="Limit Test")

        chat_repo = ChatHistoryRepository(test_db)

        # Add many messages
        for i in range(10):
            chat_repo.add_message(channel, "user", f"Message {i}")

        # Get limited history
        messages = chat_repo.get_history(channel, limit=5)
        assert len(messages) == 5

    def test_clear_history(self, test_db):
        """Test clearing chat history."""
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(gemini_store_id="store/clear", name="Clear Test")

        chat_repo = ChatHistoryRepository(test_db)

        # Add messages
        chat_repo.add_message(channel, "user", "Question 1")
        chat_repo.add_message(channel, "assistant", "Answer 1")

        # Clear history
        count = chat_repo.clear_history(channel)
        assert count == 2

        # Verify cleared
        messages = chat_repo.get_history(channel)
        assert len(messages) == 0

    def test_cascade_delete(self, test_db):
        """Test that deleting a channel also deletes its chat history."""
        channel_repo = ChannelRepository(test_db)
        channel = channel_repo.create(gemini_store_id="store/cascade", name="Cascade Test")

        chat_repo = ChatHistoryRepository(test_db)
        chat_repo.add_message(channel, "user", "Question")
        chat_repo.add_message(channel, "assistant", "Answer")

        # Delete channel
        channel_repo.delete("store/cascade")

        # Verify messages are also deleted (need new query)
        from src.models.db_models import ChatMessageDB
        messages = test_db.query(ChatMessageDB).filter(
            ChatMessageDB.channel_id == channel.id
        ).all()
        assert len(messages) == 0
