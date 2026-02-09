# -*- coding: utf-8 -*-
"""
Shared domain enums used across application and infrastructure layers.

These enums represent domain-level concepts (audio status, voice types,
trash item types) that both infrastructure implementations and API models
legitimately depend on. Defining them here in the application layer
ensures proper dependency direction: infrastructure → application (allowed).
"""

from enum import Enum


class AudioStatus(str, Enum):
    """Status of audio generation."""

    PENDING = "pending"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_AUDIO = "generating_audio"
    COMPLETED = "completed"
    FAILED = "failed"


class VoiceType(str, Enum):
    """Voice types for hosts."""

    MALE_1 = "male_1"
    MALE_2 = "male_2"
    FEMALE_1 = "female_1"
    FEMALE_2 = "female_2"


class TrashItemType(str, Enum):
    """Type of trashed item."""

    CHANNEL = "channel"
    NOTE = "note"
