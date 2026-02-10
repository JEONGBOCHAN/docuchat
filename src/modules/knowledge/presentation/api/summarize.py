# -*- coding: utf-8 -*-
"""Summarization API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.modules.knowledge.presentation.schemas.summarize import SummarizeRequest, SummarizeResponse, SummaryType
from src.shared.kernel.contracts.ports.document import DocumentPort
from src.shared.kernel.presentation.dependencies.channel_validation import (
    ValidatedChannel,
    validate_channel_with_touch,
    require_channel_with_documents,
    get_document_port,
)
from src.modules.knowledge.public import (
    create_summarize_channel_use_case,
    create_summarize_document_use_case,
)
from src.core.rate_limiter import limiter, RateLimits

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
    document_id: str,
    body: SummarizeRequest,
    validated: Annotated[ValidatedChannel, Depends(validate_channel_with_touch)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
) -> SummarizeResponse:
    """Generate a summary of a specific document in the channel.

    Supports two summary types:
    - 'short': A concise 2-3 sentence summary
    - 'detailed': A comprehensive summary with sections
    """
    # Check if document exists in channel
    files = document_port.list_documents(validated.channel_id)
    document_found = any(f.name == document_id for f in files)

    if not document_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    # Get document display name for better summarization
    document_name = next(
        (f.display_name or f.name for f in files if f.name == document_id),
        document_id,
    )

    # Generate summary using Clean Architecture use case
    use_case = create_summarize_document_use_case()
    result = use_case.execute(
        channel_id=validated.channel_id,
        document_name=document_name,
        summary_type=body.summary_type.value,
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {result.error}",
        )

    return SummarizeResponse(
        channel_id=validated.channel_id,
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
    body: SummarizeRequest,
    validated: Annotated[ValidatedChannel, Depends(require_channel_with_documents)],
) -> SummarizeResponse:
    """Generate a summary of all documents in the channel.

    Supports two summary types:
    - 'short': A concise 2-3 sentence summary
    - 'detailed': A comprehensive summary with sections
    """
    # Generate summary using Clean Architecture use case
    use_case = create_summarize_channel_use_case()
    result = use_case.execute(
        channel_id=validated.channel_id,
        summary_type=body.summary_type.value,
    )

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {result.error}",
        )

    return SummarizeResponse(
        channel_id=validated.channel_id,
        summary_type=body.summary_type,
        summary=result.summary,
    )
