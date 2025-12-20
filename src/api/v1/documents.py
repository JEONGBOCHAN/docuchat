# -*- coding: utf-8 -*-
"""Document upload API endpoints."""

import os
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status

from src.core.config import get_settings, Settings
from src.models.document import (
    DocumentResponse,
    DocumentList,
    DocumentUploadResponse,
    UploadStatus,
    UrlUploadRequest,
)
from src.services.gemini import GeminiService, get_gemini_service
from src.services.crawler import CrawlerService, get_crawler_service

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
async def upload_document(
    channel_id: Annotated[str, Query(description="Channel ID (e.g., fileSearchStores/xxx)")],
    file: Annotated[UploadFile, File(description="Document file to upload")],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    settings: Annotated[Settings, Depends(get_settings)],
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

    # Save to temporary file for upload
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(file.filename or "document").suffix,
        ) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Upload to Gemini
        operation = gemini.upload_file(channel_id, tmp_path)

        return DocumentUploadResponse(
            id=operation["name"],
            filename=file.filename or "document",
            status=UploadStatus.PROCESSING if not operation["done"] else UploadStatus.COMPLETED,
            message="Upload initiated" if not operation["done"] else "Upload completed",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}",
        )
    finally:
        # Clean up temp file
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.post(
    "/url",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload document from URL",
)
def upload_from_url(
    channel_id: Annotated[str, Query(description="Channel ID (e.g., fileSearchStores/xxx)")],
    request: UrlUploadRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    crawler: Annotated[CrawlerService, Depends(get_crawler_service)],
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

    tmp_path = None
    try:
        # Crawl the URL
        result = crawler.fetch_url(request.url)

        # Save to temp file
        tmp_path = crawler.save_to_temp_file(result)

        # Upload to Gemini
        operation = gemini.upload_file(channel_id, tmp_path)

        return DocumentUploadResponse(
            id=operation["name"],
            filename=f"{result.title}.md",
            status=UploadStatus.PROCESSING if not operation["done"] else UploadStatus.COMPLETED,
            message="URL content uploaded" if not operation["done"] else "Upload completed",
        )

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
def list_documents(
    channel_id: Annotated[str, Query(description="Channel ID (e.g., fileSearchStores/xxx)")],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
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
def get_document_status(
    document_id: str,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
) -> dict:
    """Get the status of a document upload operation."""
    status_info = gemini.get_operation_status(document_id)
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
def delete_document(
    document_id: str,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
):
    """Delete a document.

    Note: document_id should be the full file name (e.g., "files/xxx")
    """
    success = gemini.delete_file(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        )
    return None
