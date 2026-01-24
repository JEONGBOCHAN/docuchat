# -*- coding: utf-8 -*-
"""YouTube transcript extraction service."""

import os
import re
import tempfile
from functools import lru_cache

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from src.models.youtube import (
    YouTubeTranscript,
    YouTubeTranscriptSegment,
    YouTubeMetadata,
)


class YouTubeServiceError(Exception):
    """Base exception for YouTube service errors."""

    pass


class TranscriptNotAvailableError(YouTubeServiceError):
    """Raised when transcript is not available for the video."""

    pass


class InvalidVideoError(YouTubeServiceError):
    """Raised when video ID is invalid or video not found."""

    pass


class YouTubeService:
    """Service for extracting YouTube transcripts."""

    # Preferred languages in order of preference
    PREFERRED_LANGUAGES = ["ko", "en", "ja", "zh-Hans", "zh-Hant"]

    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL.

        Args:
            url: YouTube video URL

        Returns:
            Video ID string

        Raises:
            InvalidVideoError: If URL format is invalid
        """
        patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise InvalidVideoError(f"Could not extract video ID from URL: {url}")

    def get_transcript(
        self,
        video_id: str,
        preferred_languages: list[str] | None = None,
    ) -> YouTubeTranscript:
        """Get transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            preferred_languages: List of preferred language codes

        Returns:
            YouTubeTranscript with segments

        Raises:
            TranscriptNotAvailableError: If no transcript is available
            InvalidVideoError: If video is not found
        """
        if preferred_languages is None:
            preferred_languages = self.PREFERRED_LANGUAGES

        try:
            # Try to get transcript in preferred languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try manual transcripts first (more accurate)
            transcript = None
            language = ""

            # Try to find manual transcript in preferred languages
            for lang in preferred_languages:
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    language = lang
                    break
                except NoTranscriptFound:
                    continue

            # If no manual transcript, try generated transcripts
            if transcript is None:
                for lang in preferred_languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        language = lang
                        break
                    except NoTranscriptFound:
                        continue

            # If still no transcript, get any available transcript
            if transcript is None:
                try:
                    # Get first available transcript
                    for t in transcript_list:
                        transcript = t
                        language = t.language_code
                        break
                except Exception:
                    pass

            if transcript is None:
                raise TranscriptNotAvailableError(
                    f"No transcript available for video: {video_id}"
                )

            # Fetch the transcript data
            transcript_data = transcript.fetch()

            segments = [
                YouTubeTranscriptSegment(
                    text=item.get("text", ""),
                    start=item.get("start", 0.0),
                    duration=item.get("duration", 0.0),
                )
                for item in transcript_data
            ]

            return YouTubeTranscript(
                video_id=video_id,
                language=language,
                segments=segments,
            )

        except TranscriptsDisabled:
            raise TranscriptNotAvailableError(
                f"Transcripts are disabled for video: {video_id}"
            )
        except Exception as e:
            if "TranscriptsDisabled" in str(type(e).__name__):
                raise TranscriptNotAvailableError(
                    f"Transcripts are disabled for video: {video_id}"
                )
            if "NoTranscriptFound" in str(type(e).__name__):
                raise TranscriptNotAvailableError(
                    f"No transcript found for video: {video_id}"
                )
            raise YouTubeServiceError(f"Failed to get transcript: {str(e)}")

    def get_video_metadata(self, video_id: str) -> YouTubeMetadata:
        """Get basic video metadata.

        Note: This uses the transcript API which has limited metadata.
        For full metadata, YouTube Data API would be needed.

        Args:
            video_id: YouTube video ID

        Returns:
            YouTubeMetadata with available information
        """
        # Basic metadata - title fetching would require YouTube Data API
        # For now, return minimal metadata
        return YouTubeMetadata(
            video_id=video_id,
            title=f"YouTube Video ({video_id})",
            channel_name="",
            duration_seconds=None,
            language="",
        )

    def create_document_content(
        self,
        video_id: str,
        transcript: YouTubeTranscript,
        include_timestamps: bool = True,
    ) -> str:
        """Create document content from transcript.

        Args:
            video_id: YouTube video ID
            transcript: Extracted transcript
            include_timestamps: Whether to include timestamps

        Returns:
            Formatted document content
        """
        lines = [
            f"# YouTube Video Transcript",
            f"",
            f"**Video ID:** {video_id}",
            f"**URL:** https://www.youtube.com/watch?v={video_id}",
            f"**Language:** {transcript.language}",
            f"",
            f"---",
            f"",
            f"## Transcript",
            f"",
        ]

        if include_timestamps:
            lines.append(transcript.formatted_text)
        else:
            lines.append(transcript.full_text)

        return "\n".join(lines)

    def save_transcript_to_temp_file(
        self,
        video_id: str,
        transcript: YouTubeTranscript,
        include_timestamps: bool = True,
    ) -> str:
        """Save transcript to a temporary file.

        Args:
            video_id: YouTube video ID
            transcript: Extracted transcript
            include_timestamps: Whether to include timestamps

        Returns:
            Path to temporary file
        """
        content = self.create_document_content(video_id, transcript, include_timestamps)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(content)
            return tmp.name


@lru_cache
def get_youtube_service() -> YouTubeService:
    """Get cached YouTubeService instance."""
    return YouTubeService()
