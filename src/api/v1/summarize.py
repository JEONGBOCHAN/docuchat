# -*- coding: utf-8 -*-
"""Summarization API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.models.summarize import SummarizeRequest, SummarizeResponse, SummaryType
from src.application.ports.channel import ChannelPort
from src.application.ports.document import DocumentPort
from src.infrastructure.di.container import (
    create_channel_port,
    create_document_port,
    create_summarize_channel_use_case,
    create_summarize_document_use_case,
)
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.channel_repository import ChannelRepository

router = APIRouter(prefix="/channels", tags=["summarize"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_document_port() -> DocumentPort:
    """Get document port instance."""
    return create_document_port()


# NOTE: Document summarize route must come BEFORE channel summarize route
# because /{channel_id:path}/summarize would match the document path otherwise


@router.post(
    "/{channel_id:path}/documents/{document_id:path}/summarize",
    response_model=SummarizeResponse,
    summary="Summarize a specific document",
)
@limiter.limit(RateLimits.CHAT)
def summarize_document(
    request: Request,
    channel_id: str,
    document_id: str,
    body: SummarizeRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    db: Annotated[Session, Depends(get_db)],
) -> SummarizeResponse:
    """Generate a summary of a specific document in the channel.

    Supports two summary types:
    - 'short': A concise 2-3 sentence summary
    - 'detailed': A comprehensive summary with sections
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Check if document exists in channel
    files = document_port.list_documents(channel_id)
    document_found = any(f.name == document_id for f in files)

    if not document_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Get document display name for better summarization
    document_name = next(
        (f.display_name or f.name for f in files if f.name == document_id),
        document_id,
    )

    # Generate summary using Clean Architecture use case
    use_case = create_summarize_document_use_case()
    result = use_case.execute(
        channel_id=channel_id,
        document_name=document_name,
        summary_type=body.summary_type.value,
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {result.error}",
        )

    return SummarizeResponse(
        channel_id=channel_id,
        document_id=document_id,
        summary_type=body.summary_type,
        summary=result.summary,
    )


@router.post(
    "/{channel_id:path}/summarize",
    response_model=SummarizeResponse,
    summary="Summarize all documents in a channel",
)
@limiter.limit(RateLimits.CHAT)
def summarize_channel(
    request: Request,
    channel_id: str,
    body: SummarizeRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    db: Annotated[Session, Depends(get_db)],
) -> SummarizeResponse:
    """Generate a summary of all documents in the channel.

    Supports two summary types:
    - 'short': A concise 2-3 sentence summary
    - 'detailed': A comprehensive summary with sections
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Check if channel has documents
    files = document_port.list_documents(channel_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel has no documents. Upload documents first to generate summary.",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Generate summary using Clean Architecture use case
    use_case = create_summarize_channel_use_case()
    result = use_case.execute(
        channel_id=channel_id,
        summary_type=body.summary_type.value,
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {result.error}",
        )

    return SummarizeResponse(
        channel_id=channel_id,
        summary_type=body.summary_type,
        summary=result.summary,
    )
