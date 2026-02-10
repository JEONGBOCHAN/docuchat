# -*- coding: utf-8 -*-
"""Domain exceptions.

These exceptions represent domain-specific error conditions that
can be raised throughout the application.
"""


class DomainException(Exception):
    """Base exception for all domain exceptions."""

    pass


# =============================================================================
# Note Exceptions
# =============================================================================


class NoteValidationError(DomainException):
    """Raised when note validation fails."""

    pass


class NoteTitleError(NoteValidationError):
    """Raised when note title is invalid."""

    pass


class NoteContentError(NoteValidationError):
    """Raised when note content is invalid."""

    pass


# =============================================================================
# Channel Exceptions
# =============================================================================


class ChannelValidationError(DomainException):
    """Raised when channel validation fails."""

    pass


class ChannelNameError(ChannelValidationError):
    """Raised when channel name is invalid."""

    pass


# =============================================================================
# ChatMessage Exceptions
# =============================================================================


class ChatMessageValidationError(DomainException):
    """Raised when chat message validation fails."""

    pass


class InvalidRoleError(ChatMessageValidationError):
    """Raised when message role is invalid."""

    pass


class MessageContentError(ChatMessageValidationError):
    """Raised when message content is invalid."""

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
