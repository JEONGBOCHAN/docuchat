# -*- coding: utf-8 -*-
"""
Tests for Timeline and Briefing Use Cases.

Tests the Clean Architecture use cases for timeline and briefing generation.
"""

import pytest
from unittest.mock import Mock

from src.application.use_cases.timeline_briefing import (
    GenerateTimelineUseCase,
    GenerateBriefingUseCase,
    TimelineResult,
    BriefingResult,
)
from src.application.ports.timeline import (
    TimelinePort,
    BriefingPort,
    TimelineEventDTO,
    BriefingDTO,
    BriefingSectionDTO,
)


class TestGenerateTimelineUseCase:
    """Tests for GenerateTimelineUseCase."""

    def test_execute_success(self):
        """Test successful timeline generation."""
        mock_port = Mock(spec=TimelinePort)
        mock_port.generate_timeline.return_value = [
            TimelineEventDTO(
                date="2024-01-15",
                title="Project Launch",
                description="The project was launched.",
                source="launch.pdf",
            ),
            TimelineEventDTO(
                date="2024-02-01",
                title="First Milestone",
                description="Completed first milestone.",
                source=None,
            ),
        ]

        use_case = GenerateTimelineUseCase(timeline_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            max_events=10,
        )

        assert result.error is None
        assert result.channel_id == "test-channel"
        assert len(result.events) == 2
        assert result.events[0].date == "2024-01-15"
        assert result.events[0].title == "Project Launch"
        assert result.events[1].source is None

        mock_port.generate_timeline.assert_called_once_with(
            store_name="test-channel",
            max_events=10,
        )

    def test_execute_empty_result(self):
        """Test timeline generation with no events."""
        mock_port = Mock(spec=TimelinePort)
        mock_port.generate_timeline.return_value = []

        use_case = GenerateTimelineUseCase(timeline_port=mock_port)

        result = use_case.execute(channel_id="test-channel")

        assert result.error is None
        assert result.events == []

    def test_execute_error_handling(self):
        """Test error handling during timeline generation."""
        mock_port = Mock(spec=TimelinePort)
        mock_port.generate_timeline.side_effect = Exception("API error")

        use_case = GenerateTimelineUseCase(timeline_port=mock_port)

        result = use_case.execute(channel_id="test-channel")

        assert result.error is not None
        assert "API error" in result.error
        assert result.events == []


class TestGenerateBriefingUseCase:
    """Tests for GenerateBriefingUseCase."""

    def test_execute_success(self):
        """Test successful briefing generation."""
        mock_port = Mock(spec=BriefingPort)
        mock_port.generate_briefing.return_value = BriefingDTO(
            title="Q1 Project Briefing",
            executive_summary="This is the executive summary.",
            sections=[
                BriefingSectionDTO(
                    title="Current Status",
                    content="The project is on track.",
                ),
                BriefingSectionDTO(
                    title="Next Steps",
                    content="We will proceed with phase 2.",
                ),
            ],
            key_points=["On track", "Budget ok", "Timeline good"],
        )

        use_case = GenerateBriefingUseCase(briefing_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            style="executive",
            max_sections=5,
        )

        assert result.error is None
        assert result.channel_id == "test-channel"
        assert result.title == "Q1 Project Briefing"
        assert result.executive_summary == "This is the executive summary."
        assert len(result.sections) == 2
        assert result.sections[0].title == "Current Status"
        assert len(result.key_points) == 3

        mock_port.generate_briefing.assert_called_once_with(
            store_name="test-channel",
            style="executive",
            max_sections=5,
        )

    def test_execute_detailed_style(self):
        """Test briefing generation with detailed style."""
        mock_port = Mock(spec=BriefingPort)
        mock_port.generate_briefing.return_value = BriefingDTO(
            title="Detailed Report",
            executive_summary="Comprehensive overview.",
            sections=[],
            key_points=[],
        )

        use_case = GenerateBriefingUseCase(briefing_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            style="detailed",
        )

        assert result.error is None
        mock_port.generate_briefing.assert_called_once_with(
            store_name="test-channel",
            style="detailed",
            max_sections=5,
        )

    def test_execute_error_handling(self):
        """Test error handling during briefing generation."""
        mock_port = Mock(spec=BriefingPort)
        mock_port.generate_briefing.side_effect = Exception("Generation failed")

        use_case = GenerateBriefingUseCase(briefing_port=mock_port)

        result = use_case.execute(channel_id="test-channel")

        assert result.error is not None
        assert "Generation failed" in result.error
        assert result.title == ""
        assert result.sections == []


class TestTimelineResult:
    """Tests for TimelineResult dataclass."""

    def test_default_values(self):
        """Test TimelineResult with default values."""
        result = TimelineResult()

        assert result.events == []
        assert result.channel_id is None
        assert result.error is None

    def test_with_events(self):
        """Test TimelineResult with events."""
        events = [
            TimelineEventDTO(
                date="2024-01-01",
                title="Event 1",
                description="Description",
            )
        ]
        result = TimelineResult(events=events, channel_id="ch-1")

        assert len(result.events) == 1
        assert result.channel_id == "ch-1"


class TestBriefingResult:
    """Tests for BriefingResult dataclass."""

    def test_default_values(self):
        """Test BriefingResult with default values."""
        result = BriefingResult()

        assert result.title == ""
        assert result.executive_summary == ""
        assert result.sections == []
        assert result.key_points == []
        assert result.channel_id is None
        assert result.error is None
