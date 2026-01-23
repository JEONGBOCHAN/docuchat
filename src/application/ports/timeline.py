# -*- coding: utf-8 -*-
"""
Timeline and Briefing Port.

Defines the interface for timeline extraction and briefing generation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TimelineEventDTO:
    """A single timeline event."""

    date: str
    title: str
    description: str
    source: str | None = None


@dataclass
class BriefingSectionDTO:
    """A section in a briefing document."""

    title: str
    content: str


@dataclass
class BriefingDTO:
    """Result of briefing generation."""

    title: str
    executive_summary: str
    sections: list[BriefingSectionDTO] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)


class TimelinePort(ABC):
    """Abstract interface for timeline generation.

    Implementations extract chronological events from documents.

    Example:
        adapter = GeminiTimelineAdapter(gemini_service)
        events = adapter.generate_timeline("channel-123", max_events=10)
    """

    @abstractmethod
    def generate_timeline(
        self,
        store_name: str,
        max_events: int = 20,
    ) -> list[TimelineEventDTO]:
        """Generate a timeline of events from documents.

        Args:
            store_name: The document store to analyze
            max_events: Maximum number of events to extract (1-50)

        Returns:
            List of TimelineEventDTO objects sorted chronologically
        """
        pass


class BriefingPort(ABC):
    """Abstract interface for briefing generation.

    Implementations create structured briefing documents from content.

    Example:
        adapter = GeminiBriefingAdapter(gemini_service)
        briefing = adapter.generate_briefing("channel-123", style="executive")
    """

    @abstractmethod
    def generate_briefing(
        self,
        store_name: str,
        style: str = "executive",
        max_sections: int = 5,
    ) -> BriefingDTO:
        """Generate a briefing document from content.

        Args:
            store_name: The document store to analyze
            style: 'executive' (concise) or 'detailed' (comprehensive)
            max_sections: Maximum number of sections (1-10)

        Returns:
            BriefingDTO with the generated briefing
        """
        pass
