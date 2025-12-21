# -*- coding: utf-8 -*-
"""Document preview API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.models.preview import (
    DocumentPreviewResponse,
    SourceLocationResponse,
)
from src.services.gemini import GeminiService, get_gemini_service
from src.services.preview_service import PreviewService, get_preview_service, DEFAULT_PAGE_SIZE

router = APIRouter(prefix="/channels", tags=["preview"])


def _get_document_info(
    gemini: GeminiService,
    channel_id: str,
    document_id: str,
) -> tuple[str, str]:
    """Get document info and validate existence.

    Args:
        gemini: Gemini service
        channel_id: Channel (store) ID
        document_id: Document file ID

    Returns:
        Tuple of (document_id, filename)

    Raises:
        HTTPException: If channel or document not found
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Find the document
    files = gemini.list_store_files(channel_id)
    doc = None
    for f in files:
        if f.get("name") == document_id:
            doc = f
            break

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    filename = doc.get("display_name", "Unknown")
    return document_id, filename


@router.get(
    "/{channel_id:path}/documents/{document_id:path}/preview",
    response_model=DocumentPreviewResponse,
    summary="Get document preview",
)
@limiter.limit(RateLimits.DEFAULT)
def get_document_preview(
    request: Request,
    channel_id: str,
    document_id: str,
    page: Annotated[int, Query(description="Page number (1-based)", ge=1)] = 1,
    page_size: Annotated[int, Query(description="Characters per page", ge=100, le=10000)] = DEFAULT_PAGE_SIZE,
    search_term: Annotated[str | None, Query(description="Optional search term to highlight")] = None,
    gemini: GeminiService = Depends(get_gemini_service),
    db: Session = Depends(get_db),
) -> DocumentPreviewResponse:
    """Get document preview with pagination and optional text highlighting.

    Extracts text content from the document and returns it paginated.
    If search_term is provided, matching text will be highlighted.

    The first request may take longer as the content is extracted and cached.
    Subsequent requests will be faster as they use the cached content.
    """
    doc_id, filename = _get_document_info(gemini, channel_id, document_id)

    try:
        preview_service = get_preview_service(db)
        return preview_service.get_preview(
            channel_id=channel_id,
            document_id=doc_id,
            filename=filename,
            page=page,
            page_size=page_size,
            search_term=search_term,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document preview: {str(e)}",
        )


@router.get(
    "/{channel_id:path}/documents/{document_id:path}/pages/{page_num}",
    response_model=DocumentPreviewResponse,
    summary="Get specific page of document",
)
@limiter.limit(RateLimits.DEFAULT)
def get_document_page(
    request: Request,
    channel_id: str,
    document_id: str,
    page_num: int,
    page_size: Annotated[int, Query(description="Characters per page", ge=100, le=10000)] = DEFAULT_PAGE_SIZE,
    search_term: Annotated[str | None, Query(description="Optional search term to highlight")] = None,
    gemini: GeminiService = Depends(get_gemini_service),
    db: Session = Depends(get_db),
) -> DocumentPreviewResponse:
    """Get a specific page of the document.

    This is a convenience endpoint that returns a specific page directly.
    """
    if page_num < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be at least 1",
        )

    doc_id, filename = _get_document_info(gemini, channel_id, document_id)

    try:
        preview_service = get_preview_service(db)
        return preview_service.get_preview(
            channel_id=channel_id,
            document_id=doc_id,
            filename=filename,
            page=page_num,
            page_size=page_size,
            search_term=search_term,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document page: {str(e)}",
        )


@router.get(
    "/{channel_id:path}/documents/{document_id:path}/find-source",
    response_model=SourceLocationResponse,
    summary="Find source location in document",
)
@limiter.limit(RateLimits.DEFAULT)
def find_source_in_document(
    request: Request,
    channel_id: str,
    document_id: str,
    source_text: Annotated[str, Query(description="Source text to find in the document")],
    page_size: Annotated[int, Query(description="Characters per page for page calculation", ge=100, le=10000)] = DEFAULT_PAGE_SIZE,
    gemini: GeminiService = Depends(get_gemini_service),
    db: Session = Depends(get_db),
) -> SourceLocationResponse:
    """Find the location of a source citation in a document.

    This endpoint helps locate where a specific piece of text appears in a document,
    useful for implementing "click to scroll to source" functionality.

    Returns the page number and position where the text is found, along with
    surrounding context and highlights.
    """
    doc_id, filename = _get_document_info(gemini, channel_id, document_id)

    try:
        preview_service = get_preview_service(db)
        return preview_service.find_source_location(
            channel_id=channel_id,
            document_id=doc_id,
            filename=filename,
            source_text=source_text,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find source: {str(e)}",
        )


@router.delete(
    "/{channel_id:path}/documents/{document_id:path}/preview-cache",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear document preview cache",
)
@limiter.limit(RateLimits.DEFAULT)
def clear_document_preview_cache(
    request: Request,
    channel_id: str,
    document_id: str,
    gemini: GeminiService = Depends(get_gemini_service),
    db: Session = Depends(get_db),
):
    """Clear the cached preview for a document.

    Use this when the document content has been updated and you want to
    re-extract the text on the next preview request.
    """
    # Validate channel and document exist
    _get_document_info(gemini, channel_id, document_id)

    preview_service = get_preview_service(db)
    preview_service.invalidate_cache(document_id)
    return None
