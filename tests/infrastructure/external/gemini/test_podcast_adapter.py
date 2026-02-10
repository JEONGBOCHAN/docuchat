# -*- coding: utf-8 -*-
"""
Tests for GeminiPodcastAdapter.

Tests the Gemini adapter implementation for podcast script generation.
"""

import pytest
from unittest.mock import Mock

from src.infrastructure.external.gemini.podcast import GeminiPodcastAdapter
from src.shared.kernel.contracts.ports.podcast import (
    PodcastScriptDTO,
    DialogueLineDTO,
)


class TestGeminiPodcastAdapter:
    """Tests for GeminiPodcastAdapter."""

    def _create_mock_response(self, text: str):
        """Create a mock Gemini response."""
        mock_response = Mock()
        mock_response.text = text
        return mock_response

    def _create_mock_client(self, response_text: str):
        """Create a mock Gemini client."""
        mock_client = Mock()
        mock_response = self._create_mock_response(response_text)
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_generate_podcast_script_success(self):
        """Test successful podcast script generation."""
        json_response = '''{
            "title": "AI Deep Dive",
            "introduction": "Welcome to our podcast about AI!",
            "dialogue": [
                {"speaker": "Host A", "text": "Let's talk about machine learning."},
                {"speaker": "Host B", "text": "Great topic! ML is fascinating."}
            ],
            "conclusion": "Thanks for listening!",
            "estimated_duration_seconds": 300
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiPodcastAdapter(client=mock_client)

        result = adapter.generate_podcast_script(
            "test-store",
            duration_minutes=5,
            style="conversational",
            language="en",
        )

        assert isinstance(result, PodcastScriptDTO)
        assert result.title == "AI Deep Dive"
        assert result.introduction == "Welcome to our podcast about AI!"
        assert len(result.dialogue) == 2
        assert isinstance(result.dialogue[0], DialogueLineDTO)
        assert result.dialogue[0].speaker == "Host A"
        assert result.dialogue[0].text == "Let's talk about machine learning."
        assert result.dialogue[1].speaker == "Host B"
        assert result.conclusion == "Thanks for listening!"
        assert result.estimated_duration_seconds == 300

        mock_client.models.generate_content.assert_called_once()

    def test_generate_podcast_script_professional_style(self):
        """Test podcast script generation with professional style."""
        json_response = '''{
            "title": "Industry Report",
            "introduction": "Today's analysis covers...",
            "dialogue": [
                {"speaker": "Host A", "text": "Our first topic is..."}
            ],
            "conclusion": "In summary...",
            "estimated_duration_seconds": 600
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiPodcastAdapter(client=mock_client)

        result = adapter.generate_podcast_script(
            "test-store",
            duration_minutes=10,
            style="professional",
            language="ko",
        )

        assert result.title == "Industry Report"
        assert result.estimated_duration_seconds == 600

    def test_generate_podcast_script_empty_dialogue(self):
        """Test podcast script generation with empty dialogue."""
        json_response = '''{
            "title": "Empty Episode",
            "introduction": "Intro",
            "dialogue": [],
            "conclusion": "Outro",
            "estimated_duration_seconds": 60
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiPodcastAdapter(client=mock_client)

        result = adapter.generate_podcast_script("test-store")

        assert result.dialogue == []

    def test_generate_podcast_script_default_values(self):
        """Test podcast script generation with missing fields uses defaults."""
        json_response = '''{
            "dialogue": [
                {"text": "Hello"}
            ]
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiPodcastAdapter(client=mock_client)

        result = adapter.generate_podcast_script(
            "test-store",
            duration_minutes=5,
        )

        assert result.title == "Podcast Episode"
        assert result.introduction == ""
        assert result.conclusion == ""
        assert result.estimated_duration_seconds == 300
        assert result.dialogue[0].speaker == "Host A"

    def test_generate_podcast_script_invalid_json_returns_defaults(self):
        """Test podcast script generation with invalid JSON response returns defaults."""
        mock_client = self._create_mock_client("Not valid JSON")

        adapter = GeminiPodcastAdapter(client=mock_client)

        result = adapter.generate_podcast_script("test-store", duration_minutes=5)

        assert result.title == "Podcast Episode"
        assert result.introduction == ""
        assert result.dialogue == []
        assert result.conclusion == ""
        assert result.estimated_duration_seconds == 300

    def test_generate_podcast_script_service_exception(self):
        """Test podcast script generation when client raises exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        adapter = GeminiPodcastAdapter(client=mock_client)

        with pytest.raises(Exception) as exc_info:
            adapter.generate_podcast_script("test-store")

        assert "API error" in str(exc_info.value)

    def test_generate_podcast_script_null_response_text(self):
        """Test podcast script generation when response text is None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiPodcastAdapter(client=mock_client)

        result = adapter.generate_podcast_script("test-store", duration_minutes=5)

        assert result.title == "Podcast Episode"
        assert result.dialogue == []
        assert result.estimated_duration_seconds == 300
