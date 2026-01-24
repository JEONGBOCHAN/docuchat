# -*- coding: utf-8 -*-
"""Notes API endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.note import NoteCreate, NoteUpdate, NoteResponse, NoteList
from src.models.chat import GroundingSource
from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import (
    ChannelRepositoryPort,
    NoteRepositoryPort,
    TrashRepositoryPort,
)
from src.core.database import get_db
from src.infrastructure.di.container import (
    create_channel_port,
    create_channel_repository_port,
    create_note_repository_port,
    create_trash_repository_port,
)
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/notes", tags=["notes"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


def get_note_repo_port(db: Session = Depends(get_db)) -> NoteRepositoryPort:
    """Get note repository port instance."""
    return create_note_repository_port(db)


def get_trash_repo_port(db: Session = Depends(get_db)) -> TrashRepositoryPort:
    """Get trash repository port instance."""
    return create_trash_repository_port(db)


def _get_channel_or_404(
    channel_id: str,
    channel_port: ChannelPort,
    channel_repo: ChannelRepositoryPort,
) -> tuple:
    """Get channel or raise 404."""
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        # Create if not exists (for channels created before DB integration)
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=channel.display_name or "unknown",
        )

    return channel, channel_meta


def _note_dto_to_response(note_dto, gemini_store_id: str) -> NoteResponse:
    """Convert NoteDTO to NoteResponse."""
    sources = [
        GroundingSource(source=s.get("source", ""), content=s.get("content", ""))
        for s in note_dto.sources
    ]
    return NoteResponse(
        id=note_dto.id,
        channel_id=gemini_store_id,
        title=note_dto.title,
        content=note_dto.content,
        sources=sources,
        created_at=note_dto.created_at,
        updated_at=note_dto.updated_at,
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
) -> NoteResponse:
    """Create a new note in a channel.

    Notes can be created manually or from AI responses.
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    sources_data = [{"source": s.source, "content": s.content} for s in data.sources]

    note_dto = note_repo.create(
        channel_id=channel_meta.id,
        title=data.title,
        content=data.content,
        sources=sources_data,
    )

    return _note_dto_to_response(note_dto, channel_id)


@router.get(
    "",
    response_model=NoteList,
    summary="List notes in a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def list_notes(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
    limit: Annotated[int, Query(description="Maximum number of notes", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of notes to skip", ge=0)] = 0,
) -> NoteList:
    """List all notes in a channel."""
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    notes = note_repo.get_by_channel(channel_meta.id, limit=limit, offset=offset)
    total = note_repo.count_by_channel(channel_meta.id)

    return NoteList(
        notes=[_note_dto_to_response(n, channel_id) for n in notes],
        total=total,
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
) -> NoteResponse:
    """Get a specific note by its ID."""
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    note_dto = note_repo.get_by_id(note_id)

    if not note_dto or note_dto.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )

    return _note_dto_to_response(note_dto, channel_id)


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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
) -> NoteResponse:
    """Update an existing note."""
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    note_dto = note_repo.get_by_id(note_id)

    if not note_dto or note_dto.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )

    if data.title is None and data.content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (title or content) must be provided",
        )

    updated_note = note_repo.update(note_id, title=data.title, content=data.content)
    return _note_dto_to_response(updated_note, channel_id)


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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    note_repo: Annotated[NoteRepositoryPort, Depends(get_note_repo_port)],
    trash_repo: Annotated[TrashRepositoryPort, Depends(get_trash_repo_port)],
):
    """Delete a note (moves to trash).

    The note can be restored from the trash within 30 days.
    Use DELETE /trash/note/{id} for permanent deletion.
    """
    channel, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    note_dto = note_repo.get_by_id(note_id)

    if not note_dto or note_dto.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )

    # Soft delete (move to trash)
    trash_repo.soft_delete_note(note_id)
    return None
