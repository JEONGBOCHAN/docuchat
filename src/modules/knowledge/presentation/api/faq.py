# -*- coding: utf-8 -*-
"""FAQ generation API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.modules.knowledge.presentation.schemas.faq import FAQItem, FAQGenerateRequest, FAQGenerateResponse
from src.modules.knowledge.presentation.dependencies.channel_validation import ValidatedChannel, require_channel_with_documents
from src.modules.knowledge.public import create_generate_faq_use_case

router = APIRouter(prefix="/channels", tags=["faq"])


@router.post(
    "/{channel_id:path}/generate-faq",
    response_model=FAQGenerateResponse,
    summary="Generate FAQ from documents",
)
def generate_faq(
    request: FAQGenerateRequest,
    validated: Annotated[ValidatedChannel, Depends(require_channel_with_documents)],
) -> FAQGenerateResponse:
    """Generate frequently asked questions based on channel documents.

    Analyzes the documents in the channel and generates FAQ items
    with questions that users might naturally ask and their answers.
    """
    # Generate FAQ using Clean Architecture UseCase
    use_case = create_generate_faq_use_case()
    result = use_case.execute(channel_id=validated.channel_id, count=request.count)

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
        channel_id=validated.channel_id,
        items=items,
    )
