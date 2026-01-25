# -*- coding: utf-8 -*-
"""Tests for Note domain entity."""

import pytest
from datetime import datetime

from src.domain.entities.note import Note, NoteSource, MAX_TITLE_LENGTH, MAX_CONTENT_LENGTH
from src.domain.exceptions import NoteTitleError, NoteContentError


class TestNoteSource:
    """Tests for NoteSource dataclass."""

    def test_create_note_source(self):
        """Test creating a NoteSource."""
        source = NoteSource(source="document.pdf", content="Some content", page=5)
        assert source.source == "document.pdf"
        assert source.content == "Some content"
        assert source.page == 5

    def test_note_source_to_dict(self):
        """Test converting NoteSource to dictionary."""
        source = NoteSource(source="doc.pdf", content="Content", page=10)
        result = source.to_dict()
        assert result == {"source": "doc.pdf", "content": "Content", "page": 10}

    def test_note_source_to_dict_without_page(self):
        """Test converting NoteSource without page to dictionary."""
        source = NoteSource(source="doc.pdf", content="Content")
        result = source.to_dict()
        assert result == {"source": "doc.pdf", "content": "Content"}

    def test_note_source_from_dict(self):
        """Test creating NoteSource from dictionary."""
        data = {"source": "doc.pdf", "content": "Content", "page": 5}
        source = NoteSource.from_dict(data)
        assert source.source == "doc.pdf"
        assert source.content == "Content"
        assert source.page == 5

    def test_note_source_from_dict_minimal(self):
        """Test creating NoteSource from minimal dictionary."""
        data = {}
        source = NoteSource.from_dict(data)
        assert source.source == ""
        assert source.content == ""
        assert source.page is None


class TestNoteValidation:
    """Tests for Note validation."""

    def test_valid_note_creation(self):
        """Test creating a valid note."""
        note = Note(
            id=1,
            channel_id=1,
            title="Test Note",
            content="Test content",
        )
        assert note.title == "Test Note"
        assert note.content == "Test content"

    def test_empty_title_raises_error(self):
        """Test that empty title raises NoteTitleError."""
        with pytest.raises(NoteTitleError, match="cannot be empty"):
            Note(id=1, channel_id=1, title="", content="Content")

    def test_whitespace_title_raises_error(self):
        """Test that whitespace-only title raises NoteTitleError."""
        with pytest.raises(NoteTitleError, match="cannot be empty"):
            Note(id=1, channel_id=1, title="   ", content="Content")

    def test_title_too_long_raises_error(self):
        """Test that title exceeding max length raises NoteTitleError."""
        long_title = "x" * (MAX_TITLE_LENGTH + 1)
        with pytest.raises(NoteTitleError, match="cannot exceed"):
            Note(id=1, channel_id=1, title=long_title, content="Content")

    def test_title_at_max_length_is_valid(self):
        """Test that title at max length is valid."""
        max_title = "x" * MAX_TITLE_LENGTH
        note = Note(id=1, channel_id=1, title=max_title, content="Content")
        assert len(note.title) == MAX_TITLE_LENGTH

    def test_content_too_long_raises_error(self):
        """Test that content exceeding max length raises NoteContentError."""
        long_content = "x" * (MAX_CONTENT_LENGTH + 1)
        with pytest.raises(NoteContentError, match="cannot exceed"):
            Note(id=1, channel_id=1, title="Title", content=long_content)

    def test_empty_content_is_valid(self):
        """Test that empty content is valid."""
        note = Note(id=1, channel_id=1, title="Title", content="")
        assert note.content == ""


class TestNoteBusinessMethods:
    """Tests for Note business methods."""

    def test_update_title(self):
        """Test updating note title."""
        note = Note(id=1, channel_id=1, title="Old Title", content="Content")
        note.update_title("New Title")
        assert note.title == "New Title"
        assert note.updated_at is not None

    def test_update_title_invalid_raises_error(self):
        """Test that updating with invalid title raises error."""
        note = Note(id=1, channel_id=1, title="Title", content="Content")
        with pytest.raises(NoteTitleError):
            note.update_title("")

    def test_update_content(self):
        """Test updating note content."""
        note = Note(id=1, channel_id=1, title="Title", content="Old content")
        note.update_content("New content")
        assert note.content == "New content"
        assert note.updated_at is not None

    def test_add_source(self):
        """Test adding a source to note."""
        note = Note(id=1, channel_id=1, title="Title", content="Content")
        source = NoteSource(source="doc.pdf", content="Source content")
        note.add_source(source)
        assert len(note.sources) == 1
        assert note.sources[0].source == "doc.pdf"

    def test_remove_source(self):
        """Test removing a source from note."""
        note = Note(
            id=1,
            channel_id=1,
            title="Title",
            content="Content",
            sources=[NoteSource(source="doc.pdf", content="Content")],
        )
        result = note.remove_source("doc.pdf")
        assert result is True
        assert len(note.sources) == 0

    def test_remove_nonexistent_source(self):
        """Test removing a nonexistent source returns False."""
        note = Note(id=1, channel_id=1, title="Title", content="Content")
        result = note.remove_source("nonexistent.pdf")
        assert result is False

    def test_clear_sources(self):
        """Test clearing all sources."""
        note = Note(
            id=1,
            channel_id=1,
            title="Title",
            content="Content",
            sources=[
                NoteSource(source="doc1.pdf", content="Content1"),
                NoteSource(source="doc2.pdf", content="Content2"),
            ],
        )
        note.clear_sources()
        assert len(note.sources) == 0

    def test_soft_delete(self):
        """Test soft deleting a note."""
        note = Note(id=1, channel_id=1, title="Title", content="Content")
        assert note.is_deleted is False
        assert note.deleted_at is None

        note.soft_delete()
        assert note.is_deleted is True
        assert note.deleted_at is not None

    def test_soft_delete_idempotent(self):
        """Test that soft delete is idempotent."""
        note = Note(id=1, channel_id=1, title="Title", content="Content")
        note.soft_delete()
        first_deleted_at = note.deleted_at

        note.soft_delete()
        assert note.deleted_at == first_deleted_at

    def test_restore(self):
        """Test restoring a soft-deleted note."""
        note = Note(id=1, channel_id=1, title="Title", content="Content")
        note.soft_delete()
        note.restore()

        assert note.is_deleted is False
        assert note.deleted_at is None
        assert note.updated_at is not None


class TestNoteQueryMethods:
    """Tests for Note query methods."""

    def test_has_sources_true(self):
        """Test has_sources returns True when sources exist."""
        note = Note(
            id=1,
            channel_id=1,
            title="Title",
            content="Content",
            sources=[NoteSource(source="doc.pdf", content="Content")],
        )
        assert note.has_sources() is True

    def test_has_sources_false(self):
        """Test has_sources returns False when no sources."""
        note = Note(id=1, channel_id=1, title="Title", content="Content")
        assert note.has_sources() is False

    def test_source_count(self):
        """Test source_count returns correct count."""
        note = Note(
            id=1,
            channel_id=1,
            title="Title",
            content="Content",
            sources=[
                NoteSource(source="doc1.pdf", content="Content1"),
                NoteSource(source="doc2.pdf", content="Content2"),
            ],
        )
        assert note.source_count() == 2

    def test_get_source_names(self):
        """Test get_source_names returns list of source names."""
        note = Note(
            id=1,
            channel_id=1,
            title="Title",
            content="Content",
            sources=[
                NoteSource(source="doc1.pdf", content="Content1"),
                NoteSource(source="doc2.pdf", content="Content2"),
            ],
        )
        assert note.get_source_names() == ["doc1.pdf", "doc2.pdf"]

    def test_word_count(self):
        """Test word_count returns approximate word count."""
        note = Note(
            id=1,
            channel_id=1,
            title="Title",
            content="This is a test content with some words",
        )
        assert note.word_count() == 8

    def test_is_empty_true(self):
        """Test is_empty returns True for empty content."""
        note = Note(id=1, channel_id=1, title="Title", content="")
        assert note.is_empty() is True

    def test_is_empty_whitespace(self):
        """Test is_empty returns True for whitespace content."""
        note = Note(id=1, channel_id=1, title="Title", content="   ")
        assert note.is_empty() is True

    def test_is_empty_false(self):
        """Test is_empty returns False for non-empty content."""
        note = Note(id=1, channel_id=1, title="Title", content="Some content")
        assert note.is_empty() is False


class TestNoteFactoryMethods:
    """Tests for Note factory methods."""

    def test_create_basic(self):
        """Test creating a note with factory method."""
        note = Note.create(
            channel_id=1,
            title="Test Note",
            content="Test content",
        )
        assert note.id is None
        assert note.channel_id == 1
        assert note.title == "Test Note"
        assert note.content == "Test content"
        assert note.sources == []

    def test_create_with_sources(self):
        """Test creating a note with sources."""
        sources = [
            {"source": "doc.pdf", "content": "Source content", "page": 5},
        ]
        note = Note.create(
            channel_id=1,
            title="Test Note",
            content="Test content",
            sources=sources,
        )
        assert len(note.sources) == 1
        assert note.sources[0].source == "doc.pdf"
        assert note.sources[0].page == 5

    def test_create_strips_title(self):
        """Test that create strips whitespace from title."""
        note = Note.create(
            channel_id=1,
            title="  Test Note  ",
            content="Content",
        )
        assert note.title == "Test Note"

    def test_to_dict(self):
        """Test converting note to dictionary."""
        note = Note(
            id=1,
            channel_id=1,
            title="Test Note",
            content="Test content",
            sources=[NoteSource(source="doc.pdf", content="Content", page=5)],
        )
        result = note.to_dict()

        assert result["id"] == 1
        assert result["channel_id"] == 1
        assert result["title"] == "Test Note"
        assert result["content"] == "Test content"
        assert len(result["sources"]) == 1
        assert result["sources"][0]["source"] == "doc.pdf"
        assert result["is_deleted"] is False
