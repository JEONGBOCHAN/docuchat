# -*- coding: utf-8 -*-
"""Export API endpoints for exporting notes, chat history, and channels."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.modules.workspace.presentation.schemas.export import ExportFormat
from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.persistence import ChannelRepositoryPort
from src.modules.workspace.application.services.export_service import ExportService
from src.modules.workspace.public import (
    create_channel_port,
    create_channel_repository_port,
    create_export_service,
)
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/export", tags=["export"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


def get_export_service(db: Session = Depends(get_db)) -> ExportService:
    """Get export service instance."""
    return create_export_service(db)


def _get_channel_or_404(
    channel_id: str, channel_port: ChannelPort, channel_repo: ChannelRepositoryPort
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
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=channel.display_name or "unknown",
        )

    return channel, channel_meta


@router.get(
    "/channels/{channel_id:path}/notes/{note_id}",
    summary="Export a single note",
    description="Export a specific note in the specified format",
)
@limiter.limit(RateLimits.DEFAULT)
def export_note(
    request: Request,
    channel_id: str,
    note_id: int,
    format: Annotated[
        ExportFormat,
        Query(description="Export format: markdown, pdf, or json"),
    ] = ExportFormat.MARKDOWN,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)] = None,
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)] = None,
    export_service: Annotated[ExportService, Depends(get_export_service)] = None,
) -> Response:
    """Export a specific note.

    - **markdown**: Human-readable Markdown format
    - **pdf**: PDF document
    - **json**: Structured JSON format
    """
    _, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    try:
        content, content_type, filename = export_service.export_note(
            channel_meta, note_id, format
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if isinstance(content, bytes):
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        return Response(
            content=content.encode("utf-8"),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@router.get(
    "/channels/{channel_id:path}/chat",
    summary="Export chat history",
    description="Export the chat history of a channel",
)
@limiter.limit(RateLimits.DEFAULT)
def export_chat(
    request: Request,
    channel_id: str,
    format: Annotated[
        ExportFormat,
        Query(description="Export format: markdown or json (pdf not supported)"),
    ] = ExportFormat.MARKDOWN,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)] = None,
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)] = None,
    export_service: Annotated[ExportService, Depends(get_export_service)] = None,
) -> Response:
    """Export chat history of a channel.

    - **markdown**: Human-readable Markdown format
    - **json**: Structured JSON format

    Note: PDF format is not supported for chat export.
    """
    _, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    # PDF not supported for chat, fallback to markdown
    if format == ExportFormat.PDF:
        format = ExportFormat.MARKDOWN

    content, content_type, filename = export_service.export_chat(channel_meta, format)

    return Response(
        content=content.encode("utf-8"),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/channels/{channel_id:path}",
    summary="Export entire channel",
    description="Export the entire channel including metadata, notes, and chat history",
)
@limiter.limit(RateLimits.DEFAULT)
def export_channel(
    request: Request,
    channel_id: str,
    format: Annotated[
        ExportFormat,
        Query(description="Export format: markdown, json, or pdf (pdf exports as zip)"),
    ] = ExportFormat.JSON,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)] = None,
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)] = None,
    export_service: Annotated[ExportService, Depends(get_export_service)] = None,
) -> Response:
    """Export entire channel with all notes and chat history.

    - **markdown**: Human-readable Markdown format
    - **json**: Structured JSON format for data backup
    - **pdf**: ZIP archive containing all files
    """
    _, channel_meta = _get_channel_or_404(channel_id, channel_port, channel_repo)

    content, content_type, filename = export_service.export_channel(channel_meta, format)

    if isinstance(content, bytes):
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        return Response(
            content=content.encode("utf-8"),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
