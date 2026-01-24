# -*- coding: utf-8 -*-
"""Text-to-Speech service using Edge TTS."""

import asyncio
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import edge_tts

from src.models.audio import VoiceType, DialogueLine, PodcastScript


# Voice mapping for Edge TTS
# Korean voices
VOICE_MAP_KO = {
    VoiceType.MALE_1: "ko-KR-InJoonNeural",
    VoiceType.MALE_2: "ko-KR-HyunsuNeural",
    VoiceType.FEMALE_1: "ko-KR-SunHiNeural",
    VoiceType.FEMALE_2: "ko-KR-YuJinNeural",
}

# English voices
VOICE_MAP_EN = {
    VoiceType.MALE_1: "en-US-GuyNeural",
    VoiceType.MALE_2: "en-US-ChristopherNeural",
    VoiceType.FEMALE_1: "en-US-JennyNeural",
    VoiceType.FEMALE_2: "en-US-AriaNeural",
}

# Voice rate adjustments for natural speech
VOICE_RATES = {
    VoiceType.MALE_1: "+0%",
    VoiceType.MALE_2: "-5%",
    VoiceType.FEMALE_1: "+5%",
    VoiceType.FEMALE_2: "+0%",
}


def get_voice_name(voice_type: VoiceType, language: str = "ko") -> str:
    """Get Edge TTS voice name for the given voice type."""
    voice_map = VOICE_MAP_KO if language == "ko" else VOICE_MAP_EN
    return voice_map.get(voice_type, voice_map[VoiceType.MALE_1])


class TTSService:
    """Text-to-Speech service for generating podcast audio."""

    def __init__(self, audio_dir: str = "data/audio"):
        """Initialize TTS service.

        Args:
            audio_dir: Directory to store generated audio files
        """
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    async def synthesize_text(
        self,
        text: str,
        voice_type: VoiceType,
        language: str = "ko",
        output_path: str | None = None,
    ) -> str:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_type: Voice type to use
            language: Language code (ko, en)
            output_path: Optional output path (generates temp file if not provided)

        Returns:
            Path to the generated audio file
        """
        if output_path is None:
            output_path = str(self.audio_dir / f"{uuid.uuid4()}.mp3")

        voice_name = get_voice_name(voice_type, language)
        rate = VOICE_RATES.get(voice_type, "+0%")

        communicate = edge_tts.Communicate(text, voice_name, rate=rate)
        await communicate.save(output_path)

        return output_path

    async def synthesize_dialogue_line(
        self,
        line: DialogueLine,
        language: str = "ko",
    ) -> str:
        """Synthesize a single dialogue line.

        Args:
            line: Dialogue line to synthesize
            language: Language code

        Returns:
            Path to the generated audio file
        """
        return await self.synthesize_text(
            text=line.text,
            voice_type=line.voice,
            language=language,
        )

    async def generate_podcast_audio(
        self,
        script: PodcastScript,
        language: str = "ko",
        host_a_voice: VoiceType = VoiceType.MALE_1,
        host_b_voice: VoiceType = VoiceType.FEMALE_1,
    ) -> tuple[str, int]:
        """Generate complete podcast audio from script.

        Args:
            script: Podcast script to synthesize
            language: Language code
            host_a_voice: Voice for Host A
            host_b_voice: Voice for Host B

        Returns:
            Tuple of (path to final audio file, duration in seconds)
        """
        audio_id = str(uuid.uuid4())
        temp_files: list[str] = []

        try:
            # Generate intro audio
            intro_path = await self.synthesize_text(
                text=script.introduction,
                voice_type=host_a_voice,
                language=language,
            )
            temp_files.append(intro_path)

            # Generate dialogue audio
            for line in script.dialogue:
                # Map speaker to voice
                if "Host A" in line.speaker or "진행자" in line.speaker:
                    voice = host_a_voice
                else:
                    voice = host_b_voice

                line_path = await self.synthesize_text(
                    text=line.text,
                    voice_type=voice,
                    language=language,
                )
                temp_files.append(line_path)

            # Generate conclusion audio
            conclusion_path = await self.synthesize_text(
                text=script.conclusion,
                voice_type=host_a_voice,
                language=language,
            )
            temp_files.append(conclusion_path)

            # Merge all audio files
            final_path = str(self.audio_dir / f"{audio_id}.mp3")
            duration = self._merge_audio_files(temp_files, final_path)

            return final_path, duration

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                if temp_file != final_path and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass

    def _merge_audio_files(
        self,
        audio_files: list[str],
        output_path: str,
        pause_ms: int = 500,
    ) -> int:
        """Merge multiple audio files into one.

        Uses ffmpeg for audio concatenation. Falls back to simple copy if ffmpeg unavailable.

        Args:
            audio_files: List of audio file paths to merge
            output_path: Output file path
            pause_ms: Pause duration between clips in milliseconds

        Returns:
            Total duration in seconds
        """
        if not audio_files:
            return 0

        if len(audio_files) == 1:
            # Just copy the single file
            import shutil
            shutil.copy(audio_files[0], output_path)
            return self._get_audio_duration(output_path)

        try:
            # Try using ffmpeg for merging
            return self._merge_with_ffmpeg(audio_files, output_path, pause_ms)
        except (FileNotFoundError, subprocess.CalledProcessError):
            # Fallback: just concatenate binary data (works for similar mp3 files)
            return self._merge_simple(audio_files, output_path)

    def _merge_with_ffmpeg(
        self,
        audio_files: list[str],
        output_path: str,
        pause_ms: int = 500,
    ) -> int:
        """Merge audio files using ffmpeg with silence padding."""
        # Create concat file list
        concat_file = Path(self.audio_dir) / f"concat_{uuid.uuid4()}.txt"

        try:
            with open(concat_file, "w", encoding="utf-8") as f:
                for audio_file in audio_files:
                    # Escape path for ffmpeg
                    escaped_path = audio_file.replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")

            # Run ffmpeg concat
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_file), "-c", "copy", output_path
                ],
                capture_output=True,
                check=True,
            )

            return self._get_audio_duration(output_path)

        finally:
            if concat_file.exists():
                concat_file.unlink()

    def _merge_simple(
        self,
        audio_files: list[str],
        output_path: str,
    ) -> int:
        """Simple binary concatenation of mp3 files."""
        with open(output_path, "wb") as outfile:
            for audio_file in audio_files:
                with open(audio_file, "rb") as infile:
                    outfile.write(infile.read())

        return self._get_audio_duration(output_path)

    def _get_audio_duration(self, audio_path: str) -> int:
        """Get audio duration in seconds using ffprobe or estimation.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds (estimated if ffprobe unavailable)
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet", "-show_entries",
                    "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return int(float(result.stdout.strip()))
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
            # Estimate based on file size (rough: ~16KB per second for mp3 at 128kbps)
            file_size = os.path.getsize(audio_path)
            return max(1, file_size // 16000)

    def get_audio_path(self, audio_id: str) -> str | None:
        """Get the file path for an audio ID.

        Args:
            audio_id: Audio overview ID

        Returns:
            Path to audio file if exists, None otherwise
        """
        audio_path = self.audio_dir / f"{audio_id}.mp3"
        if audio_path.exists():
            return str(audio_path)
        return None

    def delete_audio(self, audio_id: str) -> bool:
        """Delete an audio file.

        Args:
            audio_id: Audio overview ID

        Returns:
            True if deleted, False otherwise
        """
        audio_path = self.audio_dir / f"{audio_id}.mp3"
        if audio_path.exists():
            try:
                audio_path.unlink()
                return True
            except OSError:
                return False
        return False


# Singleton instance
_tts_service: TTSService | None = None


def get_tts_service() -> TTSService:
    """Get TTS service singleton."""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
