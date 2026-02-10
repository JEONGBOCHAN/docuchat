# -*- coding: utf-8 -*-
"""Audio generation use case.

Orchestrates the full podcast audio generation pipeline:
script generation -> voice assignment -> TTS -> completion.

This use case extracts the business logic that was previously embedded
in the API router's background task function.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.application.ports.persistence import AudioRepositoryPort
from src.application.ports.external_services import TTSPort
from src.application.use_cases.podcast import (
    GeneratePodcastScriptUseCase,
    GeneratePodcastScriptRequest,
)

logger = logging.getLogger(__name__)


@dataclass
class AudioGenerationRequest:
    """Request parameters for audio generation."""

    audio_id: str
    store_name: str
    duration_minutes: int
    style: str
    language: str
    host_a_voice: str
    host_b_voice: str


class GenerateAudioUseCase:
    """Orchestrates full podcast audio generation.

    Pipeline: script generation -> voice assignment -> TTS -> DB update.
    """

    def __init__(
        self,
        audio_repo: AudioRepositoryPort,
        tts_port: TTSPort,
        script_use_case: GeneratePodcastScriptUseCase,
    ):
        self._audio_repo = audio_repo
        self._tts = tts_port
        self._script_use_case = script_use_case

    async def execute(self, request: AudioGenerationRequest) -> None:
        """Run the full audio generation pipeline.

        Updates the audio record status as the pipeline progresses.
        On failure, marks the record as failed with error message.
        """
        try:
            # Step 1: Generate script
            self._audio_repo.update_status(request.audio_id, "generating_script")

            script_request = GeneratePodcastScriptRequest(
                store_name=request.store_name,
                duration_minutes=request.duration_minutes,
                style=request.style,
                language=request.language,
            )

            try:
                script_dto = self._script_use_case.execute(script_request)
            except Exception as e:
                self._audio_repo.update_status(
                    request.audio_id, "failed", error_message=str(e),
                )
                return

            # Step 2: Build script JSON with voice assignments
            dialogue_lines = []
            for line in script_dto.dialogue:
                if "Host A" in line.speaker or "진행자" in line.speaker:
                    voice = request.host_a_voice
                else:
                    voice = request.host_b_voice

                dialogue_lines.append({
                    "speaker": line.speaker,
                    "text": line.text,
                    "voice": voice,
                })

            script_data = {
                "title": script_dto.title,
                "introduction": script_dto.introduction,
                "dialogue": dialogue_lines,
                "conclusion": script_dto.conclusion,
                "estimated_duration_seconds": script_dto.estimated_duration_seconds,
            }
            script_json = json.dumps(script_data, ensure_ascii=False)

            # Step 3: Save script to DB
            self._audio_repo.update_script(
                request.audio_id, script_json, title=script_dto.title,
            )

            # Step 4: Generate audio via TTS
            tts_result = await self._tts.generate_podcast_audio(
                script_json=script_json,
                language=request.language,
                host_a_voice=request.host_a_voice,
                host_b_voice=request.host_b_voice,
            )

            # Step 5: Mark complete
            self._audio_repo.update_audio_complete(
                request.audio_id,
                tts_result.audio_path,
                tts_result.duration_seconds,
            )

        except Exception as e:
            logger.error("Audio generation failed for %s: %s", request.audio_id, e)
            self._audio_repo.update_status(
                request.audio_id, "failed", error_message=str(e),
            )
