# -*- coding: utf-8 -*-
"""Document upload API endpoints."""

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
from src.services.gemini import GeminiService, get_gemini_service
from src.services.crawler import CrawlerService, get_crawler_service
from src.services.capacity_service import CapacityService, CapacityExceededError
from src.services.cache_service import CacheService, get_cache_service

router = APIRouter(prefix="/documents", tags=["documents"])


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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DocumentUploadResponse:
    """Upload a document to a channel.

    The file will be processed asynchronously. Use the returned ID to check status.
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Validate file
    validate_file(file, settings)

    # Check capacity limits
    capacity_service = CapacityService(db)
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
        operation = gemini.upload_file(channel_id, tmp_path, display_name=original_filename)

        # Update capacity tracking after successful upload
        capacity_service.update_after_upload(channel_id, actual_size)

        # Invalidate document list and chat caches for this channel
        cache.invalidate_document_cache(channel_id)
        cache.invalidate_chat_cache(channel_id)

        return DocumentUploadResponse(
            id=operation["name"],
            filename=file.filename or "document",
            status=UploadStatus.PROCESSING if not operation["done"] else UploadStatus.COMPLETED,
            message="Upload initiated" if not operation["done"] else "Upload completed",
            done=operation["done"],
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    crawler: Annotated[CrawlerService, Depends(get_crawler_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DocumentUploadResponse:
    """Crawl a URL and upload the content as a document.

    The URL content will be fetched, converted to markdown, and uploaded to the channel.
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    capacity_service = CapacityService(db)
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
        operation = gemini.upload_file(channel_id, tmp_path, display_name=url_filename)

        # Update capacity tracking
        capacity_service.update_after_upload(channel_id, file_size)

        # Invalidate document list and chat caches for this channel
        cache.invalidate_document_cache(channel_id)
        cache.invalidate_chat_cache(channel_id)

        return DocumentUploadResponse(
            id=operation["name"],
            filename=url_filename,
            status=UploadStatus.PROCESSING if not operation["done"] else UploadStatus.COMPLETED,
            message="URL content uploaded" if not operation["done"] else "Upload completed",
            done=operation["done"],
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DocumentList:
    """List all documents in a channel."""
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
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

        files = gemini.list_store_files(channel_id)
        documents = [
            DocumentResponse(
                id=f["name"],
                filename=f.get("display_name", ""),
                file_size=int(f.get("size_bytes", 0)),
                content_type="application/octet-stream",  # API doesn't return this
                status=UploadStatus.COMPLETED if f.get("state") == "ACTIVE" else UploadStatus.PROCESSING,
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
) -> dict:
    """Get the status of a document upload operation."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Checking status for document_id: {document_id}")
    status_info = gemini.get_operation_status(document_id)
    logger.info(f"Status result: {status_info}")
    return {
        "id": document_id,
        "done": status_info.get("done", False),
        "error": status_info.get("error"),
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
    channel_id: Annotated[str | None, Query(description="Channel ID to invalidate cache")] = None,
):
    """Delete a document.

    Note: document_id should be the full file name (e.g., "files/xxx")
    Optionally provide channel_id to invalidate related caches.
    """
    success = gemini.delete_file(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        )

    # Invalidate caches if channel_id is provided
    if channel_id:
        cache.invalidate_document_cache(channel_id)
        cache.invalidate_chat_cache(channel_id)

    return None
