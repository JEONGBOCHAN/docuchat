# -*- coding: utf-8 -*-
"""Tests for ChatSessionMemoryRepository and adapter."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.modules.workspace.infrastructure.persistence.models import ChannelMetadata
from src.modules.conversation.infrastructure.persistence.models import (
    ChatSessionDB,
    ChatSessionMemoryDB,
)
from src.modules.conversation.infrastructure.persistence.repositories import (
    ChatSessionMemoryRepositoryAdapter,
)

# Alias for backward-compatible test naming
ChatSessionMemoryRepository = ChatSessionMemoryRepositoryAdapter


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def channel(test_db):
    """Create a test channel."""
    ch = ChannelMetadata(gemini_store_id="test-store-001", name="Test Channel")
    test_db.add(ch)
    test_db.commit()
    test_db.refresh(ch)
    return ch


@pytest.fixture
def session(test_db, channel):
    """Create a test session."""
    sess = ChatSessionDB(
        session_id="sess_test123",
        channel_id=channel.id,
        context_window=100,
    )
    test_db.add(sess)
    test_db.commit()
    test_db.refresh(sess)
    return sess


class TestChatSessionMemoryRepository:
    """Tests for the raw repository."""

    def test_get_nonexistent_returns_none(self, test_db, session):
        repo = ChatSessionMemoryRepository(test_db)
        result = repo.get_by_session_id("sess_test123")
        assert result is None

    def test_upsert_creates_new_memory(self, test_db, session):
        repo = ChatSessionMemoryRepository(test_db)
        memory = repo.upsert(
            session_id="sess_test123",
            rolling_summary="User asked about Python.",
        )
        assert memory.rolling_summary == "User asked about Python."
        assert memory.total_compactions == 1
        assert memory.version == 1
        assert memory.session_id == session.id

    def test_upsert_updates_existing_memory(self, test_db, session):
        repo = ChatSessionMemoryRepository(test_db)
        repo.upsert(session_id="sess_test123", rolling_summary="First summary.")
        memory = repo.upsert(
            session_id="sess_test123",
            rolling_summary="Updated summary.",
            last_compacted_message_id=42,
        )
        assert memory.rolling_summary == "Updated summary."
        assert memory.total_compactions == 2
        assert memory.version == 2
        assert memory.last_compacted_message_id == 42

    def test_upsert_without_increment(self, test_db, session):
        repo = ChatSessionMemoryRepository(test_db)
        repo.upsert(session_id="sess_test123", rolling_summary="First.")
        memory = repo.upsert(
            session_id="sess_test123",
            rolling_summary="Corrected.",
            increment_compaction=False,
        )
        assert memory.total_compactions == 1  # unchanged

    def test_upsert_invalid_session_raises(self, test_db):
        repo = ChatSessionMemoryRepository(test_db)
        with pytest.raises(ValueError, match="Session not found"):
            repo.upsert(session_id="sess_nonexistent", rolling_summary="test")

    def test_clear_existing_memory(self, test_db, session):
        repo = ChatSessionMemoryRepository(test_db)
        repo.upsert(session_id="sess_test123", rolling_summary="something")
        assert repo.clear("sess_test123") is True
        assert repo.get_by_session_id("sess_test123") is None

    def test_clear_nonexistent_returns_false(self, test_db, session):
        repo = ChatSessionMemoryRepository(test_db)
        assert repo.clear("sess_test123") is False

    def test_get_nonexistent_session_returns_none(self, test_db):
        repo = ChatSessionMemoryRepository(test_db)
        assert repo.get_by_session_id("sess_doesnt_exist") is None

    def test_clear_by_channel_uses_subquery(self, test_db, channel, session):
        """clear_by_channel should delete memories for all sessions in a channel."""
        repo = ChatSessionMemoryRepository(test_db)

        # Create a second session in the same channel
        sess2 = ChatSessionDB(
            session_id="sess_other456",
            channel_id=channel.id,
            context_window=100,
        )
        test_db.add(sess2)
        test_db.commit()
        test_db.refresh(sess2)

        # Create memories for both sessions
        repo.upsert(session_id="sess_test123", rolling_summary="summary 1")
        repo.upsert(session_id="sess_other456", rolling_summary="summary 2")

        # Create a session in a DIFFERENT channel (should not be deleted)
        ch2 = ChannelMetadata(gemini_store_id="other-store", name="Other")
        test_db.add(ch2)
        test_db.commit()
        test_db.refresh(ch2)
        sess3 = ChatSessionDB(
            session_id="sess_different789",
            channel_id=ch2.id,
            context_window=100,
        )
        test_db.add(sess3)
        test_db.commit()
        test_db.refresh(sess3)
        repo.upsert(session_id="sess_different789", rolling_summary="keep this")

        # Delete memories for the original channel
        deleted = repo.clear_by_channel(channel.id)
        assert deleted == 2

        # Verify the other channel's memory is untouched
        assert repo.get_by_session_id("sess_different789") is not None

    def test_clear_by_channel_empty_returns_zero(self, test_db, channel):
        """clear_by_channel should return 0 when no memories exist."""
        repo = ChatSessionMemoryRepository(test_db)
        assert repo.clear_by_channel(channel.id) == 0


class TestChatSessionMemoryAdapter:
    """Tests for the adapter (DTO conversion)."""

    def test_adapter_upsert_returns_dto(self, test_db, session):
        adapter = ChatSessionMemoryRepositoryAdapter(test_db)
        dto = adapter.upsert(
            session_id="sess_test123",
            rolling_summary="Adapter test summary.",
        )
        assert dto.rolling_summary == "Adapter test summary."
        assert dto.total_compactions == 1
        assert dto.version == 1

    def test_adapter_get_returns_dto(self, test_db, session):
        adapter = ChatSessionMemoryRepositoryAdapter(test_db)
        adapter.upsert(session_id="sess_test123", rolling_summary="Get test.")
        dto = adapter.get_by_session_id("sess_test123")
        assert dto is not None
        assert dto.rolling_summary == "Get test."

    def test_adapter_get_nonexistent_returns_none(self, test_db, session):
        adapter = ChatSessionMemoryRepositoryAdapter(test_db)
        assert adapter.get_by_session_id("sess_test123") is None

    def test_adapter_clear(self, test_db, session):
        adapter = ChatSessionMemoryRepositoryAdapter(test_db)
        adapter.upsert(session_id="sess_test123", rolling_summary="to clear")
        assert adapter.clear("sess_test123") is True
        assert adapter.get_by_session_id("sess_test123") is None
