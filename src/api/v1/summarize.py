# -*- coding: utf-8 -*-
"""Summarization API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.models.summarize import SummarizeRequest, SummarizeResponse, SummaryType
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.channel_repository import ChannelRepository

router = APIRouter(prefix="/channels", tags=["summarize"])


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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> SummarizeResponse:
    """Generate a summary of a specific document in the channel.

    Supports two summary types:
    - 'short': A concise 2-3 sentence summary
    - 'detailed': A comprehensive summary with sections
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Check if document exists in channel
    files = gemini.list_store_files(channel_id)
    document_found = any(f["name"] == document_id for f in files)

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
        (f.get("display_name", f["name"]) for f in files if f["name"] == document_id),
        document_id,
    )

    # Generate summary
    result = gemini.summarize_document(
        channel_id,
        document_name=document_name,
        summary_type=body.summary_type.value,
    )

    if "error" in result and result["error"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {result['error']}",
        )

    return SummarizeResponse(
        channel_id=channel_id,
        document_id=document_id,
        summary_type=body.summary_type,
        summary=result["summary"],
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> SummarizeResponse:
    """Generate a summary of all documents in the channel.

    Supports two summary types:
    - 'short': A concise 2-3 sentence summary
    - 'detailed': A comprehensive summary with sections
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Check if channel has documents
    files = gemini.list_store_files(channel_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel has no documents. Upload documents first to generate summary.",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Generate summary
    result = gemini.summarize_channel(channel_id, summary_type=body.summary_type.value)

    if "error" in result and result["error"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {result['error']}",
        )

    return SummarizeResponse(
        channel_id=channel_id,
        summary_type=body.summary_type,
        summary=result["summary"],
    )
