# -*- coding: utf-8 -*-
"""Notes API endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.models.note import NoteCreate, NoteUpdate, NoteResponse, NoteList
from src.models.chat import GroundingSource
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.channel_repository import ChannelRepository
from src.services.note_repository import NoteRepository

router = APIRouter(prefix="/notes", tags=["notes"])


def _get_channel_or_404(
    channel_id: str, gemini: GeminiService, db: Session
) -> tuple:
    """Get channel or raise 404."""
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    channel_repo = ChannelRepository(db)
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        # Create if not exists (for channels created before DB integration)
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=store.get("display_name", "unknown"),
        )

    return store, channel_meta


def _note_to_response(note, gemini_store_id: str) -> NoteResponse:
    """Convert NoteDB to NoteResponse."""
    sources = [
        GroundingSource(source=s.get("source", ""), content=s.get("content", ""))
        for s in json.loads(note.sources_json)
    ]
    return NoteResponse(
        id=note.id,
        channel_id=gemini_store_id,
        title=note.title,
        content=note.content,
        sources=sources,
        created_at=note.created_at,
        updated_at=note.updated_at,
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> NoteResponse:
    """Create a new note in a channel.

    Notes can be created manually or from AI responses.
    """
    store, channel_meta = _get_channel_or_404(channel_id, gemini, db)

    note_repo = NoteRepository(db)
    sources_data = [{"source": s.source, "content": s.content} for s in data.sources]

    note = note_repo.create(
        channel=channel_meta,
        title=data.title,
        content=data.content,
        sources=sources_data,
    )

    return _note_to_response(note, channel_id)


@router.get(
    "",
    response_model=NoteList,
    summary="List notes in a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def list_notes(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(description="Maximum number of notes", ge=1, le=100)] = 50,
    offset: Annotated[int, Query(description="Number of notes to skip", ge=0)] = 0,
) -> NoteList:
    """List all notes in a channel."""
    store, channel_meta = _get_channel_or_404(channel_id, gemini, db)

    note_repo = NoteRepository(db)
    notes = note_repo.get_by_channel(channel_meta, limit=limit, offset=offset)
    total = note_repo.count_by_channel(channel_meta)

    return NoteList(
        notes=[_note_to_response(n, channel_id) for n in notes],
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> NoteResponse:
    """Get a specific note by its ID."""
    store, channel_meta = _get_channel_or_404(channel_id, gemini, db)

    note_repo = NoteRepository(db)
    note = note_repo.get_by_id(note_id)

    if not note or note.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )

    return _note_to_response(note, channel_id)


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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> NoteResponse:
    """Update an existing note."""
    store, channel_meta = _get_channel_or_404(channel_id, gemini, db)

    note_repo = NoteRepository(db)
    note = note_repo.get_by_id(note_id)

    if not note or note.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )

    if data.title is None and data.content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (title or content) must be provided",
        )

    updated_note = note_repo.update(note, title=data.title, content=data.content)
    return _note_to_response(updated_note, channel_id)


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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a note."""
    store, channel_meta = _get_channel_or_404(channel_id, gemini, db)

    note_repo = NoteRepository(db)
    note = note_repo.get_by_id(note_id)

    if not note or note.channel_id != channel_meta.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )

    note_repo.delete(note)
    return None
