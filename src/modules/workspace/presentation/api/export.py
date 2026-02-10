# -*- coding: utf-8 -*-
"""Export API endpoints (thin controller)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.modules.workspace.presentation.schemas.export import ExportFormat
from src.modules.workspace.application.use_cases.export_channel_context import (
    ExportChannelContextUseCase,
)
from src.modules.workspace.application.services.export_service import ExportService
from src.shared.kernel.contracts.errors.use_case_errors import ChannelNotFoundError
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/export", tags=["export"])


# ── Dependencies ────────────────────────────────────────────

def _get_context_use_case(db: Session = Depends(get_db)) -> ExportChannelContextUseCase:
    from src.modules.workspace.public import create_export_channel_context_use_case
    return create_export_channel_context_use_case(db)


def get_export_service(db: Session = Depends(get_db)) -> ExportService:
    from src.modules.workspace.public import create_export_service
    return create_export_service(db)


# ── Endpoints ───────────────────────────────────────────────

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
    context_uc: Annotated[ExportChannelContextUseCase, Depends(_get_context_use_case)] = None,
    export_service: Annotated[ExportService, Depends(get_export_service)] = None,
) -> Response:
    try:
        channel_meta = context_uc.resolve(channel_id)
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

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
    context_uc: Annotated[ExportChannelContextUseCase, Depends(_get_context_use_case)] = None,
    export_service: Annotated[ExportService, Depends(get_export_service)] = None,
) -> Response:
    try:
        channel_meta = context_uc.resolve(channel_id)
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

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
    context_uc: Annotated[ExportChannelContextUseCase, Depends(_get_context_use_case)] = None,
    export_service: Annotated[ExportService, Depends(get_export_service)] = None,
) -> Response:
    try:
        channel_meta = context_uc.resolve(channel_id)
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

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
