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
