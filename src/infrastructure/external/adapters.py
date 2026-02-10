# -*- coding: utf-8 -*-
"""External service adapters that implement application ports.

These adapters wrap the existing external service implementations and convert
between service-specific types and application DTOs.
"""

from src.shared.kernel.contracts.ports.external_services import (
    YouTubePort,
    YouTubeTranscriptDTO,
    YouTubeMetadataDTO,
    CrawlerPort,
    CrawlResultDTO,
    TTSPort,
    TTSResultDTO,
)
from src.shared.kernel.contracts.errors.use_case_errors import (
    YouTubeError,
    InvalidVideoError,
    TranscriptNotAvailableError,
)


# =============================================================================
# YouTube Adapter
# =============================================================================

class YouTubeAdapter(YouTubePort):
    """Adapter that implements YouTubePort.

    Converts infrastructure-level YouTube exceptions to application-level
    exceptions so the API layer doesn't depend on infrastructure.
    """

    def __init__(self):
        """Initialize adapter."""
        from src.infrastructure.external.youtube.youtube_service import YouTubeService
        self._service = YouTubeService()

    def _convert_exception(self, e: Exception) -> Exception:
        """Convert infrastructure YouTube exceptions to application exceptions."""
        from src.infrastructure.external.youtube.youtube_service import (
            InvalidVideoError as InfraInvalidVideo,
            TranscriptNotAvailableError as InfraTranscriptNotAvailable,
            YouTubeServiceError as InfraYouTubeError,
        )
        if isinstance(e, InfraInvalidVideo):
            return InvalidVideoError(str(e))
        if isinstance(e, InfraTranscriptNotAvailable):
            return TranscriptNotAvailableError(str(e))
        if isinstance(e, InfraYouTubeError):
            return YouTubeError(str(e))
        return e

    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL."""
        try:
            return self._service.extract_video_id(url)
        except Exception as e:
            raise self._convert_exception(e) from e

    def get_transcript(
        self,
        video_id: str,
        preferred_languages: list[str] | None = None,
    ) -> YouTubeTranscriptDTO:
        """Get transcript for a YouTube video."""
        try:
            transcript = self._service.get_transcript(video_id, preferred_languages)
            return YouTubeTranscriptDTO(
                video_id=transcript.video_id,
                language=transcript.language,
                full_text=transcript.full_text,
                formatted_text=transcript.formatted_text,
                segments=[
                    {"text": s.text, "start": s.start, "duration": s.duration}
                    for s in transcript.segments
                ],
            )
        except Exception as e:
            raise self._convert_exception(e) from e

    def get_video_metadata(self, video_id: str) -> YouTubeMetadataDTO:
        """Get basic video metadata."""
        try:
            metadata = self._service.get_video_metadata(video_id)
            return YouTubeMetadataDTO(
                video_id=metadata.video_id,
                title=metadata.title,
                channel_name=metadata.channel_name,
                duration_seconds=metadata.duration_seconds,
                language=metadata.language,
            )
        except Exception as e:
            raise self._convert_exception(e) from e

    def save_transcript_to_temp_file(
        self,
        video_id: str,
        transcript: YouTubeTranscriptDTO,
        include_timestamps: bool = True,
    ) -> str:
        """Save transcript to a temporary file."""
        from src.models.youtube import YouTubeTranscript, YouTubeTranscriptSegment

        # Convert DTO back to model for the service
        model_transcript = YouTubeTranscript(
            video_id=transcript.video_id,
            language=transcript.language,
            segments=[
                YouTubeTranscriptSegment(
                    text=s["text"],
                    start=s["start"],
                    duration=s["duration"],
                )
                for s in transcript.segments
            ],
        )

        return self._service.save_transcript_to_temp_file(
            video_id, model_transcript, include_timestamps
        )


# =============================================================================
# Crawler Adapter
# =============================================================================

class CrawlerAdapter(CrawlerPort):
    """Adapter that implements CrawlerPort."""

    def __init__(self):
        """Initialize adapter."""
        from src.infrastructure.external.crawler.crawler import CrawlerService
        self._service = CrawlerService()

    def fetch_url(self, url: str) -> CrawlResultDTO:
        """Fetch content from a URL."""
        result = self._service.fetch_url(url)
        return CrawlResultDTO(
            url=result.url,
            title=result.title,
            content=result.content,
            content_type=result.content_type,
        )

    def save_to_temp_file(self, result: CrawlResultDTO) -> str:
        """Save crawl result to a temporary file."""
        from src.infrastructure.external.crawler.crawler import CrawlResult

        # Convert DTO back to model for the service
        model_result = CrawlResult(
            url=result.url,
            title=result.title,
            content=result.content,
            content_type=result.content_type,
        )

        return self._service.save_to_temp_file(model_result)


# =============================================================================
# TTS Adapter
# =============================================================================

class TTSAdapter(TTSPort):
    """Adapter that implements TTSPort."""

    def __init__(self):
        """Initialize adapter."""
        from src.infrastructure.external.tts.tts_service import TTSService
        self._service = TTSService()

    async def synthesize_text(
        self,
        text: str,
        voice_type: str,
        language: str = "ko",
        output_path: str | None = None,
    ) -> str:
        """Synthesize text to speech."""
        from src.shared.kernel.contracts.dto.enums import VoiceType

        vt = VoiceType(voice_type)
        return await self._service.synthesize_text(text, vt, language, output_path)

    async def generate_podcast_audio(
        self,
        script_json: str,
        language: str = "ko",
        host_a_voice: str = "male_1",
        host_b_voice: str = "female_1",
    ) -> TTSResultDTO:
        """Generate complete podcast audio from script."""
        import json
        from src.shared.kernel.contracts.dto.enums import VoiceType
        from src.models.audio import PodcastScript, DialogueLine

        # Parse script JSON
        script_data = json.loads(script_json)

        # Convert to PodcastScript model
        dialogue = [
            DialogueLine(
                speaker=d["speaker"],
                text=d["text"],
                voice=VoiceType(d.get("voice", "male_1")),
            )
            for d in script_data.get("dialogue", [])
        ]

        script = PodcastScript(
            title=script_data.get("title", ""),
            introduction=script_data.get("introduction", ""),
            dialogue=dialogue,
            conclusion=script_data.get("conclusion", ""),
            estimated_duration_seconds=script_data.get("estimated_duration_seconds", 0),
        )

        audio_path, duration = await self._service.generate_podcast_audio(
            script=script,
            language=language,
            host_a_voice=VoiceType(host_a_voice),
            host_b_voice=VoiceType(host_b_voice),
        )

        return TTSResultDTO(
            audio_path=audio_path,
            duration_seconds=duration,
        )

    def get_audio_path(self, audio_id: str) -> str | None:
        """Get the file path for an audio ID."""
        return self._service.get_audio_path(audio_id)

    def delete_audio(self, audio_id: str) -> bool:
        """Delete an audio file."""
        return self._service.delete_audio(audio_id)
