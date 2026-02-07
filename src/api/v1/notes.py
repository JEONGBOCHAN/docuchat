# -*- coding: utf-8 -*-
"""Notes API endpoints.

Thin controller: delegates all business logic to NoteCrudUseCase.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.note import NoteCreate, NoteUpdate, NoteResponse, NoteList
from src.models.chat import GroundingSource
from src.application.use_cases.note_crud import NoteCrudUseCase, NoteDetailDTO
from src.application.use_cases.exceptions import ChannelNotFoundError
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/notes", tags=["notes"])


def get_note_crud_use_case(db: Session = Depends(get_db)) -> NoteCrudUseCase:
    """Get note CRUD use case instance with all dependencies wired."""
    from src.infrastructure.di.container import create_note_crud_use_case
    return create_note_crud_use_case(db)


def _dto_to_response(dto: NoteDetailDTO) -> NoteResponse:
    """Convert application-layer DTO to API response model."""
    sources = [
        GroundingSource(source=s.get("source", ""), content=s.get("content", ""))
        for s in dto.sources
    ]
    return NoteResponse(
        id=dto.id,
        channel_id=dto.channel_id,
        title=dto.title,
        content=dto.content,
        sources=sources,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new note",
)
@limiter.limit(RateLimits.DEFAULT)
def create_note(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    data: NoteCreate,
    use_case: Annotated[NoteCrudUseCase, Depends(get_note_crud_use_case)],
) -> NoteResponse:
    """Create a new note in a channel.

    Notes can be created manually or from AI responses.
    """
    try:
        sources_data = [{"source": s.source, "content": s.content} for s in data.sources]
        dto = use_case.create(channel_id, data.title, data.content, sources_data)
        return _dto_to_response(dto)
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "",
    response_model=NoteList,
    summary="List notes in a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def list_notes(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case: Annotated[NoteCrudUseCase, Depends(get_note_crud_use_case)],
    limit: Annotated[int, Query(description="Maximum number of notes", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of notes to skip", ge=0)] = 0,
) -> NoteList:
    """List all notes in a channel."""
    try:
        result = use_case.list(channel_id, limit=limit, offset=offset)
        return NoteList(
            notes=[_dto_to_response(n) for n in result.notes],
            total=result.total,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get a note by ID",
)
@limiter.limit(RateLimits.DEFAULT)
def get_note(
    request: Request,
    note_id: int,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case: Annotated[NoteCrudUseCase, Depends(get_note_crud_use_case)],
) -> NoteResponse:
    """Get a specific note by its ID."""
    try:
        dto = use_case.get(channel_id, note_id)
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if not dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )
    return _dto_to_response(dto)


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update a note",
)
@limiter.limit(RateLimits.DEFAULT)
def update_note(
    request: Request,
    note_id: int,
    channel_id: Annotated[str, Query(description="Channel ID")],
    data: NoteUpdate,
    use_case: Annotated[NoteCrudUseCase, Depends(get_note_crud_use_case)],
) -> NoteResponse:
    """Update an existing note."""
    if data.title is None and data.content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (title or content) must be provided",
        )

    try:
        dto = use_case.update(channel_id, note_id, title=data.title, content=data.content)
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if not dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )
    return _dto_to_response(dto)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_note(
    request: Request,
    note_id: int,
    channel_id: Annotated[str, Query(description="Channel ID")],
    use_case: Annotated[NoteCrudUseCase, Depends(get_note_crud_use_case)],
):
    """Delete a note (moves to trash).

    The note can be restored from the trash within 30 days.
    Use DELETE /trash/note/{id} for permanent deletion.
    """
    try:
        success = use_case.delete(channel_id, note_id)
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )
    return None
