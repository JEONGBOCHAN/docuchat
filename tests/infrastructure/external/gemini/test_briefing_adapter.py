# -*- coding: utf-8 -*-
"""
Tests for GeminiBriefingAdapter.

Tests the Gemini adapter implementation for briefing generation.
"""

import pytest
from unittest.mock import Mock

from src.infrastructure.external.gemini.briefing import GeminiBriefingAdapter
from src.shared.kernel.contracts.ports.timeline import BriefingDTO, BriefingSectionDTO


class TestGeminiBriefingAdapter:
    """Tests for GeminiBriefingAdapter."""

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

    def test_generate_briefing_success(self):
        """Test successful briefing generation."""
        json_response = '''{
            "title": "Q1 2024 Status Briefing",
            "executive_summary": "The project is on track for delivery.",
            "sections": [
                {"title": "Current Status", "content": "All milestones met."},
                {"title": "Risks", "content": "Minor budget concerns."}
            ],
            "key_points": ["On schedule", "Under budget", "Team aligned"]
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiBriefingAdapter(client=mock_client)

        result = adapter.generate_briefing(
            "test-store",
            style="executive",
            max_sections=5,
        )

        assert isinstance(result, BriefingDTO)
        assert result.title == "Q1 2024 Status Briefing"
        assert result.executive_summary == "The project is on track for delivery."
        assert len(result.sections) == 2
        assert all(isinstance(s, BriefingSectionDTO) for s in result.sections)
        assert result.sections[0].title == "Current Status"
        assert len(result.key_points) == 3

        mock_client.models.generate_content.assert_called_once()

    def test_generate_briefing_detailed_style(self):
        """Test briefing generation with detailed style."""
        json_response = '''{
            "title": "Detailed Report",
            "executive_summary": "Comprehensive analysis.",
            "sections": [],
            "key_points": []
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiBriefingAdapter(client=mock_client)

        result = adapter.generate_briefing("test-store", style="detailed")

        assert result.title == "Detailed Report"

    def test_generate_briefing_empty_sections(self):
        """Test briefing generation with empty sections."""
        json_response = '''{
            "title": "Brief",
            "executive_summary": "Summary",
            "sections": [],
            "key_points": []
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiBriefingAdapter(client=mock_client)

        result = adapter.generate_briefing("test-store")

        assert result.sections == []
        assert result.key_points == []

    def test_generate_briefing_invalid_json_returns_defaults(self):
        """Test briefing generation with invalid JSON response returns defaults."""
        mock_client = self._create_mock_client("Not valid JSON")

        adapter = GeminiBriefingAdapter(client=mock_client)

        result = adapter.generate_briefing("test-store")

        assert result.title == "Briefing"
        assert result.executive_summary == ""
        assert result.sections == []
        assert result.key_points == []

    def test_generate_briefing_service_exception(self):
        """Test briefing generation when client raises exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        adapter = GeminiBriefingAdapter(client=mock_client)

        with pytest.raises(Exception) as exc_info:
            adapter.generate_briefing("test-store")

        assert "API error" in str(exc_info.value)

    def test_generate_briefing_null_response_text(self):
        """Test briefing generation when response text is None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiBriefingAdapter(client=mock_client)

        result = adapter.generate_briefing("test-store")

        assert result.title == "Briefing"
        assert result.sections == []
