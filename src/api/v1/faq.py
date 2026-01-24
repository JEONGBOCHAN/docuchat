# -*- coding: utf-8 -*-
"""FAQ generation API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.models.faq import FAQItem, FAQGenerateRequest, FAQGenerateResponse
from src.application.ports.channel import ChannelPort
from src.application.ports.document import DocumentPort
from src.application.ports.persistence import ChannelRepositoryPort
from src.core.database import get_db
from src.infrastructure.di.container import (
    create_channel_port,
    create_document_port,
    create_generate_faq_use_case,
    create_channel_repository_port,
)

router = APIRouter(prefix="/channels", tags=["faq"])


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
    "/{channel_id:path}/generate-faq",
    response_model=FAQGenerateResponse,
    summary="Generate FAQ from documents",
)
def generate_faq(
    channel_id: str,
    request: FAQGenerateRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
) -> FAQGenerateResponse:
    """Generate frequently asked questions based on channel documents.

    Analyzes the documents in the channel and generates FAQ items
    with questions that users might naturally ask and their answers.
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
            detail="Channel has no documents. Upload documents first to generate FAQ.",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Generate FAQ using Clean Architecture UseCase
    use_case = create_generate_faq_use_case()
    result = use_case.execute(channel_id=channel_id, count=request.count)

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate FAQ: {result.error}",
        )

    # Convert FAQItemDTO to FAQItem models
    items = [
        FAQItem(
            question=item.question,
            answer=item.answer,
        )
        for item in result.items
    ]

    return FAQGenerateResponse(
        channel_id=channel_id,
        items=items,
    )
