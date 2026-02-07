# -*- coding: utf-8 -*-
"""Document preview API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session

from src.core.rate_limiter import limiter, RateLimits
from src.core.database import get_db
from src.models.preview import (
    DocumentPreviewResponse,
    TextHighlight,
    SourceLocation,
    SourceLocationResponse,
)
from src.application.ports.channel import ChannelPort
from src.application.ports.document import DocumentPort
from src.application.ports.preview import DocumentPreviewDTO, SourceLocationResultDTO
from src.application.services.preview_service import PreviewService, DEFAULT_PAGE_SIZE
from src.infrastructure.di.container import (
    create_channel_port,
    create_document_port,
    create_preview_service,
)

router = APIRouter(prefix="/channels", tags=["preview"])


def _preview_dto_to_response(dto: DocumentPreviewDTO) -> DocumentPreviewResponse:
    """Convert DocumentPreviewDTO to Pydantic response model."""
    return DocumentPreviewResponse(
        document_id=dto.document_id,
        filename=dto.filename,
        total_pages=dto.total_pages,
        total_characters=dto.total_characters,
        current_page=dto.current_page,
        page_size=dto.page_size,
        content=dto.content,
        highlights=[
            TextHighlight(start=h.start, end=h.end, text=h.text)
            for h in dto.highlights
        ],
        has_next=dto.has_next,
        has_previous=dto.has_previous,
        cached_at=dto.cached_at,
    )


def _location_dto_to_response(dto: SourceLocationResultDTO) -> SourceLocationResponse:
    """Convert SourceLocationResultDTO to Pydantic response model."""
    location = None
    if dto.location:
        location = SourceLocation(
            document_id=dto.location.document_id,
            filename=dto.location.filename,
            page_number=dto.location.page_number,
            position=dto.location.position,
            context=dto.location.context,
            highlights=[
                TextHighlight(start=h.start, end=h.end, text=h.text)
                for h in dto.location.highlights
            ],
        )
    return SourceLocationResponse(found=dto.found, location=location)


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_document_port() -> DocumentPort:
    """Get document port instance."""
    return create_document_port()


def get_preview_service_dep(db: Session = Depends(get_db)) -> PreviewService:
    """Get preview service instance."""
    return create_preview_service(db)


def _get_document_info(
    channel_port: ChannelPort,
    document_port: DocumentPort,
    channel_id: str,
    document_id: str,
) -> tuple[str, str]:
    """Get document info and validate existence.

    Args:
        channel_port: Channel port
        document_port: Document port
        channel_id: Channel (store) ID
        document_id: Document file ID

    Returns:
        Tuple of (document_id, filename)

    Raises:
        HTTPException: If channel or document not found
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Find the document
    files = document_port.list_documents(channel_id)
    doc = None
    for f in files:
        if f.name == document_id:
            doc = f
            break

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    filename = doc.display_name or "Unknown"
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)] = None,
    document_port: Annotated[DocumentPort, Depends(get_document_port)] = None,
    preview_service: Annotated[PreviewService, Depends(get_preview_service_dep)] = None,
) -> DocumentPreviewResponse:
    """Get document preview with pagination and optional text highlighting.

    Extracts text content from the document and returns it paginated.
    If search_term is provided, matching text will be highlighted.

    The first request may take longer as the content is extracted and cached.
    Subsequent requests will be faster as they use the cached content.
    """
    doc_id, filename = _get_document_info(channel_port, document_port, channel_id, document_id)

    try:
        dto = preview_service.get_preview(
            channel_id=channel_id,
            document_id=doc_id,
            filename=filename,
            page=page,
            page_size=page_size,
            search_term=search_term,
        )
        return _preview_dto_to_response(dto)
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)] = None,
    document_port: Annotated[DocumentPort, Depends(get_document_port)] = None,
    preview_service: Annotated[PreviewService, Depends(get_preview_service_dep)] = None,
) -> DocumentPreviewResponse:
    """Get a specific page of the document.

    This is a convenience endpoint that returns a specific page directly.
    """
    if page_num < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be at least 1",
        )

    doc_id, filename = _get_document_info(channel_port, document_port, channel_id, document_id)

    try:
        dto = preview_service.get_preview(
            channel_id=channel_id,
            document_id=doc_id,
            filename=filename,
            page=page_num,
            page_size=page_size,
            search_term=search_term,
        )
        return _preview_dto_to_response(dto)
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)] = None,
    document_port: Annotated[DocumentPort, Depends(get_document_port)] = None,
    preview_service: Annotated[PreviewService, Depends(get_preview_service_dep)] = None,
) -> SourceLocationResponse:
    """Find the location of a source citation in a document.

    This endpoint helps locate where a specific piece of text appears in a document,
    useful for implementing "click to scroll to source" functionality.

    Returns the page number and position where the text is found, along with
    surrounding context and highlights.
    """
    doc_id, filename = _get_document_info(channel_port, document_port, channel_id, document_id)

    try:
        dto = preview_service.find_source_location(
            channel_id=channel_id,
            document_id=doc_id,
            filename=filename,
            source_text=source_text,
            page_size=page_size,
        )
        return _location_dto_to_response(dto)
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)] = None,
    document_port: Annotated[DocumentPort, Depends(get_document_port)] = None,
    preview_service: Annotated[PreviewService, Depends(get_preview_service_dep)] = None,
):
    """Clear the cached preview for a document.

    Use this when the document content has been updated and you want to
    re-extract the text on the next preview request.
    """
    # Validate channel and document exist
    _get_document_info(channel_port, document_port, channel_id, document_id)
    preview_service.invalidate_cache(document_id)
    return None
