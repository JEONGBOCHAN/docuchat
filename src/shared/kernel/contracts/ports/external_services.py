# -*- coding: utf-8 -*-
"""External service ports.

These ports define abstract interfaces for external service integrations
like YouTube, web crawling, and TTS. They allow the application layer
to work with external services without knowing about implementation details.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


# =============================================================================
# Data Transfer Objects (DTOs)
# =============================================================================

@dataclass
class YouTubeTranscriptDTO:
    """DTO for YouTube transcript."""

    video_id: str
    language: str
    full_text: str
    formatted_text: str
    segments: list[dict]  # List of {text, start, duration}


@dataclass
class YouTubeMetadataDTO:
    """DTO for YouTube video metadata."""

    video_id: str
    title: str
    channel_name: str
    duration_seconds: int | None
    language: str


@dataclass
class CrawlResultDTO:
    """DTO for URL crawl result."""

    url: str
    title: str
    content: str
    content_type: str


@dataclass
class TTSResultDTO:
    """DTO for TTS synthesis result."""

    audio_path: str
    duration_seconds: int


# =============================================================================
# Port Interfaces
# =============================================================================

class YouTubePort(ABC):
    """Port for YouTube service operations."""

    @abstractmethod
    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL.

        Args:
            url: YouTube video URL

        Returns:
            Video ID string

        Raises:
            InvalidVideoError: If URL format is invalid
        """
        ...

    @abstractmethod
    def get_transcript(
        self,
        video_id: str,
        preferred_languages: list[str] | None = None,
    ) -> YouTubeTranscriptDTO:
        """Get transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            preferred_languages: List of preferred language codes

        Returns:
            YouTubeTranscriptDTO with transcript data

        Raises:
            TranscriptNotAvailableError: If transcript is not available
            YouTubeServiceError: If YouTube service fails
        """
        ...

    @abstractmethod
    def get_video_metadata(self, video_id: str) -> YouTubeMetadataDTO:
        """Get basic video metadata.

        Args:
            video_id: YouTube video ID

        Returns:
            YouTubeMetadataDTO with available information
        """
        ...

    @abstractmethod
    def save_transcript_to_temp_file(
        self,
        video_id: str,
        transcript: YouTubeTranscriptDTO,
        include_timestamps: bool = True,
    ) -> str:
        """Save transcript to a temporary file.

        Args:
            video_id: YouTube video ID
            transcript: Transcript DTO
            include_timestamps: Whether to include timestamps

        Returns:
            Path to temporary file
        """
        ...


class CrawlerPort(ABC):
    """Port for URL crawling operations."""

    @abstractmethod
    def fetch_url(self, url: str) -> CrawlResultDTO:
        """Fetch content from a URL.

        Args:
            url: The URL to fetch

        Returns:
            CrawlResultDTO with extracted content

        Raises:
            ValueError: If URL is invalid or fetch fails
        """
        ...

    @abstractmethod
    def save_to_temp_file(self, result: CrawlResultDTO) -> str:
        """Save crawl result to a temporary file.

        Args:
            result: The crawl result to save

        Returns:
            Path to the temporary file
        """
        ...


class TTSPort(ABC):
    """Port for Text-to-Speech operations."""

    @abstractmethod
    async def synthesize_text(
        self,
        text: str,
        voice_type: str,
        language: str = "ko",
        output_path: str | None = None,
    ) -> str:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice_type: Voice type identifier
            language: Language code (ko, en)
            output_path: Optional output path

        Returns:
            Path to the generated audio file
        """
        ...

    @abstractmethod
    async def generate_podcast_audio(
        self,
        script_json: str,
        language: str = "ko",
        host_a_voice: str = "male_1",
        host_b_voice: str = "female_1",
    ) -> TTSResultDTO:
        """Generate complete podcast audio from script.

        Args:
            script_json: Podcast script as JSON string
            language: Language code
            host_a_voice: Voice identifier for Host A
            host_b_voice: Voice identifier for Host B

        Returns:
            TTSResultDTO with path and duration
        """
        ...

    @abstractmethod
    def get_audio_path(self, audio_id: str) -> str | None:
        """Get the file path for an audio ID.

        Args:
            audio_id: Audio overview ID

        Returns:
            Path to audio file if exists, None otherwise
        """
        ...

    @abstractmethod
    def delete_audio(self, audio_id: str) -> bool:
        """Delete an audio file.

        Args:
            audio_id: Audio overview ID

        Returns:
            True if deleted, False otherwise
        """
        ...
