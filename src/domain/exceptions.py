# -*- coding: utf-8 -*-
"""Domain exceptions.

These exceptions represent domain-specific error conditions that
can be raised throughout the application.
"""


class DomainException(Exception):
    """Base exception for all domain exceptions."""

    pass


# =============================================================================
# YouTube Exceptions
# =============================================================================


class YouTubeServiceError(DomainException):
    """Base exception for YouTube service errors."""

    pass


class InvalidVideoError(YouTubeServiceError):
    """Raised when a YouTube video URL or ID is invalid."""

    pass


class TranscriptNotAvailableError(YouTubeServiceError):
    """Raised when no transcript is available for a video."""

    pass


# =============================================================================
# Crawler Exceptions
# =============================================================================


class CrawlerError(DomainException):
    """Base exception for crawler errors."""

    pass


class URLFetchError(CrawlerError):
    """Raised when URL fetch fails."""

    pass


class ContentParseError(CrawlerError):
    """Raised when content parsing fails."""

    pass


# =============================================================================
# TTS Exceptions
# =============================================================================


class TTSError(DomainException):
    """Base exception for TTS errors."""

    pass


class VoiceSynthesisError(TTSError):
    """Raised when voice synthesis fails."""

    pass


# =============================================================================
# Capacity Exceptions
# =============================================================================


class CapacityError(DomainException):
    """Base exception for capacity-related errors."""

    pass


class CapacityExceededError(CapacityError):
    """Raised when a capacity limit would be exceeded."""

    def __init__(self, message: str, limit_type: str, current: float, limit: float):
        super().__init__(message)
        self.limit_type = limit_type
        self.current = current
        self.limit = limit
