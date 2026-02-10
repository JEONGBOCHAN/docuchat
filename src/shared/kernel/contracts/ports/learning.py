# -*- coding: utf-8 -*-
"""
Learning Features Port.

Defines the interface for study guide and quiz generation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class KeyConceptDTO:
    """A key concept with definition."""

    term: str
    definition: str
    importance: str | None = None


@dataclass
class StudySectionDTO:
    """A section in a study guide."""

    title: str
    content: str
    key_points: list[str] = field(default_factory=list)


@dataclass
class StudyGuideDTO:
    """Result of study guide generation."""

    title: str
    overview: str
    sections: list[StudySectionDTO] = field(default_factory=list)
    key_concepts: list[KeyConceptDTO] = field(default_factory=list)
    study_tips: list[str] = field(default_factory=list)


@dataclass
class QuizChoiceDTO:
    """A choice in a multiple choice question."""

    label: str
    text: str
    is_correct: bool


@dataclass
class QuizQuestionDTO:
    """A quiz question."""

    question: str
    question_type: str  # "multiple_choice", "short_answer", "true_false"
    correct_answer: str
    choices: list[QuizChoiceDTO] | None = None
    explanation: str | None = None
    difficulty: str = "medium"


@dataclass
class QuizDTO:
    """Result of quiz generation."""

    title: str
    description: str
    questions: list[QuizQuestionDTO] = field(default_factory=list)


class StudyGuidePort(ABC):
    """Abstract interface for study guide generation.

    Implementations create structured study guides from documents.

    Example:
        adapter = GeminiStudyGuideAdapter(gemini_service)
        guide = adapter.generate_study_guide(
            "channel-123",
            difficulty="medium",
            max_sections=5,
        )
    """

    @abstractmethod
    def generate_study_guide(
        self,
        store_name: str,
        include_concepts: bool = True,
        include_summary: bool = True,
        max_sections: int = 5,
        difficulty: str = "medium",
    ) -> StudyGuideDTO:
        """Generate a study guide from documents.

        Args:
            store_name: The document store to analyze
            include_concepts: Whether to include key concepts section
            include_summary: Whether to include overview summary
            max_sections: Maximum number of sections (1-10)
            difficulty: Target difficulty level (easy, medium, hard)

        Returns:
            StudyGuideDTO with the generated study guide
        """
        pass


class QuizPort(ABC):
    """Abstract interface for quiz generation.

    Implementations create quizzes from document content.

    Example:
        adapter = GeminiQuizAdapter(gemini_service)
        quiz = adapter.generate_quiz(
            "channel-123",
            count=10,
            quiz_type="mixed",
        )
    """

    @abstractmethod
    def generate_quiz(
        self,
        store_name: str,
        count: int = 5,
        quiz_type: str = "mixed",
        difficulty: str = "medium",
        include_explanations: bool = True,
    ) -> QuizDTO:
        """Generate a quiz from documents.

        Args:
            store_name: The document store to analyze
            count: Number of questions to generate (1-20)
            quiz_type: Type of questions (multiple_choice, short_answer, true_false, mixed)
            difficulty: Target difficulty level (easy, medium, hard)
            include_explanations: Whether to include answer explanations

        Returns:
            QuizDTO with the generated quiz
        """
        pass
