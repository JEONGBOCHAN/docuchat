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
from src.services.channel_repository import ChannelRepository
from src.services.gemini import GeminiService, get_gemini_service

router = APIRouter(prefix="/channels", tags=["study"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
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
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check if channel has documents
    files = gemini.list_store_files(channel_id)
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Channel has no documents. Upload documents first.",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Generate study guide
    result = gemini.generate_study_guide(
        store_name=channel_id,
        include_concepts=body.include_concepts,
        include_summary=body.include_summary,
        max_sections=body.max_sections,
        difficulty=body.difficulty.value,
    )

    if "error" in result:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate study guide: {result['error']}",
        )

    # Convert to response model
    sections = [
        StudySection(
            title=s.get("title", ""),
            content=s.get("content", ""),
            key_points=s.get("key_points", []),
        )
        for s in result.get("sections", [])
    ]

    key_concepts = [
        KeyConcept(
            term=c.get("term", ""),
            definition=c.get("definition", ""),
            importance=c.get("importance"),
        )
        for c in result.get("key_concepts", [])
    ]

    return StudyGuideResponse(
        channel_id=channel_id,
        title=result.get("title", "Study Guide"),
        overview=result.get("overview", ""),
        sections=sections,
        key_concepts=key_concepts,
        study_tips=result.get("study_tips", []),
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
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
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check if channel has documents
    files = gemini.list_store_files(channel_id)
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Channel has no documents. Upload documents first.",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Generate quiz
    result = gemini.generate_quiz(
        store_name=channel_id,
        count=body.count,
        quiz_type=body.quiz_type.value,
        difficulty=body.difficulty.value,
        include_explanations=body.include_explanations,
    )

    if "error" in result:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate quiz: {result['error']}",
        )

    # Convert to response model
    questions = []
    for q in result.get("questions", []):
        # Parse question type
        q_type_str = q.get("question_type", "multiple_choice")
        try:
            q_type = QuizType(q_type_str)
        except ValueError:
            q_type = QuizType.MULTIPLE_CHOICE

        # Parse difficulty
        diff_str = q.get("difficulty", "medium")
        try:
            difficulty = DifficultyLevel(diff_str)
        except ValueError:
            difficulty = DifficultyLevel.MEDIUM

        # Parse choices
        choices = None
        if q.get("choices"):
            choices = [
                QuizChoice(
                    label=c.get("label", ""),
                    text=c.get("text", ""),
                    is_correct=c.get("is_correct", False),
                )
                for c in q.get("choices", [])
            ]

        questions.append(
            QuizQuestion(
                question=q.get("question", ""),
                question_type=q_type,
                choices=choices,
                correct_answer=q.get("correct_answer", ""),
                explanation=q.get("explanation", ""),
                difficulty=difficulty,
            )
        )

    return QuizResponse(
        channel_id=channel_id,
        title=result.get("title", "Quiz"),
        description=result.get("description", ""),
        questions=questions,
        total_questions=len(questions),
        quiz_type=body.quiz_type,
        difficulty=body.difficulty,
        generated_at=datetime.now(UTC),
    )
