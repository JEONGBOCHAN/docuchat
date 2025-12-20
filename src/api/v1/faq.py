# -*- coding: utf-8 -*-
"""FAQ generation API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.models.faq import FAQItem, FAQGenerateRequest, FAQGenerateResponse
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.services.channel_repository import ChannelRepository

router = APIRouter(prefix="/channels", tags=["faq"])


@router.post(
    "/{channel_id:path}/generate-faq",
    response_model=FAQGenerateResponse,
    summary="Generate FAQ from documents",
)
def generate_faq(
    channel_id: str,
    request: FAQGenerateRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> FAQGenerateResponse:
    """Generate frequently asked questions based on channel documents.

    Analyzes the documents in the channel and generates FAQ items
    with questions that users might naturally ask and their answers.
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
            detail="Channel has no documents. Upload documents first to generate FAQ.",
        )

    # Update last accessed time
    channel_repo = ChannelRepository(db)
    channel_repo.touch(channel_id)

    # Generate FAQ
    result = gemini.generate_faq(channel_id, count=request.count)

    if "error" in result and result["error"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate FAQ: {result['error']}",
        )

    # Convert to FAQItem models
    items = [
        FAQItem(
            question=item.get("question", ""),
            answer=item.get("answer", ""),
        )
        for item in result.get("items", [])
    ]

    return FAQGenerateResponse(
        channel_id=channel_id,
        items=items,
    )
