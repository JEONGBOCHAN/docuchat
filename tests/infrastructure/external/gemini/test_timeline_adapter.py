# -*- coding: utf-8 -*-
"""
Tests for GeminiTimelineAdapter.

Tests the Gemini adapter implementation for timeline generation.
"""

import pytest
from unittest.mock import Mock

from src.infrastructure.external.gemini.timeline import GeminiTimelineAdapter
from src.shared.kernel.contracts.ports.timeline import TimelineEventDTO


class TestGeminiTimelineAdapter:
    """Tests for GeminiTimelineAdapter."""

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

    def test_generate_timeline_success(self):
        """Test successful timeline generation."""
        json_response = '''[
            {
                "date": "2024-01-15",
                "title": "Project Kickoff",
                "description": "Initial project meeting held.",
                "source": "project_overview.pdf"
            },
            {
                "date": "2024-02-01",
                "title": "Phase 1 Complete",
                "description": "First milestone achieved."
            }
        ]'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiTimelineAdapter(client=mock_client)

        result = adapter.generate_timeline("test-store", max_events=10)

        assert len(result) == 2
        assert all(isinstance(e, TimelineEventDTO) for e in result)
        assert result[0].date == "2024-01-15"
        assert result[0].title == "Project Kickoff"
        assert result[0].description == "Initial project meeting held."
        assert result[0].source == "project_overview.pdf"
        assert result[1].date == "2024-02-01"
        assert result[1].source is None

        mock_client.models.generate_content.assert_called_once()

    def test_generate_timeline_empty(self):
        """Test timeline generation with no events."""
        mock_client = self._create_mock_client("[]")

        adapter = GeminiTimelineAdapter(client=mock_client)

        result = adapter.generate_timeline("test-store")

        assert result == []

    def test_generate_timeline_missing_fields(self):
        """Test timeline generation with missing fields."""
        json_response = '''[
            {
                "date": "2024-01-15"
            },
            {
                "title": "Event"
            }
        ]'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiTimelineAdapter(client=mock_client)

        result = adapter.generate_timeline("test-store")

        assert len(result) == 2
        assert result[0].date == "2024-01-15"
        assert result[0].title == ""
        assert result[1].date == "Unknown"
        assert result[1].title == "Event"

    def test_generate_timeline_invalid_json(self):
        """Test timeline generation with invalid JSON response."""
        mock_client = self._create_mock_client("Not valid JSON")

        adapter = GeminiTimelineAdapter(client=mock_client)

        result = adapter.generate_timeline("test-store")

        assert result == []

    def test_generate_timeline_json_with_extra_text(self):
        """Test timeline generation when JSON is embedded in extra text."""
        json_response = '''Here are the timeline events:
        [{"date": "2024-01-15", "title": "Event 1", "description": "Desc"}]
        That's all!'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiTimelineAdapter(client=mock_client)

        result = adapter.generate_timeline("test-store")

        assert len(result) == 1
        assert result[0].title == "Event 1"

    def test_generate_timeline_service_exception(self):
        """Test timeline generation when client raises exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        adapter = GeminiTimelineAdapter(client=mock_client)

        with pytest.raises(Exception) as exc_info:
            adapter.generate_timeline("test-store")

        assert "API error" in str(exc_info.value)

    def test_generate_timeline_null_response_text(self):
        """Test timeline generation when response text is None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiTimelineAdapter(client=mock_client)

        result = adapter.generate_timeline("test-store")

        assert result == []
