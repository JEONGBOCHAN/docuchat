# -*- coding: utf-8 -*-
"""Study guide and quiz models."""

from datetime import datetime, UTC
from enum import Enum
from pydantic import BaseModel, Field


class QuizType(str, Enum):
    """Quiz question types."""

    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    TRUE_FALSE = "true_false"
    MIXED = "mixed"


class DifficultyLevel(str, Enum):
    """Difficulty levels for study materials."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# Study Guide Models


class KeyConcept(BaseModel):
    """A key concept from the documents."""

    term: str = Field(..., description="The concept or term name")
    definition: str = Field(..., description="Clear definition or explanation")
    importance: str | None = Field(None, description="Why this concept is important")


class StudySection(BaseModel):
    """A section in the study guide."""

    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content/explanation")
    key_points: list[str] = Field(
        default_factory=list, description="Key points to remember"
    )


class StudyGuideGenerateRequest(BaseModel):
    """Request model for generating a study guide."""

    include_concepts: bool = Field(
        default=True, description="Include key concepts section"
    )
    include_summary: bool = Field(default=True, description="Include summary section")
    max_sections: int = Field(
        default=5, ge=1, le=10, description="Maximum number of sections"
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM, description="Target difficulty level"
    )


class StudyGuideResponse(BaseModel):
    """Response model for study guide generation."""

    channel_id: str
    title: str
    overview: str
    sections: list[StudySection]
    key_concepts: list[KeyConcept]
    study_tips: list[str]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Quiz Models


class QuizChoice(BaseModel):
    """A choice for multiple choice questions."""

    label: str = Field(..., description="Choice label (A, B, C, D)")
    text: str = Field(..., description="Choice text")
    is_correct: bool = Field(default=False, description="Whether this is correct")


class QuizQuestion(BaseModel):
    """A quiz question."""

    question: str = Field(..., description="The question text")
    question_type: QuizType = Field(..., description="Type of question")
    choices: list[QuizChoice] | None = Field(
        None, description="Choices for multiple choice"
    )
    correct_answer: str = Field(..., description="The correct answer")
    explanation: str = Field(..., description="Explanation of the answer")
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM, description="Question difficulty"
    )


class QuizGenerateRequest(BaseModel):
    """Request model for generating a quiz."""

    count: int = Field(
        default=5, ge=1, le=20, description="Number of questions to generate"
    )
    quiz_type: QuizType = Field(
        default=QuizType.MIXED, description="Type of questions"
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM, description="Target difficulty level"
    )
    include_explanations: bool = Field(
        default=True, description="Include answer explanations"
    )


class QuizResponse(BaseModel):
    """Response model for quiz generation."""

    channel_id: str
    title: str
    description: str
    questions: list[QuizQuestion]
    total_questions: int
    quiz_type: QuizType
    difficulty: DifficultyLevel
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QuizAnswerSubmission(BaseModel):
    """User's answer submission for a quiz question."""

    question_index: int = Field(..., ge=0, description="Index of the question")
    user_answer: str = Field(..., description="User's answer")


class QuizResult(BaseModel):
    """Result of a quiz attempt."""

    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str


class QuizEvaluationResponse(BaseModel):
    """Response for quiz evaluation."""

    channel_id: str
    total_questions: int
    correct_count: int
    score_percentage: float
    results: list[QuizResult]
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
