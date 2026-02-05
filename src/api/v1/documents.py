# -*- coding: utf-8 -*-
"""Document upload API endpoints."""

import logging
import os
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from src.core.config import get_settings, Settings
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.models.document import (
    DocumentResponse,
    DocumentList,
    DocumentUploadResponse,
    UploadStatus,
    UrlUploadRequest,
)
from src.application.ports.channel import ChannelPort
from src.application.ports.document import DocumentPort
from src.application.ports.external_services import CrawlerPort
from src.application.ports.cache import CachePort
from src.application.services.capacity_service import CapacityService, CapacityExceededError
from src.application.use_cases.document_summary import GenerateDocumentSummaryUseCase
from src.infrastructure.di.container import (
    create_channel_port,
    create_document_port,
    create_crawler_port,
    create_cache_port,
    create_capacity_service,
    create_generate_document_summary_use_case,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_document_port() -> DocumentPort:
    """Get document port instance."""
    return create_document_port()


def get_crawler_port() -> CrawlerPort:
    """Get crawler port instance."""
    return create_crawler_port()


def get_cache_port() -> CachePort:
    """Get cache port instance."""
    return create_cache_port()


def get_capacity_service(db: Session = Depends(get_db)) -> CapacityService:
    """Get capacity service instance."""
    return create_capacity_service(db)


def get_summary_use_case(db: Session = Depends(get_db)) -> GenerateDocumentSummaryUseCase:
    """Get document summary use case instance."""
    return create_generate_document_summary_use_case(db)


def validate_file(
    file: UploadFile,
    settings: Settings,
) -> None:
    """Validate uploaded file.

    Raises:
        HTTPException: If file validation fails
    """
    # Check file extension
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed: {settings.allowed_extensions}",
            )

    # Check file size (read content to check)
    # Note: For large files, we should use streaming, but for simplicity we check after upload
    max_size = settings.max_file_size_mb * 1024 * 1024
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB",
        )


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document to channel",
)
@limiter.limit(RateLimits.FILE_UPLOAD)
async def upload_document(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID (e.g., fileSearchStores/xxx)")],
    file: Annotated[UploadFile, File(description="Document file to upload")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    settings: Annotated[Settings, Depends(get_settings)],
    cache: Annotated[CachePort, Depends(get_cache_port)],
    capacity_service: Annotated[CapacityService, Depends(get_capacity_service)],
    summary_use_case: Annotated[GenerateDocumentSummaryUseCase, Depends(get_summary_use_case)],
) -> DocumentUploadResponse:
    """Upload a document to a channel.

    The file will be processed asynchronously. Use the returned ID to check status.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Validate file
    validate_file(file, settings)

    # Check capacity limits
    file_size = file.size or 0
    try:
        capacity_service.validate_upload(channel_id, file_size)
    except CapacityExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )

    # Save to temporary file for upload (preserve original filename)
    try:
        original_filename = file.filename or "document"
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, original_filename)
        content = await file.read()
        with open(tmp_path, "wb") as tmp:
            tmp.write(content)
        actual_size = len(content)

        # Upload to Gemini with original filename as display_name
        result = document_port.upload_document(channel_id, tmp_path, display_name=original_filename)

        # Update capacity tracking after successful upload
        capacity_service.update_after_upload(channel_id, actual_size)

        # Invalidate document list and chat caches for this channel
        cache.invalidate_document_cache(channel_id)
        cache.invalidate_chat_cache(channel_id)

        # Generate document summary for agent context (graceful degradation)
        # This helps the agent choose the right tool (search_documents vs web_search)
        try:
            summary_result = summary_use_case.execute(
                channel_id=channel_id,
                document_id=result.document_id or result.operation_name,
                document_name=original_filename,
            )
            if summary_result.success:
                logger.info(f"Generated summary for document: {original_filename}")
            else:
                logger.warning(
                    f"Failed to generate summary for {original_filename}: "
                    f"{summary_result.error}"
                )
        except Exception as e:
            # Graceful degradation: log but don't fail upload
            logger.warning(f"Summary generation failed for {original_filename}: {e}")

        return DocumentUploadResponse(
            id=result.operation_name,
            filename=file.filename or "document",
            status=UploadStatus.PROCESSING if not result.done else UploadStatus.COMPLETED,
            message="Upload initiated" if not result.done else "Upload completed",
            done=result.done,
        )

    except CapacityExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}",
        )
    finally:
        # Clean up temp file and directory
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if "tmp_dir" in locals():
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass


@router.post(
    "/url",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload document from URL",
)
@limiter.limit(RateLimits.FILE_UPLOAD)
def upload_from_url(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID (e.g., fileSearchStores/xxx)")],
    body: UrlUploadRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    crawler: Annotated[CrawlerPort, Depends(get_crawler_port)],
    cache: Annotated[CachePort, Depends(get_cache_port)],
    capacity_service: Annotated[CapacityService, Depends(get_capacity_service)],
    summary_use_case: Annotated[GenerateDocumentSummaryUseCase, Depends(get_summary_use_case)],
) -> DocumentUploadResponse:
    """Crawl a URL and upload the content as a document.

    The URL content will be fetched, converted to markdown, and uploaded to the channel.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    tmp_path = None
    try:
        # Crawl the URL
        result = crawler.fetch_url(body.url)

        # Save to temp file
        tmp_path = crawler.save_to_temp_file(result)

        # Get file size and validate capacity
        file_size = os.path.getsize(tmp_path)
        try:
            capacity_service.validate_upload(channel_id, file_size)
        except CapacityExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(e),
            )

        # Upload to Gemini with URL title as display_name
        url_filename = f"{result.title}.md"
        upload_result = document_port.upload_document(channel_id, tmp_path, display_name=url_filename)

        # Update capacity tracking
        capacity_service.update_after_upload(channel_id, file_size)

        # Invalidate document list and chat caches for this channel
        cache.invalidate_document_cache(channel_id)
        cache.invalidate_chat_cache(channel_id)

        # Generate document summary for agent context (graceful degradation)
        try:
            summary_result = summary_use_case.execute(
                channel_id=channel_id,
                document_id=upload_result.document_id or upload_result.operation_name,
                document_name=url_filename,
            )
            if summary_result.success:
                logger.info(f"Generated summary for URL document: {url_filename}")
            else:
                logger.warning(
                    f"Failed to generate summary for {url_filename}: "
                    f"{summary_result.error}"
                )
        except Exception as e:
            logger.warning(f"Summary generation failed for {url_filename}: {e}")

        return DocumentUploadResponse(
            id=upload_result.operation_name,
            filename=url_filename,
            status=UploadStatus.PROCESSING if not upload_result.done else UploadStatus.COMPLETED,
            message="URL content uploaded" if not upload_result.done else "Upload completed",
            done=upload_result.done,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload from URL: {str(e)}",
        )
    finally:
        # Clean up temp file
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.get(
    "",
    response_model=DocumentList,
    summary="List documents in channel",
)
@limiter.limit(RateLimits.DEFAULT)
def list_documents(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID (e.g., fileSearchStores/xxx)")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    cache: Annotated[CachePort, Depends(get_cache_port)],
) -> DocumentList:
    """List all documents in a channel."""
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    try:
        # Try to get from cache first
        cached_docs = cache.get_document_list(channel_id)
        if cached_docs is not None:
            documents = [DocumentResponse(**doc) for doc in cached_docs]
            return DocumentList(documents=documents, total=len(documents))

        files = document_port.list_documents(channel_id)
        documents = [
            DocumentResponse(
                id=f.name,
                filename=f.display_name,
                file_size=f.size_bytes,
                content_type="application/octet-stream",  # API doesn't return this
                status=UploadStatus.COMPLETED if f.state == "ACTIVE" else UploadStatus.PROCESSING,
                channel_id=channel_id,
                created_at=datetime.now(UTC),
            )
            for f in files
        ]

        # Cache the document list
        cache.set_document_list(
            channel_id,
            [doc.model_dump(mode="json") for doc in documents],
        )

        return DocumentList(documents=documents, total=len(documents))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}",
        )


@router.get(
    "/{document_id:path}/status",
    summary="Get document upload status",
)
@limiter.limit(RateLimits.DEFAULT)
def get_document_status(
    request: Request,
    document_id: str,
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
) -> dict:
    """Get the status of a document upload operation."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Checking status for document_id: {document_id}")
    status_result = document_port.get_operation_status(document_id)
    logger.info(f"Status result: done={status_result.done}")
    return {
        "id": document_id,
        "done": status_result.done,
    }


@router.delete(
    "/{document_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_document(
    request: Request,
    document_id: str,
    document_port: Annotated[DocumentPort, Depends(get_document_port)],
    cache: Annotated[CachePort, Depends(get_cache_port)],
    channel_id: Annotated[str | None, Query(description="Channel ID to invalidate cache")] = None,
):
    """Delete a document.

    Note: document_id should be the full document name
    (e.g., "fileSearchStores/xxx/documents/yyy")
    Optionally provide channel_id to invalidate related caches.
    """
    # Extract channel_id from document_id if not provided
    # Format: fileSearchStores/xxx/documents/yyy -> fileSearchStores/xxx
    extracted_channel_id = channel_id
    if not extracted_channel_id and document_id.startswith("fileSearchStores/"):
        parts = document_id.split("/documents/")
        if len(parts) >= 1:
            extracted_channel_id = parts[0]

    # Use the correct method based on document_id format
    if document_id.startswith("fileSearchStores/"):
        # File Search Store document
        success = document_port.delete_document(document_id)
    else:
        # Legacy Files API
        success = document_port.delete_file(document_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        )

    # Invalidate caches
    if extracted_channel_id:
        cache.invalidate_document_cache(extracted_channel_id)
        cache.invalidate_chat_cache(extracted_channel_id)

    return None
