# -*- coding: utf-8 -*-
"""Shared use case exceptions.

Domain-level exceptions raised by use cases.
Routers catch these and translate to HTTP status codes.
"""


class ChannelNotFoundError(Exception):
    """Channel not found. Maps to HTTP 404."""

    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        super().__init__(f"Channel not found: {channel_id}")


class TargetNotFoundError(Exception):
    """Favorite target (note, document) not found. Maps to HTTP 404."""
    pass


class InvalidTargetError(Exception):
    """Invalid target format. Maps to HTTP 400."""
    pass


class FileValidationError(Exception):
    """File validation failed (extension, size). Maps to HTTP 400."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class SessionNotFoundError(Exception):
    """Chat session not found. Maps to HTTP 404."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionExpiredError(Exception):
    """Chat session has expired. Maps to HTTP 410."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session has expired: {session_id}")


class NoteValidationError(Exception):
    """Note validation failed (title/content constraints). Maps to HTTP 400."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ServiceNotConfiguredError(Exception):
    """Required external service config is missing. Maps to HTTP 503."""

    def __init__(self, service: str, missing_fields: list[str] | None = None):
        self.service = service
        self.missing_fields = missing_fields or []
        detail = f"{service} is not configured"
        if self.missing_fields:
            detail += f" (missing: {', '.join(self.missing_fields)})"
        super().__init__(detail)


class UpstreamError(Exception):
    """External service (upstream) error. Maps to HTTP 502.

    Raised when an external API call fails for reasons other than
    'resource not found' (e.g., auth failure, server error, timeout).
    """

    def __init__(self, service: str, message: str, status_code: int | None = None):
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service} error: {message}")


class YouTubeError(Exception):
    """Base YouTube operation error. Maps to HTTP 500."""
    pass


class InvalidVideoError(YouTubeError):
    """Invalid video URL or ID. Maps to HTTP 400."""
    pass


class TranscriptNotAvailableError(YouTubeError):
    """Transcript not available for the video. Maps to HTTP 422."""
    pass
