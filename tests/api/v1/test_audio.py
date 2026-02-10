# -*- coding: utf-8 -*-
"""Tests for Audio Overview API."""

import json
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.modules.knowledge.presentation.api.audio import _get_use_case
from src.modules.knowledge.presentation.schemas.audio import AudioStatus, VoiceType
from src.modules.workspace.infrastructure.persistence.models import ChannelMetadata, AudioOverviewDB
from src.shared.kernel.contracts.ports.persistence import AudioOverviewDTO


def _build_use_case_with_mocks(test_db):
    """Build AudioOverviewUseCase with real DB repos and mock external ports."""
    from src.modules.knowledge.application.use_cases.audio_overview import AudioOverviewUseCase
    from src.modules.workspace.public import (
        create_channel_port,
        create_channel_repository_port,
    )
    from src.modules.knowledge.public import create_audio_repository_port

    mock_channel_port = MagicMock()
    mock_channel_port.get_channel.return_value = MagicMock(
        name="fileSearchStores/test-store",
        display_name="Test Channel",
    )

    mock_tts = MagicMock()
    mock_task_port = MagicMock()
    mock_script_uc = MagicMock()

    return AudioOverviewUseCase(
        channel_port=mock_channel_port,
        audio_repo=create_audio_repository_port(test_db),
        channel_repo=create_channel_repository_port(test_db),
        tts_port=mock_tts,
        task_port=mock_task_port,
        script_use_case=mock_script_uc,
    ), mock_channel_port, mock_task_port, mock_tts, mock_script_uc


class TestGenerateAudioOverview:
    """Tests for POST /api/v1/channels/{channel_id}/audio."""

    def test_generate_audio_overview_success(self, client_with_db: TestClient, test_db):
        """Test successful audio overview generation start."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        uc, mock_port, mock_task, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

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

        # Verify task_port.enqueue was called
        mock_task.enqueue.assert_called_once()
        req = mock_task.enqueue.call_args[0][0]
        assert req.duration_minutes == 5
        assert req.style == "conversational"
        assert req.language == "ko"

        app.dependency_overrides.pop(_get_use_case, None)

    def test_generate_audio_overview_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test audio generation for non-existent channel."""
        uc, mock_port, _, _, _ = _build_use_case_with_mocks(test_db)
        mock_port.get_channel.return_value = None
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/audio",
            json={},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)

    def test_generate_audio_overview_channel_metadata_not_found(self, client_with_db: TestClient, test_db):
        """Test audio generation when channel exists in Gemini but not in database."""
        uc, mock_port, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/audio",
            json={},
        )

        assert response.status_code == 404
        assert "metadata" in response.json()["detail"].lower()

        app.dependency_overrides.pop(_get_use_case, None)


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

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

        app.dependency_overrides.pop(_get_use_case, None)

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

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        app.dependency_overrides.pop(_get_use_case, None)

    def test_list_audio_overviews_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test listing audio overviews for non-existent channel."""
        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/not-exists/audio",
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)


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

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

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

        app.dependency_overrides.pop(_get_use_case, None)

    def test_get_audio_overview_not_found(self, client_with_db: TestClient, test_db):
        """Test getting non-existent audio overview."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/not-exists",
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)

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

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/channel-2/audio/audio-123",
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)


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

        uc, _, _, mock_tts, _ = _build_use_case_with_mocks(test_db)
        mock_tts.delete_audio.return_value = True
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/audio/audio-123",
        )

        assert response.status_code == 204

        # Verify deleted
        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/audio-123",
        )
        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)

    def test_delete_audio_overview_not_found(self, client_with_db: TestClient, test_db):
        """Test deleting non-existent audio overview."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.delete(
            "/api/v1/channels/fileSearchStores/test-store/audio/not-exists",
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)


class TestPreviewScript:
    """Tests for POST /api/v1/channels/{channel_id}/audio/preview-script."""

    def test_preview_script_success(self, client_with_db: TestClient, test_db):
        """Test successful script preview."""
        from src.shared.kernel.contracts.ports.podcast import PodcastScriptDTO, DialogueLineDTO

        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        uc, mock_port, _, _, mock_script_uc = _build_use_case_with_mocks(test_db)
        mock_script_uc.execute.return_value = PodcastScriptDTO(
            title="Test Podcast",
            introduction="Welcome to our podcast!",
            dialogue=[
                DialogueLineDTO(speaker="Host A", text="Today we discuss..."),
                DialogueLineDTO(speaker="Host B", text="Great topic!"),
            ],
            conclusion="Thanks for listening!",
            estimated_duration_seconds=300,
        )

        app.dependency_overrides[_get_use_case] = lambda: uc

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

        app.dependency_overrides.pop(_get_use_case, None)

    def test_preview_script_channel_not_found(self, client_with_db: TestClient, test_db):
        """Test script preview for non-existent channel."""
        uc, mock_port, _, _, _ = _build_use_case_with_mocks(test_db)
        mock_port.get_channel.return_value = None
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/not-exists/audio/preview-script",
            json={},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)

    def test_preview_script_api_error(self, client_with_db: TestClient, test_db):
        """Test script preview handles API errors."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        uc, mock_port, _, _, mock_script_uc = _build_use_case_with_mocks(test_db)
        mock_script_uc.execute.side_effect = Exception("API Error")

        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.post(
            "/api/v1/channels/fileSearchStores/test-store/audio/preview-script",
            json={},
        )

        assert response.status_code == 500
        assert "Failed to generate script" in response.json()["detail"]

        app.dependency_overrides.pop(_get_use_case, None)


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

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/audio-123/stream",
        )

        assert response.status_code == 400
        assert "not ready" in response.json()["detail"].lower()

        app.dependency_overrides.pop(_get_use_case, None)

    def test_stream_audio_not_found(self, client_with_db: TestClient, test_db):
        """Test streaming non-existent audio."""
        channel = ChannelMetadata(
            gemini_store_id="fileSearchStores/test-store",
            name="Test Channel",
        )
        test_db.add(channel)
        test_db.commit()

        uc, _, _, _, _ = _build_use_case_with_mocks(test_db)
        app.dependency_overrides[_get_use_case] = lambda: uc

        response = client_with_db.get(
            "/api/v1/channels/fileSearchStores/test-store/audio/not-exists/stream",
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(_get_use_case, None)


class TestAudioExecutorShutdown:
    """Tests for shutdown/lazy-recreation of audio executor."""

    def test_shutdown_calls_executor_shutdown(self):
        """shutdown_audio_executor should invoke the executor's shutdown method."""
        from src.modules.knowledge.infrastructure.runtime import audio_executor as rt

        original = rt._audio_executor
        mock_executor = MagicMock()
        rt._audio_executor = mock_executor

        try:
            rt.shutdown_audio_executor(wait=True)
            mock_executor.shutdown.assert_called_once_with(wait=True)
            assert rt._audio_executor is None
        finally:
            rt._audio_executor = original

    def test_shutdown_exception_does_not_propagate(self):
        """Even if executor.shutdown raises, the function should not propagate."""
        from src.modules.knowledge.infrastructure.runtime import audio_executor as rt

        original = rt._audio_executor
        mock_executor = MagicMock()
        mock_executor.shutdown.side_effect = RuntimeError("thread error")
        rt._audio_executor = mock_executor

        try:
            rt.shutdown_audio_executor(wait=False)
            assert rt._audio_executor is None
        finally:
            rt._audio_executor = original

    def test_shutdown_noop_when_none(self):
        """shutdown_audio_executor is safe to call when no executor exists."""
        from src.modules.knowledge.infrastructure.runtime import audio_executor as rt

        original = rt._audio_executor
        rt._audio_executor = None

        try:
            rt.shutdown_audio_executor(wait=False)
        finally:
            rt._audio_executor = original

    def test_get_recreates_after_shutdown(self):
        """_get_audio_executor creates a fresh executor after shutdown."""
        from src.modules.knowledge.infrastructure.runtime import audio_executor as rt

        original = rt._audio_executor

        try:
            exec1 = rt.get_audio_executor()
            assert exec1 is not None

            rt.shutdown_audio_executor(wait=True)
            assert rt._audio_executor is None

            exec2 = rt.get_audio_executor()
            assert exec2 is not None
            assert exec2 is not exec1
        finally:
            if rt._audio_executor is not None and rt._audio_executor is not original:
                rt._audio_executor.shutdown(wait=True)
            rt._audio_executor = original
