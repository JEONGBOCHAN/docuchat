# -*- coding: utf-8 -*-
"""
Tests for Podcast Script Generation Use Case.

Tests the Clean Architecture use case for podcast script generation.
"""

import pytest
from unittest.mock import Mock

from src.application.use_cases.podcast import (
    GeneratePodcastScriptUseCase,
    GeneratePodcastScriptRequest,
)
from src.application.ports.podcast import (
    PodcastScriptPort,
    PodcastScriptDTO,
    DialogueLineDTO,
)


class TestGeneratePodcastScriptUseCase:
    """Tests for GeneratePodcastScriptUseCase."""

    def test_execute_success(self):
        """Test successful podcast script generation."""
        mock_port = Mock(spec=PodcastScriptPort)
        mock_port.generate_podcast_script.return_value = PodcastScriptDTO(
            title="AI Deep Dive",
            introduction="Welcome to our podcast about AI!",
            dialogue=[
                DialogueLineDTO(
                    speaker="Host A",
                    text="Let's talk about machine learning.",
                ),
                DialogueLineDTO(
                    speaker="Host B",
                    text="Great topic! ML is fascinating.",
                ),
            ],
            conclusion="Thanks for listening!",
            estimated_duration_seconds=300,
        )

        use_case = GeneratePodcastScriptUseCase(podcast_port=mock_port)

        request = GeneratePodcastScriptRequest(
            store_name="test-channel",
            duration_minutes=5,
            style="conversational",
            language="en",
        )

        result = use_case.execute(request)

        assert isinstance(result, PodcastScriptDTO)
        assert result.title == "AI Deep Dive"
        assert result.introduction == "Welcome to our podcast about AI!"
        assert len(result.dialogue) == 2
        assert result.dialogue[0].speaker == "Host A"
        assert result.dialogue[1].speaker == "Host B"
        assert result.conclusion == "Thanks for listening!"
        assert result.estimated_duration_seconds == 300

        mock_port.generate_podcast_script.assert_called_once_with(
            store_name="test-channel",
            duration_minutes=5,
            style="conversational",
            language="en",
        )

    def test_execute_professional_style(self):
        """Test podcast script generation with professional style."""
        mock_port = Mock(spec=PodcastScriptPort)
        mock_port.generate_podcast_script.return_value = PodcastScriptDTO(
            title="Industry Report",
            introduction="Today's analysis covers...",
            dialogue=[],
            conclusion="In summary...",
            estimated_duration_seconds=600,
        )

        use_case = GeneratePodcastScriptUseCase(podcast_port=mock_port)

        request = GeneratePodcastScriptRequest(
            store_name="test-channel",
            duration_minutes=10,
            style="professional",
            language="ko",
        )

        result = use_case.execute(request)

        assert result.title == "Industry Report"
        mock_port.generate_podcast_script.assert_called_once_with(
            store_name="test-channel",
            duration_minutes=10,
            style="professional",
            language="ko",
        )

    def test_execute_default_values(self):
        """Test podcast script generation with default values."""
        mock_port = Mock(spec=PodcastScriptPort)
        mock_port.generate_podcast_script.return_value = PodcastScriptDTO(
            title="Episode",
            introduction="",
            dialogue=[],
            conclusion="",
            estimated_duration_seconds=300,
        )

        use_case = GeneratePodcastScriptUseCase(podcast_port=mock_port)

        request = GeneratePodcastScriptRequest(store_name="test-channel")

        result = use_case.execute(request)

        mock_port.generate_podcast_script.assert_called_once_with(
            store_name="test-channel",
            duration_minutes=5,
            style="conversational",
            language="ko",
        )

    def test_execute_error_propagation(self):
        """Test that errors from port are propagated."""
        mock_port = Mock(spec=PodcastScriptPort)
        mock_port.generate_podcast_script.side_effect = Exception("API error")

        use_case = GeneratePodcastScriptUseCase(podcast_port=mock_port)

        request = GeneratePodcastScriptRequest(store_name="test-channel")

        with pytest.raises(Exception) as exc_info:
            use_case.execute(request)

        assert "API error" in str(exc_info.value)


class TestGeneratePodcastScriptRequest:
    """Tests for GeneratePodcastScriptRequest dataclass."""

    def test_default_values(self):
        """Test GeneratePodcastScriptRequest with default values."""
        request = GeneratePodcastScriptRequest(store_name="test")

        assert request.store_name == "test"
        assert request.duration_minutes == 5
        assert request.style == "conversational"
        assert request.language == "ko"

    def test_custom_values(self):
        """Test GeneratePodcastScriptRequest with custom values."""
        request = GeneratePodcastScriptRequest(
            store_name="channel-123",
            duration_minutes=10,
            style="professional",
            language="en",
        )

        assert request.store_name == "channel-123"
        assert request.duration_minutes == 10
        assert request.style == "professional"
        assert request.language == "en"
