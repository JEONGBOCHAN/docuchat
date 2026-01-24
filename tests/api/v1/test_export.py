# -*- coding: utf-8 -*-
"""Tests for Export API."""

import json
import zipfile
import io
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.api.v1.export import get_channel_port
from src.api.v1.notes import get_channel_port as notes_get_channel_port
from src.application.ports.channel import ChannelDTO
from src.models.db_models import ChannelMetadata, NoteDB, ChatMessageDB


class TestExportNote:
    """Tests for GET /api/v1/export/channels/{channel_id}/notes/{note_id}."""

    def test_export_note_markdown(self, client_with_db: TestClient, test_db):
        """Test exporting a note as Markdown."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[notes_get_channel_port] = lambda: mock_channel_port

        # Create a note first
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={
                "title": "Test Note",
                "content": "This is a test note content.",
                "sources": [{"source": "doc.pdf", "content": "Source content"}],
            },
        )
        assert create_response.status_code == 201
        note_id = create_response.json()["id"]

        # Export as Markdown
        response = client_with_db.get(
            f"/api/v1/export/channels/fileSearchStores/test-store/notes/{note_id}",
            params={"format": "markdown"},
        )

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]

        content = response.content.decode("utf-8")
        assert "# Test Note" in content
        assert "This is a test note content." in content
        assert "doc.pdf" in content

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(notes_get_channel_port, None)

    def test_export_note_json(self, client_with_db: TestClient, test_db):
        """Test exporting a note as JSON."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[notes_get_channel_port] = lambda: mock_channel_port

        # Create a note first
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={
                "title": "JSON Export Test",
                "content": "Content for JSON export.",
                "sources": [],
            },
        )
        assert create_response.status_code == 201
        note_id = create_response.json()["id"]

        # Export as JSON
        response = client_with_db.get(
            f"/api/v1/export/channels/fileSearchStores/test-store/notes/{note_id}",
            params={"format": "json"},
        )

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        data = json.loads(response.content.decode("utf-8"))
        assert data["title"] == "JSON Export Test"
        assert data["content"] == "Content for JSON export."

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(notes_get_channel_port, None)

    def test_export_note_pdf(self, client_with_db: TestClient, test_db):
        """Test exporting a note as PDF."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port
        app.dependency_overrides[notes_get_channel_port] = lambda: mock_channel_port

        # Create a note first
        create_response = client_with_db.post(
            "/api/v1/notes",
            params={"channel_id": "fileSearchStores/test-store"},
            json={
                "title": "PDF Export Test",
                "content": "Content for PDF export.",
                "sources": [],
            },
        )
        assert create_response.status_code == 201
        note_id = create_response.json()["id"]

        # Export as PDF
        response = client_with_db.get(
            f"/api/v1/export/channels/fileSearchStores/test-store/notes/{note_id}",
            params={"format": "pdf"},
        )

        assert response.status_code == 200
        assert "application/pdf" in response.headers["content-type"]
        assert ".pdf" in response.headers["content-disposition"]

        app.dependency_overrides.pop(get_channel_port, None)
        app.dependency_overrides.pop(notes_get_channel_port, None)

    def test_export_note_not_found(self, client_with_db: TestClient, test_db):
        """Test exporting non-existent note."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            "/api/v1/export/channels/fileSearchStores/test-store/notes/99999",
            params={"format": "markdown"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_channel_port, None)


class TestExportChat:
    """Tests for GET /api/v1/export/channels/{channel_id}/chat."""

    def test_export_chat_markdown(self, client_with_db: TestClient, test_db, sample_channel):
        """Test exporting chat history as Markdown."""
        # Add some chat messages
        from src.models.db_models import ChatMessageDB
        msg1 = ChatMessageDB(
            channel_id=sample_channel.id,
            role="user",
            content="Hello, can you help me?",
            sources_json="[]",
        )
        msg2 = ChatMessageDB(
            channel_id=sample_channel.id,
            role="assistant",
            content="Of course! How can I assist you?",
            sources_json='[{"source": "help.pdf", "content": "Help content"}]',
        )
        test_db.add(msg1)
        test_db.add(msg2)
        test_db.commit()

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=sample_channel.gemini_store_id,
            display_name=sample_channel.name,
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            f"/api/v1/export/channels/{sample_channel.gemini_store_id}/chat",
            params={"format": "markdown"},
        )

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]

        content = response.content.decode("utf-8")
        assert "Chat History" in content
        assert "Hello, can you help me?" in content
        assert "Of course! How can I assist you?" in content

        app.dependency_overrides.pop(get_channel_port, None)

    def test_export_chat_json(self, client_with_db: TestClient, test_db, sample_channel):
        """Test exporting chat history as JSON."""
        # Add some chat messages
        from src.models.db_models import ChatMessageDB
        msg = ChatMessageDB(
            channel_id=sample_channel.id,
            role="user",
            content="Test message",
            sources_json="[]",
        )
        test_db.add(msg)
        test_db.commit()

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=sample_channel.gemini_store_id,
            display_name=sample_channel.name,
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            f"/api/v1/export/channels/{sample_channel.gemini_store_id}/chat",
            params={"format": "json"},
        )

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        data = json.loads(response.content.decode("utf-8"))
        assert data["channel_id"] == sample_channel.gemini_store_id
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "Test message"

        app.dependency_overrides.pop(get_channel_port, None)

    def test_export_chat_empty(self, client_with_db: TestClient, test_db):
        """Test exporting empty chat history."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/empty-channel",
            display_name="Empty Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            "/api/v1/export/channels/fileSearchStores/empty-channel/chat",
            params={"format": "json"},
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode("utf-8"))
        assert data["messages"] == []

        app.dependency_overrides.pop(get_channel_port, None)


class TestExportChannel:
    """Tests for GET /api/v1/export/channels/{channel_id}."""

    def test_export_channel_json(self, client_with_db: TestClient, test_db, sample_channel):
        """Test exporting entire channel as JSON."""
        # Add a note
        from src.models.db_models import NoteDB
        note = NoteDB(
            channel_id=sample_channel.id,
            title="Channel Note",
            content="Note content",
            sources_json="[]",
        )
        test_db.add(note)
        test_db.commit()

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=sample_channel.gemini_store_id,
            display_name=sample_channel.name,
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            f"/api/v1/export/channels/{sample_channel.gemini_store_id}",
            params={"format": "json"},
        )

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        data = json.loads(response.content.decode("utf-8"))
        assert data["metadata"]["id"] == sample_channel.gemini_store_id
        assert data["metadata"]["name"] == sample_channel.name
        assert len(data["notes"]) == 1
        assert data["notes"][0]["title"] == "Channel Note"

        app.dependency_overrides.pop(get_channel_port, None)

    def test_export_channel_markdown(self, client_with_db: TestClient, test_db, sample_channel):
        """Test exporting entire channel as Markdown."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=sample_channel.gemini_store_id,
            display_name=sample_channel.name,
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            f"/api/v1/export/channels/{sample_channel.gemini_store_id}",
            params={"format": "markdown"},
        )

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]

        content = response.content.decode("utf-8")
        assert sample_channel.name in content

        app.dependency_overrides.pop(get_channel_port, None)

    def test_export_channel_zip(self, client_with_db: TestClient, test_db, sample_channel):
        """Test exporting entire channel as ZIP (pdf format triggers zip)."""
        # Add a note
        from src.models.db_models import NoteDB
        note = NoteDB(
            channel_id=sample_channel.id,
            title="Zip Test Note",
            content="Content for zip",
            sources_json="[]",
        )
        test_db.add(note)
        test_db.commit()

        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = ChannelDTO(
            name=sample_channel.gemini_store_id,
            display_name=sample_channel.name,
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            f"/api/v1/export/channels/{sample_channel.gemini_store_id}",
            params={"format": "pdf"},  # PDF triggers ZIP for channel export
        )

        assert response.status_code == 200
        assert "application/zip" in response.headers["content-type"]

        # Verify it's a valid ZIP file
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            namelist = zf.namelist()
            assert "metadata.json" in namelist
            assert "notes.json" in namelist
            assert "chat_history.md" in namelist
            assert "chat_history.json" in namelist
            assert "full_export.json" in namelist
            # Check notes folder exists
            assert any("notes/" in name for name in namelist)

        app.dependency_overrides.pop(get_channel_port, None)

    def test_export_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test exporting non-existent channel."""
        mock_channel_port = MagicMock()
        mock_channel_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_channel_port

        response = client_with_db.get(
            "/api/v1/export/channels/fileSearchStores/not-exists",
            params={"format": "json"},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_channel_port, None)


class TestExportService:
    """Unit tests for ExportService."""

    def test_parse_sources_empty(self, test_db):
        """Test parsing empty sources."""
        from src.application.services.export_service import ExportService

        service = ExportService(test_db)
        sources = service._parse_sources("")
        assert sources == []

    def test_parse_sources_valid(self, test_db):
        """Test parsing valid sources JSON."""
        from src.application.services.export_service import ExportService

        service = ExportService(test_db)
        sources_json = '[{"source": "test.pdf", "content": "Test content", "page": 1}]'
        sources = service._parse_sources(sources_json)

        assert len(sources) == 1
        assert sources[0].source == "test.pdf"
        assert sources[0].page == 1

    def test_parse_sources_invalid_json(self, test_db):
        """Test parsing invalid JSON returns empty list."""
        from src.application.services.export_service import ExportService

        service = ExportService(test_db)
        sources = service._parse_sources("invalid json")
        assert sources == []
