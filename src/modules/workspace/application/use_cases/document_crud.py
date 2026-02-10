# -*- coding: utf-8 -*-
"""Document CRUD use case.

Orchestrates document upload, listing, status checking, and deletion.
Handles channel validation, capacity checking, cache invalidation,
and summary generation.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.document import DocumentPort
from src.shared.kernel.contracts.ports.external_services import CrawlerPort
from src.shared.kernel.contracts.ports.cache import CachePort
from src.modules.workspace.application.services.capacity_service import CapacityService
from src.modules.workspace.application.use_cases.document_summary import GenerateDocumentSummaryUseCase
from src.shared.kernel.contracts.errors.use_case_errors import ChannelNotFoundError, FileValidationError

logger = logging.getLogger(__name__)


@dataclass
class DocumentUploadResultDTO:
    """Result of a document upload."""
    operation_name: str
    filename: str
    done: bool
    document_name: str | None = None


@dataclass
class DocumentInfoDTO:
    """Information about a single document."""
    id: str
    filename: str
    file_size: int
    content_type: str
    status: str  # "completed" or "processing"
    channel_id: str
    created_at: datetime


@dataclass
class DocumentListResultDTO:
    """Result of listing documents."""
    documents: list[DocumentInfoDTO]
    total: int


@dataclass
class DocumentStatusDTO:
    """Status of a document upload."""
    id: str
    done: bool


class DocumentCrudUseCase:
    """Orchestrates document CRUD operations."""

    def __init__(
        self,
        channel_port: ChannelPort,
        document_port: DocumentPort,
        cache: CachePort,
        capacity_service: CapacityService,
        summary_use_case: GenerateDocumentSummaryUseCase,
        crawler_port: CrawlerPort | None = None,
        allowed_extensions: set[str] | None = None,
        max_file_size_mb: int = 50,
    ):
        self._channel_port = channel_port
        self._document_port = document_port
        self._cache = cache
        self._capacity = capacity_service
        self._summary = summary_use_case
        self._crawler = crawler_port
        self._allowed_extensions = allowed_extensions or {
            ".pdf", ".txt", ".md", ".docx",
        }
        self._max_file_size_mb = max_file_size_mb

    def _validate_channel(self, channel_id: str) -> None:
        """Validate channel exists."""
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            raise ChannelNotFoundError(channel_id)

    def _generate_summary(self, channel_id, upload_result, document_name):
        """Generate document summary with graceful degradation."""
        try:
            summary_result = self._summary.execute(
                channel_id=channel_id,
                document_id=upload_result.document_name or upload_result.operation_name,
                document_name=document_name,
            )
            if summary_result.success:
                logger.info(f"Generated summary for document: {document_name}")
            else:
                logger.warning(
                    f"Failed to generate summary for {document_name}: "
                    f"{summary_result.error}"
                )
        except Exception as e:
            logger.warning(f"Summary generation failed for {document_name}: {e}")

    def validate_file(self, filename: str | None, file_size: int | None) -> None:
        """Validate file extension and size.

        Raises:
            FileValidationError: If file validation fails.
        """
        if filename:
            ext = Path(filename).suffix.lower()
            if ext not in self._allowed_extensions:
                raise FileValidationError(
                    f"File type not allowed. Allowed: {self._allowed_extensions}"
                )

        max_size = self._max_file_size_mb * 1024 * 1024
        if file_size and file_size > max_size:
            raise FileValidationError(
                f"File too large. Maximum size: {self._max_file_size_mb}MB"
            )

    def upload(
        self,
        channel_id: str,
        file_path: str,
        original_filename: str,
        file_size: int,
    ) -> DocumentUploadResultDTO:
        """Upload a document to a channel.

        Validates channel and capacity, uploads document, updates capacity,
        invalidates caches, and generates summary.

        Raises:
            ChannelNotFoundError: Channel not found.
            CapacityExceededError: Capacity limits exceeded.
        """
        self._validate_channel(channel_id)
        self._capacity.validate_upload(channel_id, file_size)

        result = self._document_port.upload_document(
            channel_id, file_path, display_name=original_filename
        )

        self._capacity.update_after_upload(channel_id, file_size)
        self._cache.invalidate_document_cache(channel_id)
        self._cache.invalidate_chat_cache(channel_id)
        self._generate_summary(channel_id, result, original_filename)

        return DocumentUploadResultDTO(
            operation_name=result.operation_name,
            filename=original_filename,
            done=result.done,
            document_name=result.document_name,
        )

    def upload_from_url(self, channel_id: str, url: str) -> DocumentUploadResultDTO:
        """Crawl URL and upload content as a document.

        Raises:
            ChannelNotFoundError: Channel not found.
            CapacityExceededError: Capacity limits exceeded.
            ValueError: Invalid URL.
            RuntimeError: Crawler not configured.
        """
        if not self._crawler:
            raise RuntimeError("Crawler port not configured")

        self._validate_channel(channel_id)

        tmp_path = None
        try:
            crawl_result = self._crawler.fetch_url(url)
            tmp_path = self._crawler.save_to_temp_file(crawl_result)
            file_size = os.path.getsize(tmp_path)
            url_filename = f"{crawl_result.title}.md"

            self._capacity.validate_upload(channel_id, file_size)

            upload_result = self._document_port.upload_document(
                channel_id, tmp_path, display_name=url_filename
            )

            self._capacity.update_after_upload(channel_id, file_size)
            self._cache.invalidate_document_cache(channel_id)
            self._cache.invalidate_chat_cache(channel_id)
            self._generate_summary(channel_id, upload_result, url_filename)

            return DocumentUploadResultDTO(
                operation_name=upload_result.operation_name,
                filename=url_filename,
                done=upload_result.done,
                document_name=upload_result.document_name,
            )
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def list_documents(self, channel_id: str) -> DocumentListResultDTO:
        """List documents in a channel.

        Raises:
            ChannelNotFoundError: Channel not found.
        """
        self._validate_channel(channel_id)

        # Try cache first
        cached_docs = self._cache.get_document_list(channel_id)
        if cached_docs is not None:
            documents = [
                DocumentInfoDTO(
                    id=doc["id"],
                    filename=doc["filename"],
                    file_size=doc.get("file_size", 0),
                    content_type=doc.get("content_type", "application/octet-stream"),
                    status=doc.get("status", "completed"),
                    channel_id=doc.get("channel_id", channel_id),
                    created_at=(
                        datetime.fromisoformat(doc["created_at"])
                        if isinstance(doc.get("created_at"), str)
                        else doc.get("created_at", datetime.now(UTC))
                    ),
                )
                for doc in cached_docs
            ]
            return DocumentListResultDTO(documents=documents, total=len(documents))

        # Fetch from port
        files = self._document_port.list_documents(channel_id)
        documents = [
            DocumentInfoDTO(
                id=f.name,
                filename=f.display_name,
                file_size=f.size_bytes,
                content_type="application/octet-stream",
                status="completed" if f.state == "ACTIVE" else "processing",
                channel_id=channel_id,
                created_at=datetime.now(UTC),
            )
            for f in files
        ]

        # Cache the document list
        cache_data = [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "content_type": doc.content_type,
                "status": doc.status,
                "channel_id": doc.channel_id,
                "created_at": doc.created_at.isoformat(),
            }
            for doc in documents
        ]
        self._cache.set_document_list(channel_id, cache_data)

        return DocumentListResultDTO(documents=documents, total=len(documents))

    def get_status(self, document_id: str) -> DocumentStatusDTO:
        """Get document upload status."""
        status_result = self._document_port.get_operation_status(document_id)
        return DocumentStatusDTO(id=document_id, done=status_result.done)

    def delete(self, document_id: str, channel_id: str | None = None) -> bool:
        """Delete a document.

        Returns True if deleted, False otherwise.
        Updates capacity statistics after successful deletion.
        """
        # Extract channel_id from document_id if not provided
        extracted_channel_id = channel_id
        if not extracted_channel_id:
            extracted_channel_id = self._document_port.extract_channel_id(document_id)

        # Try to get file size before deletion (best-effort for capacity update)
        deleted_file_size = 0
        if extracted_channel_id:
            try:
                docs = self._document_port.list_documents(extracted_channel_id)
                for doc in docs:
                    if doc.name == document_id:
                        deleted_file_size = doc.size_bytes
                        break
            except Exception:
                logger.warning(
                    "Could not determine file size before deletion, "
                    "capacity size will sync on next scheduled update"
                )

        # Delete using unified method (port decides based on ID format)
        success = self._document_port.delete_any(document_id)

        if not success:
            return False

        # Update capacity and invalidate caches
        if extracted_channel_id:
            try:
                self._capacity.update_after_delete(
                    extracted_channel_id, deleted_file_size
                )
            except Exception:
                logger.warning("Failed to update capacity after deletion")
            self._cache.invalidate_document_cache(extracted_channel_id)
            self._cache.invalidate_chat_cache(extracted_channel_id)

        return True
