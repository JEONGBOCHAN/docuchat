# -*- coding: utf-8 -*-
"""Unit tests for AudioOverviewUseCase."""

from datetime import datetime, UTC
from unittest.mock import MagicMock, patch
import pytest

from src.modules.knowledge.application.use_cases.audio_overview import (
    AudioOverviewUseCase,
    AudioOverviewResult,
    AudioOverviewListResult,
    ScriptPreviewResult,
    StreamInfo,
    ChannelNotFoundError,
    ChannelMetadataNotFoundError,
    AudioNotFoundError,
    AudioNotReadyError,
    AudioFileNotFoundError,
    ScriptGenerationError,
)
from src.shared.kernel.contracts.ports.persistence import AudioOverviewDTO, ChannelMetadataDTO
from src.shared.kernel.contracts.ports.podcast import PodcastScriptDTO, DialogueLineDTO


def _make_use_case():
    """Create AudioOverviewUseCase with all-mock dependencies."""
    channel_port = MagicMock()
    audio_repo = MagicMock()
    channel_repo = MagicMock()
    tts_port = MagicMock()
    task_port = MagicMock()
    script_uc = MagicMock()

    uc = AudioOverviewUseCase(
        channel_port=channel_port,
        audio_repo=audio_repo,
        channel_repo=channel_repo,
        tts_port=tts_port,
        task_port=task_port,
        script_use_case=script_uc,
    )
    return uc, channel_port, audio_repo, channel_repo, tts_port, task_port, script_uc


def _fake_channel_meta(id=1, store_id="fileSearchStores/test-store"):
    return ChannelMetadataDTO(
        id=id,
        gemini_store_id=store_id,
        name="Test Channel",
        description=None,
        created_at=datetime.now(UTC),
        last_accessed_at=datetime.now(UTC),
        file_count=0,
        total_size_bytes=0,
        is_deleted=False,
        deleted_at=None,
    )


def _fake_audio_dto(audio_id="audio-1", channel_id=1, status="pending"):
    return AudioOverviewDTO(
        id=1,
        audio_id=audio_id,
        channel_id=channel_id,
        title=None,
        status=status,
        language="ko",
        style="conversational",
        script_json=None,
        audio_path=None,
        audio_duration_seconds=None,
        error_message=None,
        created_at=datetime.now(UTC),
        completed_at=None,
    )


class TestStartGeneration:
    """Tests for start_generation method."""

    def test_success(self):
        uc, ch_port, audio_repo, ch_repo, _, task_port, _ = _make_use_case()
        ch_port.get_channel.return_value = MagicMock()
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta()
        audio_repo.create_audio_overview.return_value = _fake_audio_dto()

        result = uc.start_generation(
            channel_id="fileSearchStores/test-store",
            duration_minutes=5,
            style="conversational",
            language="ko",
            host_a_voice="male_1",
            host_b_voice="female_1",
        )

        assert isinstance(result, AudioOverviewResult)
        assert result.channel_store_id == "fileSearchStores/test-store"
        task_port.enqueue.assert_called_once()
        ch_repo.touch.assert_called_once_with("fileSearchStores/test-store")

    def test_channel_not_found(self):
        uc, ch_port, _, _, _, _, _ = _make_use_case()
        ch_port.get_channel.return_value = None

        with pytest.raises(ChannelNotFoundError):
            uc.start_generation(
                channel_id="fileSearchStores/missing",
                duration_minutes=5, style="conversational",
                language="ko", host_a_voice="m", host_b_voice="f",
            )

    def test_channel_metadata_not_found(self):
        uc, ch_port, audio_repo, _, _, _, _ = _make_use_case()
        ch_port.get_channel.return_value = MagicMock()
        audio_repo.get_channel_by_store_id.return_value = None

        with pytest.raises(ChannelMetadataNotFoundError):
            uc.start_generation(
                channel_id="fileSearchStores/no-meta",
                duration_minutes=5, style="conversational",
                language="ko", host_a_voice="m", host_b_voice="f",
            )

    def test_enqueue_receives_correct_request(self):
        uc, ch_port, audio_repo, ch_repo, _, task_port, _ = _make_use_case()
        ch_port.get_channel.return_value = MagicMock()
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta()
        audio_repo.create_audio_overview.return_value = _fake_audio_dto(audio_id="test-id")

        uc.start_generation(
            channel_id="fileSearchStores/test-store",
            duration_minutes=10,
            style="professional",
            language="en",
            host_a_voice="male_2",
            host_b_voice="female_2",
        )

        req = task_port.enqueue.call_args[0][0]
        assert req.audio_id == "test-id"
        assert req.duration_minutes == 10
        assert req.style == "professional"
        assert req.language == "en"
        assert req.host_a_voice == "male_2"
        assert req.host_b_voice == "female_2"


class TestList:
    """Tests for list method."""

    def test_success(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta()
        audio_repo.get_audios_by_channel.return_value = [_fake_audio_dto()]
        audio_repo.count_audios_by_channel.return_value = 1

        result = uc.list("fileSearchStores/test-store")

        assert isinstance(result, AudioOverviewListResult)
        assert result.total == 1
        assert len(result.items) == 1

    def test_channel_not_found(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_repo.get_channel_by_store_id.return_value = None

        with pytest.raises(ChannelMetadataNotFoundError):
            uc.list("fileSearchStores/missing")


class TestGet:
    """Tests for get method."""

    def test_success(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_dto = _fake_audio_dto(audio_id="audio-1", channel_id=1)
        audio_repo.get_audio_by_id.return_value = audio_dto
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta(id=1)

        result = uc.get("fileSearchStores/test-store", "audio-1")
        assert result.dto.audio_id == "audio-1"

    def test_audio_not_found(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_repo.get_audio_by_id.return_value = None

        with pytest.raises(AudioNotFoundError):
            uc.get("fileSearchStores/test-store", "missing")

    def test_audio_wrong_channel(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_dto = _fake_audio_dto(audio_id="audio-1", channel_id=1)
        audio_repo.get_audio_by_id.return_value = audio_dto
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta(id=2)

        with pytest.raises(AudioNotFoundError):
            uc.get("fileSearchStores/other", "audio-1")


class TestGetStreamInfo:
    """Tests for get_stream_info method."""

    def test_success(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_dto = _fake_audio_dto(audio_id="audio-1", channel_id=1)
        audio_dto.status = "completed"
        audio_dto.audio_path = "/data/audio.mp3"
        audio_dto.title = "Podcast"
        audio_repo.get_audio_by_id.return_value = audio_dto
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta(id=1)

        info = uc.get_stream_info("fileSearchStores/test-store", "audio-1")
        assert isinstance(info, StreamInfo)
        assert info.audio_path == "/data/audio.mp3"
        assert info.title == "Podcast"

    def test_not_ready(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_dto = _fake_audio_dto(audio_id="audio-1", channel_id=1)
        audio_dto.status = "generating_audio"
        audio_repo.get_audio_by_id.return_value = audio_dto
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta(id=1)

        with pytest.raises(AudioNotReadyError):
            uc.get_stream_info("fileSearchStores/test-store", "audio-1")

    def test_no_audio_file(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_dto = _fake_audio_dto(audio_id="audio-1", channel_id=1)
        audio_dto.status = "completed"
        audio_dto.audio_path = None
        audio_repo.get_audio_by_id.return_value = audio_dto
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta(id=1)

        with pytest.raises(AudioFileNotFoundError):
            uc.get_stream_info("fileSearchStores/test-store", "audio-1")


class TestDelete:
    """Tests for delete method."""

    def test_success_with_audio_file(self):
        uc, _, audio_repo, _, tts_port, _, _ = _make_use_case()
        audio_dto = _fake_audio_dto(audio_id="audio-1", channel_id=1)
        audio_dto.audio_path = "/data/audio.mp3"
        audio_repo.get_audio_by_id.return_value = audio_dto
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta(id=1)

        uc.delete("fileSearchStores/test-store", "audio-1")

        tts_port.delete_audio.assert_called_once_with("audio-1")
        audio_repo.delete_audio.assert_called_once_with("audio-1")

    def test_success_without_audio_file(self):
        uc, _, audio_repo, _, tts_port, _, _ = _make_use_case()
        audio_dto = _fake_audio_dto(audio_id="audio-1", channel_id=1)
        audio_dto.audio_path = None
        audio_repo.get_audio_by_id.return_value = audio_dto
        audio_repo.get_channel_by_store_id.return_value = _fake_channel_meta(id=1)

        uc.delete("fileSearchStores/test-store", "audio-1")

        tts_port.delete_audio.assert_not_called()
        audio_repo.delete_audio.assert_called_once_with("audio-1")

    def test_not_found(self):
        uc, _, audio_repo, _, _, _, _ = _make_use_case()
        audio_repo.get_audio_by_id.return_value = None

        with pytest.raises(AudioNotFoundError):
            uc.delete("fileSearchStores/test-store", "missing")


class TestPreviewScript:
    """Tests for preview_script method."""

    def test_success(self):
        uc, ch_port, _, ch_repo, _, _, script_uc = _make_use_case()
        ch_port.get_channel.return_value = MagicMock()
        script_uc.execute.return_value = PodcastScriptDTO(
            title="Preview",
            introduction="Intro",
            dialogue=[
                DialogueLineDTO(speaker="Host A", text="Hi"),
                DialogueLineDTO(speaker="Host B", text="Hello"),
            ],
            conclusion="Bye",
            estimated_duration_seconds=120,
        )

        result = uc.preview_script(
            channel_id="fileSearchStores/test-store",
            duration_minutes=3,
            style="conversational",
            language="ko",
            host_a_voice="male_1",
            host_b_voice="female_1",
        )

        assert isinstance(result, ScriptPreviewResult)
        assert result.title == "Preview"
        assert len(result.dialogue) == 2
        assert result.dialogue[0]["voice"] == "male_1"
        assert result.dialogue[1]["voice"] == "female_1"
        ch_repo.touch.assert_called_once()

    def test_channel_not_found(self):
        uc, ch_port, _, _, _, _, _ = _make_use_case()
        ch_port.get_channel.return_value = None

        with pytest.raises(ChannelNotFoundError):
            uc.preview_script(
                channel_id="fileSearchStores/missing",
                duration_minutes=3, style="conversational",
                language="ko", host_a_voice="m", host_b_voice="f",
            )

    def test_script_generation_error(self):
        uc, ch_port, _, _, _, _, script_uc = _make_use_case()
        ch_port.get_channel.return_value = MagicMock()
        script_uc.execute.side_effect = Exception("API Error")

        with pytest.raises(ScriptGenerationError, match="Failed to generate script"):
            uc.preview_script(
                channel_id="fileSearchStores/test-store",
                duration_minutes=3, style="conversational",
                language="ko", host_a_voice="m", host_b_voice="f",
            )

    def test_voice_assignment_korean_speaker(self):
        """Voice assignment should work with Korean speaker names."""
        uc, ch_port, _, _, _, _, script_uc = _make_use_case()
        ch_port.get_channel.return_value = MagicMock()
        script_uc.execute.return_value = PodcastScriptDTO(
            title="Korean",
            introduction="Intro",
            dialogue=[
                DialogueLineDTO(speaker="진행자 A", text="안녕하세요"),
                DialogueLineDTO(speaker="진행자 B", text="반갑습니다"),
            ],
            conclusion="끝",
            estimated_duration_seconds=60,
        )

        result = uc.preview_script(
            channel_id="fileSearchStores/test-store",
            duration_minutes=1, style="conversational",
            language="ko", host_a_voice="male_1", host_b_voice="female_1",
        )

        # "진행자" in speaker → host_a_voice
        assert result.dialogue[0]["voice"] == "male_1"
        # "진행자 B" also contains "진행자" → host_a_voice
        assert result.dialogue[1]["voice"] == "male_1"
