# -*- coding: utf-8 -*-
"""
Tests for Learning Features Use Cases.

Tests the Clean Architecture use cases for study guide and quiz generation.
"""

import pytest
from unittest.mock import Mock

from src.application.use_cases.learning import (
    GenerateStudyGuideUseCase,
    GenerateQuizUseCase,
    StudyGuideResult,
    QuizResult,
)
from src.application.ports.learning import (
    StudyGuidePort,
    QuizPort,
    StudyGuideDTO,
    StudySectionDTO,
    KeyConceptDTO,
    QuizDTO,
    QuizQuestionDTO,
    QuizChoiceDTO,
)


class TestGenerateStudyGuideUseCase:
    """Tests for GenerateStudyGuideUseCase."""

    def test_execute_success(self):
        """Test successful study guide generation."""
        mock_port = Mock(spec=StudyGuidePort)
        mock_port.generate_study_guide.return_value = StudyGuideDTO(
            title="Machine Learning Study Guide",
            overview="This guide covers ML fundamentals.",
            sections=[
                StudySectionDTO(
                    title="Introduction",
                    content="ML is a subset of AI.",
                    key_points=["Data driven", "Pattern recognition"],
                ),
            ],
            key_concepts=[
                KeyConceptDTO(
                    term="Neural Network",
                    definition="A computing system inspired by biological neurons.",
                    importance="Foundation of deep learning",
                ),
            ],
            study_tips=["Start with basics", "Practice coding"],
        )

        use_case = GenerateStudyGuideUseCase(study_guide_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            include_concepts=True,
            include_summary=True,
            max_sections=5,
            difficulty="medium",
        )

        assert result.error is None
        assert result.channel_id == "test-channel"
        assert result.title == "Machine Learning Study Guide"
        assert len(result.sections) == 1
        assert len(result.key_concepts) == 1
        assert len(result.study_tips) == 2

        mock_port.generate_study_guide.assert_called_once_with(
            store_name="test-channel",
            include_concepts=True,
            include_summary=True,
            max_sections=5,
            difficulty="medium",
        )

    def test_execute_without_concepts(self):
        """Test study guide generation without concepts."""
        mock_port = Mock(spec=StudyGuidePort)
        mock_port.generate_study_guide.return_value = StudyGuideDTO(
            title="Guide",
            overview="Overview",
            sections=[],
            key_concepts=[],
            study_tips=[],
        )

        use_case = GenerateStudyGuideUseCase(study_guide_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            include_concepts=False,
        )

        assert result.error is None
        mock_port.generate_study_guide.assert_called_once()

    def test_execute_error_handling(self):
        """Test error handling during study guide generation."""
        mock_port = Mock(spec=StudyGuidePort)
        mock_port.generate_study_guide.side_effect = Exception("API error")

        use_case = GenerateStudyGuideUseCase(study_guide_port=mock_port)

        result = use_case.execute(channel_id="test-channel")

        assert result.error is not None
        assert "API error" in result.error
        assert result.title == ""
        assert result.sections == []


class TestGenerateQuizUseCase:
    """Tests for GenerateQuizUseCase."""

    def test_execute_success(self):
        """Test successful quiz generation."""
        mock_port = Mock(spec=QuizPort)
        mock_port.generate_quiz.return_value = QuizDTO(
            title="ML Fundamentals Quiz",
            description="Test your knowledge of machine learning.",
            questions=[
                QuizQuestionDTO(
                    question="What is supervised learning?",
                    question_type="multiple_choice",
                    correct_answer="A. Learning with labeled data",
                    choices=[
                        QuizChoiceDTO(label="A", text="Learning with labeled data", is_correct=True),
                        QuizChoiceDTO(label="B", text="Learning without labels", is_correct=False),
                    ],
                    explanation="Supervised learning uses labeled data.",
                    difficulty="medium",
                ),
                QuizQuestionDTO(
                    question="Neural networks are inspired by biological neurons.",
                    question_type="true_false",
                    correct_answer="True",
                    choices=None,
                    explanation="They mimic biological neural structures.",
                    difficulty="easy",
                ),
            ],
        )

        use_case = GenerateQuizUseCase(quiz_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            count=5,
            quiz_type="mixed",
            difficulty="medium",
            include_explanations=True,
        )

        assert result.error is None
        assert result.channel_id == "test-channel"
        assert result.title == "ML Fundamentals Quiz"
        assert len(result.questions) == 2
        assert result.questions[0].question_type == "multiple_choice"
        assert result.questions[1].question_type == "true_false"

        mock_port.generate_quiz.assert_called_once_with(
            store_name="test-channel",
            count=5,
            quiz_type="mixed",
            difficulty="medium",
            include_explanations=True,
        )

    def test_execute_multiple_choice_only(self):
        """Test quiz generation with only multiple choice questions."""
        mock_port = Mock(spec=QuizPort)
        mock_port.generate_quiz.return_value = QuizDTO(
            title="Quiz",
            description="Description",
            questions=[],
        )

        use_case = GenerateQuizUseCase(quiz_port=mock_port)

        result = use_case.execute(
            channel_id="test-channel",
            quiz_type="multiple_choice",
        )

        assert result.error is None
        mock_port.generate_quiz.assert_called_once()
        call_args = mock_port.generate_quiz.call_args
        assert call_args.kwargs["quiz_type"] == "multiple_choice"

    def test_execute_error_handling(self):
        """Test error handling during quiz generation."""
        mock_port = Mock(spec=QuizPort)
        mock_port.generate_quiz.side_effect = Exception("Generation failed")

        use_case = GenerateQuizUseCase(quiz_port=mock_port)

        result = use_case.execute(channel_id="test-channel")

        assert result.error is not None
        assert "Generation failed" in result.error
        assert result.title == ""
        assert result.questions == []


class TestStudyGuideResult:
    """Tests for StudyGuideResult dataclass."""

    def test_default_values(self):
        """Test StudyGuideResult with default values."""
        result = StudyGuideResult()

        assert result.title == ""
        assert result.overview == ""
        assert result.sections == []
        assert result.key_concepts == []
        assert result.study_tips == []
        assert result.channel_id is None
        assert result.error is None


class TestQuizResult:
    """Tests for QuizResult dataclass."""

    def test_default_values(self):
        """Test QuizResult with default values."""
        result = QuizResult()

        assert result.title == ""
        assert result.description == ""
        assert result.questions == []
        assert result.channel_id is None
        assert result.error is None
