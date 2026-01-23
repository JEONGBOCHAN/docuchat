# -*- coding: utf-8 -*-
"""
Tests for GeminiQuizAdapter.

Tests the Gemini adapter implementation for quiz generation.
"""

import pytest
from unittest.mock import Mock

from src.infrastructure.external.gemini.quiz import GeminiQuizAdapter
from src.application.ports.learning import QuizDTO, QuizQuestionDTO, QuizChoiceDTO


class TestGeminiQuizAdapter:
    """Tests for GeminiQuizAdapter."""

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

    def test_generate_quiz_success(self):
        """Test successful quiz generation."""
        json_response = '''{
            "title": "ML Fundamentals Quiz",
            "description": "Test your machine learning knowledge.",
            "questions": [
                {
                    "question": "What is supervised learning?",
                    "question_type": "multiple_choice",
                    "correct_answer": "A. Learning with labeled data",
                    "choices": [
                        {"label": "A", "text": "Learning with labeled data", "is_correct": true},
                        {"label": "B", "text": "Learning without labels", "is_correct": false}
                    ],
                    "explanation": "Supervised learning uses labeled training data.",
                    "difficulty": "medium"
                },
                {
                    "question": "Neural networks are inspired by biological neurons.",
                    "question_type": "true_false",
                    "correct_answer": "True",
                    "choices": null,
                    "explanation": "They mimic biological neural structures.",
                    "difficulty": "easy"
                }
            ]
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiQuizAdapter(client=mock_client)

        result = adapter.generate_quiz(
            "test-store",
            count=5,
            quiz_type="mixed",
            difficulty="medium",
            include_explanations=True,
        )

        assert isinstance(result, QuizDTO)
        assert result.title == "ML Fundamentals Quiz"
        assert result.description == "Test your machine learning knowledge."
        assert len(result.questions) == 2

        # Check first question (multiple choice)
        q1 = result.questions[0]
        assert isinstance(q1, QuizQuestionDTO)
        assert q1.question_type == "multiple_choice"
        assert q1.choices is not None
        assert len(q1.choices) == 2
        assert all(isinstance(c, QuizChoiceDTO) for c in q1.choices)
        assert q1.choices[0].is_correct is True

        # Check second question (true/false)
        q2 = result.questions[1]
        assert q2.question_type == "true_false"
        assert q2.choices is None
        assert q2.correct_answer == "True"

        mock_client.models.generate_content.assert_called_once()

    def test_generate_quiz_empty(self):
        """Test quiz generation with no questions."""
        json_response = '''{
            "title": "Quiz",
            "description": "Description",
            "questions": []
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiQuizAdapter(client=mock_client)

        result = adapter.generate_quiz("test-store")

        assert result.questions == []

    def test_generate_quiz_missing_explanation(self):
        """Test quiz generation with missing explanation."""
        json_response = '''{
            "title": "Quiz",
            "description": "Description",
            "questions": [
                {
                    "question": "Test question?",
                    "question_type": "short_answer",
                    "correct_answer": "Answer"
                }
            ]
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiQuizAdapter(client=mock_client)

        result = adapter.generate_quiz("test-store", include_explanations=False)

        assert result.questions[0].explanation is None

    def test_generate_quiz_multiple_choice_only(self):
        """Test quiz generation with only multiple choice questions."""
        json_response = '''{
            "title": "MC Quiz",
            "description": "Multiple choice only",
            "questions": [
                {
                    "question": "Q1?",
                    "question_type": "multiple_choice",
                    "correct_answer": "A",
                    "choices": [
                        {"label": "A", "text": "Answer A", "is_correct": true},
                        {"label": "B", "text": "Answer B", "is_correct": false},
                        {"label": "C", "text": "Answer C", "is_correct": false},
                        {"label": "D", "text": "Answer D", "is_correct": false}
                    ],
                    "difficulty": "hard"
                }
            ]
        }'''
        mock_client = self._create_mock_client(json_response)

        adapter = GeminiQuizAdapter(client=mock_client)

        result = adapter.generate_quiz("test-store", quiz_type="multiple_choice")

        assert len(result.questions[0].choices) == 4

    def test_generate_quiz_invalid_json_returns_defaults(self):
        """Test quiz generation with invalid JSON response returns defaults."""
        mock_client = self._create_mock_client("Not valid JSON")

        adapter = GeminiQuizAdapter(client=mock_client)

        result = adapter.generate_quiz("test-store")

        assert result.title == "Quiz"
        assert result.description == ""
        assert result.questions == []

    def test_generate_quiz_service_exception(self):
        """Test quiz generation when client raises exception."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        adapter = GeminiQuizAdapter(client=mock_client)

        with pytest.raises(Exception) as exc_info:
            adapter.generate_quiz("test-store")

        assert "API error" in str(exc_info.value)

    def test_generate_quiz_null_response_text(self):
        """Test quiz generation when response text is None."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        adapter = GeminiQuizAdapter(client=mock_client)

        result = adapter.generate_quiz("test-store")

        assert result.title == "Quiz"
        assert result.questions == []
