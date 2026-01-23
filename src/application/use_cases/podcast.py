# -*- coding: utf-8 -*-
"""
Podcast Script Generation Use Case.

Application logic for generating podcast scripts from documents.
"""

from dataclasses import dataclass

from src.application.ports.podcast import (
    PodcastScriptPort,
    PodcastScriptDTO,
)


@dataclass
class GeneratePodcastScriptRequest:
    """Request for podcast script generation."""

    store_name: str
    duration_minutes: int = 5
    style: str = "conversational"
    language: str = "ko"


class GeneratePodcastScriptUseCase:
    """Use case for generating podcast scripts.

    This use case coordinates podcast script generation from documents
    using the configured adapter.

    Example:
        use_case = GeneratePodcastScriptUseCase(podcast_adapter)

        request = GeneratePodcastScriptRequest(
            store_name="channel-123",
            duration_minutes=5,
            style="conversational",
        )
        script = use_case.execute(request)
    """

    def __init__(self, podcast_port: PodcastScriptPort):
        """Initialize with a podcast script port.

        Args:
            podcast_port: The adapter implementing PodcastScriptPort
        """
        self._podcast_port = podcast_port

    def execute(self, request: GeneratePodcastScriptRequest) -> PodcastScriptDTO:
        """Execute podcast script generation.

        Args:
            request: The generation request parameters

        Returns:
            PodcastScriptDTO with the generated script

        Raises:
            Exception: If script generation fails
        """
        return self._podcast_port.generate_podcast_script(
            store_name=request.store_name,
            duration_minutes=request.duration_minutes,
            style=request.style,
            language=request.language,
        )
