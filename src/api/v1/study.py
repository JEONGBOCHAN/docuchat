# -*- coding: utf-8 -*-
"""Study guide and quiz generation API endpoints."""

from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_db
from src.core.rate_limiter import RateLimits
from src.models.study import (
    DifficultyLevel,
    KeyConcept,
    QuizChoice,
    QuizGenerateRequest,
    QuizQuestion,
    QuizResponse,
    QuizType,
    StudyGuideGenerateRequest,
    StudyGuideResponse,
    StudySection,
)
from src.application.ports.channel import ChannelPort
from src.application.ports.document import DocumentPort
from src.application.ports.persistence import ChannelRepositoryPort
from src.infrastructure.di.container import (
    create_channel_port,
    create_document_port,
    create_generate_study_guide_use_case,
    create_generate_quiz_use_case,
    create_channel_repository_port,
)

router = APIRouter(prefix="/channels", tags=["study"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_document_port() -> DocumentPort:
    """Get document port instance."""
    return create_document_port()


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


@router.post(
    "/{channel_id:path}/generate-study-guide",
    response_model=StudyGuideResponse,
    summary="Generate a study guide",
    description="Generate a comprehensive study guide based on documents in the channel",
)
@limiter.limit(RateLimits.CHAT)
async def generate_study_guide(
    request: Request,
    channel_id: str,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    body: StudyGuideGenerateRequest | None = None,
):
    """Generate a study guide from channel documents.

    Creates a structured study guide with:
    - Overview of the material
    - Study sections with key points
    - Key concepts and definitions
    - Study tips

    Args:
        channel_id: The channel (File Search Store) ID
        body: Optional configuration for the study guide

    Returns:
        StudyGuideResponse with the generated study guide
    """
    if body is None:
        body = StudyGuideGenerateRequest()

    # Verify channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check if channel has documents
    files = document_port.list_documents(channel_id)
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Channel has no documents. Upload documents first.",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Generate study guide using Clean Architecture use case
    use_case = create_generate_study_guide_use_case()
    result = use_case.execute(
        channel_id=channel_id,
        include_concepts=body.include_concepts,
        include_summary=body.include_summary,
        max_sections=body.max_sections,
        difficulty=body.difficulty.value,
    )

    if result.error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate study guide: {result.error}",
        )

    # Convert to response model
    sections = [
        StudySection(
            title=s.title,
            content=s.content,
            key_points=s.key_points,
        )
        for s in result.sections
    ]

    key_concepts = [
        KeyConcept(
            term=c.term,
            definition=c.definition,
            importance=c.importance,
        )
        for c in result.key_concepts
    ]

    return StudyGuideResponse(
        channel_id=channel_id,
        title=result.title,
        overview=result.overview,
        sections=sections,
        key_concepts=key_concepts,
        study_tips=result.study_tips,
        generated_at=datetime.now(UTC),
    )


@router.post(
    "/{channel_id:path}/generate-quiz",
    response_model=QuizResponse,
    summary="Generate a quiz",
    description="Generate a quiz with various question types based on channel documents",
)
@limiter.limit(RateLimits.CHAT)
async def generate_quiz(
    request: Request,
    channel_id: str,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    body: QuizGenerateRequest | None = None,
):
    """Generate a quiz from channel documents.

    Creates a quiz with:
    - Multiple choice questions
    - Short answer questions
    - True/false questions
    - Answer explanations

    Args:
        channel_id: The channel (File Search Store) ID
        body: Optional configuration for the quiz

    Returns:
        QuizResponse with the generated quiz
    """
    if body is None:
        body = QuizGenerateRequest()

    # Verify channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check if channel has documents
    files = document_port.list_documents(channel_id)
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Channel has no documents. Upload documents first.",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Generate quiz using Clean Architecture use case
    use_case = create_generate_quiz_use_case()
    result = use_case.execute(
        channel_id=channel_id,
        count=body.count,
        quiz_type=body.quiz_type.value,
        difficulty=body.difficulty.value,
        include_explanations=body.include_explanations,
    )

    if result.error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate quiz: {result.error}",
        )

    # Convert to response model
    questions = []
    for q in result.questions:
        # Parse question type
        try:
            q_type = QuizType(q.question_type)
        except ValueError:
            q_type = QuizType.MULTIPLE_CHOICE

        # Parse difficulty
        try:
            difficulty = DifficultyLevel(q.difficulty)
        except ValueError:
            difficulty = DifficultyLevel.MEDIUM

        # Parse choices
        choices = None
        if q.choices:
            choices = [
                QuizChoice(
                    label=c.label,
                    text=c.text,
                    is_correct=c.is_correct,
                )
                for c in q.choices
            ]

        questions.append(
            QuizQuestion(
                question=q.question,
                question_type=q_type,
                choices=choices,
                correct_answer=q.correct_answer,
                explanation=q.explanation or "",
                difficulty=difficulty,
            )
        )

    return QuizResponse(
        channel_id=channel_id,
        title=result.title,
        description=result.description,
        questions=questions,
        total_questions=len(questions),
        quiz_type=body.quiz_type,
        difficulty=body.difficulty,
        generated_at=datetime.now(UTC),
    )
