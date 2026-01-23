# -*- coding: utf-8 -*-
"""
Podcast Generation Port.

Defines the interface for podcast script generation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DialogueLineDTO:
    """A single line of dialogue in the podcast."""

    speaker: str
    text: str


@dataclass
class PodcastScriptDTO:
    """Result of podcast script generation."""

    title: str
    introduction: str
    dialogue: list[DialogueLineDTO] = field(default_factory=list)
    conclusion: str = ""
    estimated_duration_seconds: int = 0


class PodcastScriptPort(ABC):
    """Abstract interface for podcast script generation.

    Implementations create conversational podcast scripts from documents.

    Example:
        adapter = GeminiPodcastAdapter(gemini_service)
        script = adapter.generate_podcast_script(
            "channel-123",
            duration_minutes=5,
            style="conversational",
        )
    """

    @abstractmethod
    def generate_podcast_script(
        self,
        store_name: str,
        duration_minutes: int = 5,
        style: str = "conversational",
        language: str = "ko",
    ) -> PodcastScriptDTO:
        """Generate a podcast script from documents.

        Creates a conversational dialogue between two AI hosts discussing
        the document content.

        Args:
            store_name: The document store to analyze
            duration_minutes: Target duration in minutes (1-15)
            style: 'conversational' (casual) or 'professional' (formal)
            language: Language code (ko, en, ja, etc.)

        Returns:
            PodcastScriptDTO with the generated script
        """
        pass
