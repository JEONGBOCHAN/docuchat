# -*- coding: utf-8 -*-
"""Audio overview orchestration use case.

Consolidates audio overview CRUD and generation orchestration
that was previously in the presentation router.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, UTC

from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.persistence import (
    AudioRepositoryPort,
    ChannelRepositoryPort,
    AudioOverviewDTO,
    ChannelMetadataDTO,
)
from src.shared.kernel.contracts.ports.external_services import TTSPort
from src.shared.kernel.contracts.ports.infrastructure import AudioGenerationTaskPort
from src.modules.knowledge.application.use_cases.audio_generation import AudioGenerationRequest
from src.modules.knowledge.application.use_cases.podcast import (
    GeneratePodcastScriptUseCase,
    GeneratePodcastScriptRequest,
)
from src.shared.kernel.contracts.ports.podcast import PodcastScriptDTO, DialogueLineDTO

logger = logging.getLogger(__name__)


# ── Errors ──────────────────────────────────────────────────

class ChannelNotFoundError(Exception):
    """Raised when the external channel does not exist."""


class ChannelMetadataNotFoundError(Exception):
    """Raised when local channel metadata is missing."""


class AudioNotFoundError(Exception):
    """Raised when an audio overview record is not found."""


class AudioNotReadyError(Exception):
    """Raised when audio file is not ready for streaming."""


class AudioFileNotFoundError(Exception):
    """Raised when audio file path is missing."""


class ScriptGenerationError(Exception):
    """Raised when script preview generation fails."""


# ── DTOs ────────────────────────────────────────────────────

@dataclass
class AudioOverviewResult:
    """Result from audio overview operations."""

    dto: AudioOverviewDTO
    channel_store_id: str


@dataclass
class AudioOverviewListResult:
    """Result from listing audio overviews."""

    items: list[AudioOverviewDTO]
    total: int
    channel_store_id: str


@dataclass
class ScriptPreviewResult:
    """Result from script preview generation."""

    title: str
    introduction: str
    dialogue: list[dict]
    conclusion: str
    estimated_duration_seconds: int
    channel_store_id: str
    generated_at: datetime


@dataclass
class StreamInfo:
    """Information needed to stream an audio file."""

    audio_path: str
    title: str | None


# ── Use Case ────────────────────────────────────────────────

class AudioOverviewUseCase:
    """Orchestrates audio overview operations.

    Handles validation, repository interaction, and background task dispatching
    for audio overview CRUD operations.
    """

    def __init__(
        self,
        channel_port: ChannelPort,
        audio_repo: AudioRepositoryPort,
        channel_repo: ChannelRepositoryPort,
        tts_port: TTSPort,
        task_port: AudioGenerationTaskPort,
        script_use_case: GeneratePodcastScriptUseCase,
    ):
        self._channel_port = channel_port
        self._audio_repo = audio_repo
        self._channel_repo = channel_repo
        self._tts = tts_port
        self._task_port = task_port
        self._script_use_case = script_use_case

    # ── helpers ──────────────────────────────────────────

    def _validate_channel(self, channel_id: str) -> None:
        """Validate channel exists in external store."""
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            raise ChannelNotFoundError(f"Channel not found: {channel_id}")

    def _get_channel_metadata(self, channel_id: str) -> ChannelMetadataDTO:
        """Get local channel metadata or raise."""
        channel_dto = self._audio_repo.get_channel_by_store_id(channel_id)
        if not channel_dto:
            raise ChannelMetadataNotFoundError(
                f"Channel metadata not found: {channel_id}"
            )
        return channel_dto

    def _get_audio_in_channel(
        self, channel_id: str, audio_id: str,
    ) -> tuple[AudioOverviewDTO, ChannelMetadataDTO]:
        """Get audio overview and verify it belongs to the channel."""
        audio_dto = self._audio_repo.get_audio_by_id(audio_id)
        if not audio_dto:
            raise AudioNotFoundError(f"Audio overview not found: {audio_id}")

        channel_dto = self._audio_repo.get_channel_by_store_id(channel_id)
        if not channel_dto or audio_dto.channel_id != channel_dto.id:
            raise AudioNotFoundError(
                f"Audio overview not found in channel: {channel_id}"
            )

        return audio_dto, channel_dto

    # ── public methods ──────────────────────────────────

    def start_generation(
        self,
        channel_id: str,
        duration_minutes: int,
        style: str,
        language: str,
        host_a_voice: str,
        host_b_voice: str,
    ) -> AudioOverviewResult:
        """Start audio overview generation.

        Validates channel, creates DB record, dispatches background task.

        Raises:
            ChannelNotFoundError: External channel not found.
            ChannelMetadataNotFoundError: Local metadata missing.
        """
        self._validate_channel(channel_id)
        channel_dto = self._get_channel_metadata(channel_id)

        # Update last accessed time
        self._channel_repo.touch(channel_id)

        # Create audio overview record
        audio_dto = self._audio_repo.create_audio_overview(
            channel_id=channel_dto.id,
            language=language,
            style=style,
        )

        # Build and dispatch background generation request
        gen_request = AudioGenerationRequest(
            audio_id=audio_dto.audio_id,
            store_name=channel_id,
            duration_minutes=duration_minutes,
            style=style,
            language=language,
            host_a_voice=host_a_voice,
            host_b_voice=host_b_voice,
        )
        self._task_port.enqueue(gen_request)

        return AudioOverviewResult(dto=audio_dto, channel_store_id=channel_id)

    def list(
        self, channel_id: str, limit: int = 20, offset: int = 0,
    ) -> AudioOverviewListResult:
        """List audio overviews for a channel.

        Raises:
            ChannelMetadataNotFoundError: Local metadata missing.
        """
        channel_dto = self._get_channel_metadata(channel_id)

        audios = self._audio_repo.get_audios_by_channel(
            channel_dto.id, limit=limit, offset=offset,
        )
        total = self._audio_repo.count_audios_by_channel(channel_dto.id)

        return AudioOverviewListResult(
            items=audios, total=total, channel_store_id=channel_id,
        )

    def get(self, channel_id: str, audio_id: str) -> AudioOverviewResult:
        """Get a specific audio overview.

        Raises:
            AudioNotFoundError: Audio not found or not in channel.
        """
        audio_dto, _ = self._get_audio_in_channel(channel_id, audio_id)
        return AudioOverviewResult(dto=audio_dto, channel_store_id=channel_id)

    def get_stream_info(self, channel_id: str, audio_id: str) -> StreamInfo:
        """Get stream information for an audio file.

        Raises:
            AudioNotFoundError: Audio not found or not in channel.
            AudioNotReadyError: Audio is not in completed status.
            AudioFileNotFoundError: Audio file path is missing.
        """
        audio_dto, _ = self._get_audio_in_channel(channel_id, audio_id)

        if audio_dto.status != "completed":
            raise AudioNotReadyError(
                f"Audio is not ready. Current status: {audio_dto.status}"
            )

        if not audio_dto.audio_path:
            raise AudioFileNotFoundError("Audio file not found")

        return StreamInfo(
            audio_path=audio_dto.audio_path,
            title=audio_dto.title,
        )

    def delete(self, channel_id: str, audio_id: str) -> None:
        """Delete an audio overview and its audio file.

        Raises:
            AudioNotFoundError: Audio not found or not in channel.
        """
        audio_dto, _ = self._get_audio_in_channel(channel_id, audio_id)

        # Delete audio file if it exists
        if audio_dto.audio_path:
            self._tts.delete_audio(audio_dto.audio_id)

        # Delete database record
        self._audio_repo.delete_audio(audio_id)

    def preview_script(
        self,
        channel_id: str,
        duration_minutes: int,
        style: str,
        language: str,
        host_a_voice: str,
        host_b_voice: str,
    ) -> ScriptPreviewResult:
        """Generate and preview podcast script without creating audio.

        Raises:
            ChannelNotFoundError: External channel not found.
            ScriptGenerationError: Script generation failed.
        """
        self._validate_channel(channel_id)

        # Update last accessed time
        self._channel_repo.touch(channel_id)

        # Generate script
        script_request = GeneratePodcastScriptRequest(
            store_name=channel_id,
            duration_minutes=duration_minutes,
            style=style,
            language=language,
        )

        try:
            script_dto = self._script_use_case.execute(script_request)
        except Exception as e:
            raise ScriptGenerationError(f"Failed to generate script: {e}") from e

        # Assign voices to dialogue lines
        dialogue = []
        for line in script_dto.dialogue:
            speaker = line.speaker
            if "Host A" in speaker or "진행자" in speaker:
                voice = host_a_voice
            else:
                voice = host_b_voice

            dialogue.append({
                "speaker": speaker,
                "text": line.text,
                "voice": voice,
            })

        return ScriptPreviewResult(
            title=script_dto.title,
            introduction=script_dto.introduction,
            dialogue=dialogue,
            conclusion=script_dto.conclusion,
            estimated_duration_seconds=script_dto.estimated_duration_seconds,
            channel_store_id=channel_id,
            generated_at=datetime.now(UTC),
        )
