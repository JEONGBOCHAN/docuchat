# -*- coding: utf-8 -*-
"""Tests for Audio Overview API."""

import json
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.api.v1.audio import get_channel_port
from src.application.ports.channel import ChannelDTO
from src.models.audio import AudioStatus, VoiceType
from src.infrastructure.persistence.db_models import ChannelMetadata, AudioOverviewDB


class TestGenerateAudioOverview:
    """Tests for POST /api/v1/channels/{channel_id}/audio."""

    def test_generate_audio_overview_success(self, client_with_db: TestClient, test_db):
        """Test successful audio overview generation start."""
        import threading

        # Create channel in database
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        with patch.object(threading, "Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/audio",
                json={
                    "duration_minutes": 5,
                    "style": "conversational",
                    "language": "ko",
                },
            )

            assert response.status_code == 202
            data = response.json()
            assert data["channel_id"] == "fileSearchStores/test-store"
            assert data["status"] == "pending"
            assert "id" in data
            assert data["title"] is None
            assert data["audio_url"] is None
            mock_thread_instance.start.assert_called_once()

        app.dependency_overrides.pop(get_channel_port, None)

    def test_generate_audio_overview_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test audio generation for non-existent channel."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/audio",
            json={},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_channel_port, None)

    def test_generate_audio_overview_channel_metadata_not_found(self, client_with_db: TestClient, test_db):
        """Test audio generation when channel exists in Gemini but not in database."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/audio",
            json={},
        )

        assert response.status_code == 404
        assert "metadata" in response.json()["detail"].lower()

        app.dependency_overrides.pop(get_channel_port, None)


class TestListAudioOverviews:
    """Tests for GET /api/v1/channels/{channel_id}/audio."""

    def test_list_audio_overviews_empty(self, client_with_db: TestClient, test_db):
        """Test listing audio overviews when none exist."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_audio_overviews_with_items(self, client_with_db: TestClient, test_db):
        """Test listing audio overviews with existing items."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        audio1 = AudioOverviewDB(
            audio_id="audio-1",
            channel_id=channel.id,
            status="completed",
            title="Test Podcast 1",
            duration_seconds=300,
        )
        audio2 = AudioOverviewDB(
            audio_id="audio-2",
            channel_id=channel.id,
            status="pending",
        )
        test_db.add_all([audio1, audio2])
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_audio_overviews_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test listing audio overviews for non-existent channel."""
        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/not-exists/audio",
        )

        assert response.status_code == 404


class TestGetAudioOverview:
    """Tests for GET /api/v1/channels/{channel_id}/audio/{audio_id}."""

    def test_get_audio_overview_success(self, client_with_db: TestClient, test_db):
        """Test getting a specific audio overview."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        audio = AudioOverviewDB(
            audio_id="audio-123",
            channel_id=channel.id,
            status="completed",
            title="Test Podcast",
            duration_seconds=300,
            audio_path="/data/audio/audio-123.mp3",
        )
        test_db.add(audio)
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/audio-123",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "audio-123"
        assert data["status"] == "completed"
        assert data["title"] == "Test Podcast"
        assert data["duration_seconds"] == 300
        assert "stream" in data["audio_url"]

    def test_get_audio_overview_not_found(self, client_with_db: TestClient, test_db):
        """Test getting non-existent audio overview."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/not-exists",
        )

        assert response.status_code == 404

    def test_get_audio_overview_wrong_channel(self, client_with_db: TestClient, test_db):
        """Test getting audio overview from wrong channel."""
        channel1 = ChannelMetadata(
            gemini_store_id="fileSearchStores/channel-1",
            name="Channel 1",
        )
        channel2 = ChannelMetadata(
            gemini_store_id="fileSearchStores/channel-2",
            name="Channel 2",
        )
        test_db.add_all([channel1, channel2])
        test_db.commit()

        audio = AudioOverviewDB(
            audio_id="audio-123",
            channel_id=channel1.id,
            status="completed",
        )
        test_db.add(audio)
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/channel-2/audio/audio-123",
        )

        assert response.status_code == 404


class TestDeleteAudioOverview:
    """Tests for DELETE /api/v1/channels/{channel_id}/audio/{audio_id}."""

    def test_delete_audio_overview_success(self, client_with_db: TestClient, test_db):
        """Test deleting an audio overview."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        audio = AudioOverviewDB(
            audio_id="audio-123",
            channel_id=channel.id,
            status="completed",
        )
        test_db.add(audio)
        test_db.commit()

        with patch("src.api.v1.audio.create_tts_port") as mock_tts:
            mock_tts.return_value.delete_audio.return_value = True

            response = client_with_db.delete(
                "/api/v1/channels/fileSearchStores/test-store/audio/audio-123",
            )

            assert response.status_code == 204

        # Verify deleted
        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/audio-123",
        )
        assert response.status_code == 404

    def test_delete_audio_overview_not_found(self, client_with_db: TestClient, test_db):
        """Test deleting non-existent audio overview."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/audio/not-exists",
        )

        assert response.status_code == 404


class TestPreviewScript:
    """Tests for POST /api/v1/channels/{channel_id}/audio/preview-script."""

    def test_preview_script_success(self, client_with_db: TestClient, test_db):
        """Test successful script preview."""
        from src.application.ports.podcast import PodcastScriptDTO, DialogueLineDTO

        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        mock_use_case = MagicMock()
        mock_use_case.execute.return_value = PodcastScriptDTO(
            title="Test Podcast",
            introduction="Welcome to our podcast!",
            dialogue=[
                DialogueLineDTO(speaker="Host A", text="Today we discuss..."),
                DialogueLineDTO(speaker="Host B", text="Great topic!"),
            ],
            conclusion="Thanks for listening!",
            estimated_duration_seconds=300,
        )

        with patch(
            "src.api.v1.audio.create_generate_podcast_script_use_case",
            return_value=mock_use_case,
        ):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/audio/preview-script",
                json={"duration_minutes": 5},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "fileSearchStores/test-store"
        assert data["script"]["title"] == "Test Podcast"
        assert len(data["script"]["dialogue"]) == 2
        assert "generated_at" in data

        app.dependency_overrides.pop(get_channel_port, None)

    def test_preview_script_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test script preview for non-existent channel."""
        mock_port = MagicMock()
        mock_port.get_channel.return_value = None

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/audio/preview-script",
            json={},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_channel_port, None)

    def test_preview_script_api_error(self, client_with_db: TestClient, test_db):
        """Test script preview handles API errors."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        mock_port = MagicMock()
        mock_port.get_channel.return_value = ChannelDTO(
            name="fileSearchStores/test-store",
            display_name="Test Channel",
        )

        app.dependency_overrides[get_channel_port] = lambda: mock_port

        mock_use_case = MagicMock()
        mock_use_case.execute.side_effect = Exception("API Error")

        with patch(
            "src.api.v1.audio.create_generate_podcast_script_use_case",
            return_value=mock_use_case,
        ):
            response = client_with_db.post(
                "/api/v1/channels/fileSearchStores/test-store/audio/preview-script",
                json={},
            )

        assert response.status_code == 500
        assert "Failed to generate script" in response.json()["detail"]

        app.dependency_overrides.pop(get_channel_port, None)


class TestStreamAudio:
    """Tests for GET /api/v1/channels/{channel_id}/audio/{audio_id}/stream."""

    def test_stream_audio_not_ready(self, client_with_db: TestClient, test_db):
        """Test streaming audio that is not ready."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        audio = AudioOverviewDB(
            audio_id="audio-123",
            channel_id=channel.id,
            status="generating_audio",
        )
        test_db.add(audio)
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/audio-123/stream",
        )

        assert response.status_code == 400
        assert "not ready" in response.json()["detail"].lower()

    def test_stream_audio_not_found(self, client_with_db: TestClient, test_db):
        """Test streaming non-existent audio."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/not-exists/stream",
        )

        assert response.status_code == 404


class TestAudioExecutorShutdown:
    """Tests for shutdown_audio_executor."""

    def test_shutdown_calls_executor_shutdown(self):
        """shutdown_audio_executor should invoke the executor's shutdown method."""
        from src.api.v1 import audio as audio_module

        original = audio_module._audio_executor
        mock_executor = MagicMock()
        audio_module._audio_executor = mock_executor

        try:
            audio_module.shutdown_audio_executor(wait=True)
            mock_executor.shutdown.assert_called_once_with(wait=True)
        finally:
            audio_module._audio_executor = original

    def test_shutdown_exception_does_not_propagate(self):
        """Even if executor.shutdown raises, the function should not propagate."""
        from src.api.v1 import audio as audio_module

        original = audio_module._audio_executor
        mock_executor = MagicMock()
        mock_executor.shutdown.side_effect = RuntimeError("thread error")
        audio_module._audio_executor = mock_executor

        try:
            # Should not raise
            audio_module.shutdown_audio_executor(wait=False)
        finally:
            audio_module._audio_executor = original
