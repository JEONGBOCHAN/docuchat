# -*- coding: utf-8 -*-
"""
Learning Features Use Cases.

These use cases handle study guide and quiz generation.
"""

from dataclasses import dataclass, field

from src.application.ports.learning import (
    StudyGuidePort,
    QuizPort,
    StudySectionDTO,
    KeyConceptDTO,
    QuizQuestionDTO,
)


@dataclass
class StudyGuideResult:
    """Result of study guide generation.

    Attributes:
        title: Study guide title
        overview: Brief overview of the material
        sections: List of study sections
        key_concepts: List of key concepts
        study_tips: List of study tips
        channel_id: The channel/store that was analyzed
        error: Error message if generation failed
    """

    title: str = ""
    overview: str = ""
    sections: list[StudySectionDTO] = field(default_factory=list)
    key_concepts: list[KeyConceptDTO] = field(default_factory=list)
    study_tips: list[str] = field(default_factory=list)
    channel_id: str | None = None
    error: str | None = None


@dataclass
class QuizResult:
    """Result of quiz generation.

    Attributes:
        title: Quiz title
        description: Quiz description
        questions: List of quiz questions
        channel_id: The channel/store that was analyzed
        error: Error message if generation failed
    """

    title: str = ""
    description: str = ""
    questions: list[QuizQuestionDTO] = field(default_factory=list)
    channel_id: str | None = None
    error: str | None = None


class GenerateStudyGuideUseCase:
    """Use case for generating a study guide from documents.

    This use case coordinates study guide generation through the port interface,
    allowing the underlying implementation to be swapped without changing
    the application logic.

    Example:
        use_case = GenerateStudyGuideUseCase(study_guide_port=adapter)
        result = use_case.execute(
            channel_id="channel-123",
            difficulty="medium",
        )
        print(result.title)
        for section in result.sections:
            print(f"- {section.title}")
    """

    def __init__(self, study_guide_port: StudyGuidePort):
        """Initialize the use case with dependencies.

        Args:
            study_guide_port: The study guide port implementation
        """
        self.study_guide_port = study_guide_port

    def execute(
        self,
        channel_id: str,
        include_concepts: bool = True,
        include_summary: bool = True,
        max_sections: int = 5,
        difficulty: str = "medium",
    ) -> StudyGuideResult:
        """Execute study guide generation.

        Args:
            channel_id: The channel (document store) to analyze
            include_concepts: Whether to include key concepts section
            include_summary: Whether to include overview summary
            max_sections: Maximum number of sections (1-10)
            difficulty: Target difficulty level (easy, medium, hard)

        Returns:
            StudyGuideResult with generated guide or error
        """
        try:
            guide = self.study_guide_port.generate_study_guide(
                store_name=channel_id,
                include_concepts=include_concepts,
                include_summary=include_summary,
                max_sections=max_sections,
                difficulty=difficulty,
            )

            return StudyGuideResult(
                title=guide.title,
                overview=guide.overview,
                sections=guide.sections,
                key_concepts=guide.key_concepts,
                study_tips=guide.study_tips,
                channel_id=channel_id,
                error=None,
            )

        except Exception as e:
            return StudyGuideResult(
                title="",
                overview="",
                sections=[],
                key_concepts=[],
                study_tips=[],
                channel_id=channel_id,
                error=str(e),
            )


class GenerateQuizUseCase:
    """Use case for generating a quiz from documents.

    This use case coordinates quiz generation through the port interface.

    Example:
        use_case = GenerateQuizUseCase(quiz_port=adapter)
        result = use_case.execute(
            channel_id="channel-123",
            count=10,
            quiz_type="mixed",
        )
        for q in result.questions:
            print(f"Q: {q.question}")
    """

    def __init__(self, quiz_port: QuizPort):
        """Initialize the use case with dependencies.

        Args:
            quiz_port: The quiz port implementation
        """
        self.quiz_port = quiz_port

    def execute(
        self,
        channel_id: str,
        count: int = 5,
        quiz_type: str = "mixed",
        difficulty: str = "medium",
        include_explanations: bool = True,
    ) -> QuizResult:
        """Execute quiz generation.

        Args:
            channel_id: The channel (document store) to analyze
            count: Number of questions to generate (1-20)
            quiz_type: Type of questions (multiple_choice, short_answer, true_false, mixed)
            difficulty: Target difficulty level (easy, medium, hard)
            include_explanations: Whether to include answer explanations

        Returns:
            QuizResult with generated quiz or error
        """
        try:
            quiz = self.quiz_port.generate_quiz(
                store_name=channel_id,
                count=count,
                quiz_type=quiz_type,
                difficulty=difficulty,
                include_explanations=include_explanations,
            )

            return QuizResult(
                title=quiz.title,
                description=quiz.description,
                questions=quiz.questions,
                channel_id=channel_id,
                error=None,
            )

        except Exception as e:
            return QuizResult(
                title="",
                description="",
                questions=[],
                channel_id=channel_id,
                error=str(e),
            )
