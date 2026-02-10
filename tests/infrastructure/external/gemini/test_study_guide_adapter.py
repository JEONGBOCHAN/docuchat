# -*- coding: utf-8 -*-
"""
Tests for GeminiStudyGuideAdapter.

Tests the Gemini adapter implementation for study guide generation.
"""

import pytest
from unittest.mock import Mock

from src.infrastructure.external.gemini.study_guide import GeminiStudyGuideAdapter
from src.shared.kernel.contracts.ports.learning import (
    StudyGuideDTO,
    StudySectionDTO,
    KeyConceptDTO,
)


class TestGeminiStudyGuideAdapter:
    """Tests for GeminiStudyGuideAdapter."""

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

    def test_generate_study_guide_success(self):
        """Test successful study guide generation."""
        json_response = '''{
            "title": "Machine Learning Study Guide",
            "overview": "This guide covers ML fundamentals.",
            "sections": [
                {
                    "title": "Introduction",
                    "content": "ML is a subset of AI.",
                    "key_points": ["Data driven", "Pattern recognition"]
                }
            ],
            "key_concepts": [
                {
                    "term": "Neural Network",
                    "definition": "Computing system inspired by biological neurons.",
                    "importance": "Foundation of deep learning"
                }
            ],
            "study_tips": ["Start with basics", "Practice coding"]
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiStudyGuideAdapter(client=mock_client)

        result = adapter.generate_study_guide(
            "test-store",
            include_concepts=True,
            include_summary=True,
            max_sections=5,
            difficulty="medium",
        )

        assert isinstance(result, StudyGuideDTO)
        assert result.title == "Machine Learning Study Guide"
        assert result.overview == "This guide covers ML fundamentals."
        assert len(result.sections) == 1
        assert isinstance(result.sections[0], StudySectionDTO)
        assert result.sections[0].title == "Introduction"
        assert len(result.key_concepts) == 1
        assert isinstance(result.key_concepts[0], KeyConceptDTO)
        assert result.key_concepts[0].term == "Neural Network"
        assert len(result.study_tips) == 2

        mock_client.models.generate_content.assert_called_once()

    def test_generate_study_guide_without_concepts(self):
        """Test study guide generation without concepts."""
        json_response = '''{
            "title": "Guide",
            "overview": "Overview",
            "sections": [],
            "key_concepts": [],
            "study_tips": []
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiStudyGuideAdapter(client=mock_client)

        result = adapter.generate_study_guide(
            "test-store",
            include_concepts=False,
        )

        assert result.key_concepts == []

    def test_generate_study_guide_missing_importance(self):
        """Test study guide generation with missing optional fields."""
        json_response = '''{
            "title": "Guide",
            "overview": "Overview",
            "sections": [],
            "key_concepts": [
                {
                    "term": "Concept",
                    "definition": "Definition"
                }
            ],
            "study_tips": []
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiStudyGuideAdapter(client=mock_client)

        result = adapter.generate_study_guide("test-store")

        assert result.key_concepts[0].importance is None

    def test_generate_study_guide_invalid_json_returns_defaults(self):
        """Test study guide generation with invalid JSON response returns defaults."""
        mock_client = self._create_mock_client("Not valid JSON")

        adapter = GeminiStudyGuideAdapter(client=mock_client)

        result = adapter.generate_study_guide("test-store")

        assert result.title == "Study Guide"
        assert result.overview == ""
        assert result.sections == []
        assert result.key_concepts == []
        assert result.study_tips == []

    def test_generate_study_guide_service_exception(self):
        """Test study guide generation when client raises exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        adapter = GeminiStudyGuideAdapter(client=mock_client)

        with pytest.raises(Exception) as exc_info:
            adapter.generate_study_guide("test-store")

        assert "API error" in str(exc_info.value)

    def test_generate_study_guide_null_response_text(self):
        """Test study guide generation when response text is None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiStudyGuideAdapter(client=mock_client)

        result = adapter.generate_study_guide("test-store")

        assert result.title == "Study Guide"
        assert result.sections == []
