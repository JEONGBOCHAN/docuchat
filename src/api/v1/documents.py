# -*- coding: utf-8 -*-
"""Document upload API endpoints (thin controller).

All business logic is delegated to DocumentCrudUseCase.
This router handles HTTP concerns: request parsing, response formatting,
and error code translation.
"""

import logging
import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.models.document import (
    DocumentResponse,
    DocumentList,
    DocumentUploadResponse,
    UploadStatus,
    UrlUploadRequest,
)
from src.application.use_cases.document_crud import DocumentCrudUseCase
from src.application.use_cases.exceptions import ChannelNotFoundError, FileValidationError
from src.domain.exceptions import CapacityExceededError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_crud_use_case(
    db: Session = Depends(get_db),
) -> DocumentCrudUseCase:
    """Get document CRUD use case instance."""
    from src.infrastructure.di.container import create_document_crud_use_case
    return create_document_crud_use_case(db)


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
    use_case: Annotated[DocumentCrudUseCase, Depends(get_document_crud_use_case)],
) -> DocumentUploadResponse:
    """Upload a document to a channel.

    The file will be processed asynchronously. Use the returned ID to check status.
    """
    try:
        use_case.validate_file(file.filename, file.size)
    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
        original_filename = os.path.basename(file.filename or "document")
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, original_filename)
        actual_size = 0
        max_size = get_settings().max_file_size_mb * 1024 * 1024
        with open(tmp_path, "wb") as tmp:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                actual_size += len(chunk)
                if actual_size > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size: {get_settings().max_file_size_mb}MB",
                    )
                tmp.write(chunk)

        result = use_case.upload(channel_id, tmp_path, original_filename, actual_size)

        return DocumentUploadResponse(
            id=result.operation_name,
            filename=result.filename,
            status=UploadStatus.PROCESSING if not result.done else UploadStatus.COMPLETED,
            message="Upload initiated" if not result.done else "Upload completed",
            done=result.done,
        )

    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    except CapacityExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload document", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )
    finally:
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
    use_case: Annotated[DocumentCrudUseCase, Depends(get_document_crud_use_case)],
) -> DocumentUploadResponse:
    """Crawl a URL and upload the content as a document.

    The URL content will be fetched, converted to markdown, and uploaded to the channel.
    """
    try:
        result = use_case.upload_from_url(channel_id, body.url)

        return DocumentUploadResponse(
            id=result.operation_name,
            filename=result.filename,
            status=UploadStatus.PROCESSING if not result.done else UploadStatus.COMPLETED,
            message="URL content uploaded" if not result.done else "Upload completed",
            done=result.done,
        )

    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    except CapacityExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload from URL", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload from URL",
        )


@router.get(
    "",
    response_model=DocumentList,
    summary="List documents in channel",
)
@limiter.limit(RateLimits.DEFAULT)
def list_documents(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID (e.g., fileSearchStores/xxx)")],
    use_case: Annotated[DocumentCrudUseCase, Depends(get_document_crud_use_case)],
) -> DocumentList:
    """List all documents in a channel."""
    try:
        result = use_case.list_documents(channel_id)

        documents = [
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                file_size=doc.file_size,
                content_type=doc.content_type,
                status=(
                    UploadStatus.COMPLETED
                    if doc.status == "completed"
                    else UploadStatus.PROCESSING
                ),
                channel_id=doc.channel_id,
                created_at=doc.created_at,
            )
            for doc in result.documents
        ]

        return DocumentList(documents=documents, total=result.total)

    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    except Exception as e:
        logger.error("Failed to list documents", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents",
        )


@router.get(
    "/{document_id:path}/status",
    summary="Get document upload status",
)
@limiter.limit(RateLimits.DEFAULT)
def get_document_status(
    request: Request,
    document_id: str,
    use_case: Annotated[DocumentCrudUseCase, Depends(get_document_crud_use_case)],
) -> dict:
    """Get the status of a document upload operation."""
    result = use_case.get_status(document_id)
    return {"id": result.id, "done": result.done}


@router.delete(
    "/{document_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_document(
    request: Request,
    document_id: str,
    use_case: Annotated[DocumentCrudUseCase, Depends(get_document_crud_use_case)],
    channel_id: Annotated[
        str | None, Query(description="Channel ID to invalidate cache")
    ] = None,
):
    """Delete a document.

    Note: document_id should be the full document name
    (e.g., "fileSearchStores/xxx/documents/yyy")
    Optionally provide channel_id to invalidate related caches.
    """
    success = use_case.delete(document_id, channel_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        )
    return None
