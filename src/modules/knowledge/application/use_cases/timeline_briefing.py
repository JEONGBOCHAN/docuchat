# -*- coding: utf-8 -*-
"""
Timeline and Briefing Use Cases.

These use cases handle timeline extraction and briefing generation.
"""

from dataclasses import dataclass, field

from src.application.ports.timeline import (
    TimelinePort,
    BriefingPort,
    TimelineEventDTO,
    BriefingSectionDTO,
)


@dataclass
class TimelineResult:
    """Result of timeline generation.

    Attributes:
        events: List of timeline events
        channel_id: The channel/store that was analyzed
        error: Error message if generation failed
    """

    events: list[TimelineEventDTO] = field(default_factory=list)
    channel_id: str | None = None
    error: str | None = None


@dataclass
class BriefingResult:
    """Result of briefing generation.

    Attributes:
        title: Briefing title
        executive_summary: Brief overview
        sections: List of briefing sections
        key_points: Key takeaways
        channel_id: The channel/store that was analyzed
        error: Error message if generation failed
    """

    title: str = ""
    executive_summary: str = ""
    sections: list[BriefingSectionDTO] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    channel_id: str | None = None
    error: str | None = None


class GenerateTimelineUseCase:
    """Use case for generating a timeline from documents.

    This use case coordinates timeline generation through the port interface,
    allowing the underlying implementation to be swapped without changing
    the application logic.

    Example:
        use_case = GenerateTimelineUseCase(timeline_port=adapter)
        result = use_case.execute(
            channel_id="channel-123",
            max_events=10,
        )
        for event in result.events:
            print(f"{event.date}: {event.title}")
    """

    def __init__(self, timeline_port: TimelinePort):
        """Initialize the use case with dependencies.

        Args:
            timeline_port: The timeline port implementation
        """
        self.timeline_port = timeline_port

    def execute(
        self,
        channel_id: str,
        max_events: int = 20,
    ) -> TimelineResult:
        """Execute timeline generation.

        Args:
            channel_id: The channel (document store) to analyze
            max_events: Maximum number of events to extract (1-50)

        Returns:
            TimelineResult with extracted events or error
        """
        try:
            events = self.timeline_port.generate_timeline(
                store_name=channel_id,
                max_events=max_events,
            )

            return TimelineResult(
                events=events,
                channel_id=channel_id,
                error=None,
            )

        except Exception as e:
            return TimelineResult(
                events=[],
                channel_id=channel_id,
                error=str(e),
            )


class GenerateBriefingUseCase:
    """Use case for generating a briefing document.

    This use case coordinates briefing generation through the port interface.

    Example:
        use_case = GenerateBriefingUseCase(briefing_port=adapter)
        result = use_case.execute(
            channel_id="channel-123",
            style="executive",
        )
        print(result.executive_summary)
    """

    def __init__(self, briefing_port: BriefingPort):
        """Initialize the use case with dependencies.

        Args:
            briefing_port: The briefing port implementation
        """
        self.briefing_port = briefing_port

    def execute(
        self,
        channel_id: str,
        style: str = "executive",
        max_sections: int = 5,
    ) -> BriefingResult:
        """Execute briefing generation.

        Args:
            channel_id: The channel (document store) to analyze
            style: 'executive' (concise) or 'detailed' (comprehensive)
            max_sections: Maximum number of sections (1-10)

        Returns:
            BriefingResult with generated briefing or error
        """
        try:
            briefing = self.briefing_port.generate_briefing(
                store_name=channel_id,
                style=style,
                max_sections=max_sections,
            )

            return BriefingResult(
                title=briefing.title,
                executive_summary=briefing.executive_summary,
                sections=briefing.sections,
                key_points=briefing.key_points,
                channel_id=channel_id,
                error=None,
            )

        except Exception as e:
            return BriefingResult(
                title="",
                executive_summary="",
                sections=[],
                key_points=[],
                channel_id=channel_id,
                error=str(e),
            )
