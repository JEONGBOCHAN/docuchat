# -*- coding: utf-8 -*-
"""Repository for document summary cache database operations."""

from datetime import datetime, UTC
from sqlalchemy.orm import Session

from src.infrastructure.persistence.db_models import DocumentSummaryCacheDB
from src.application.ports.document_summary import (
    DocumentSummaryCachePort,
    DocumentSummaryDTO,
)


class DocumentSummaryCacheRepository(DocumentSummaryCachePort):
    """Repository for document summary cache operations.

    Implements DocumentSummaryCachePort for persistence layer.
    Stores document summaries for efficient retrieval during chat.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def save(self, summary: DocumentSummaryDTO) -> DocumentSummaryDTO:
        """Save or update a document summary.

        If a summary for the document already exists, it is updated.
        Otherwise, a new record is created.

        Args:
            summary: The summary to save

        Returns:
            Saved DocumentSummaryDTO with timestamps
        """
        existing = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.document_id == summary.document_id
        ).first()

        if existing:
            # Update existing
            existing.channel_id = summary.channel_id
            existing.document_name = summary.document_name
            existing.summary = summary.summary
            existing.updated_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(existing)
            return self._to_dto(existing)
        else:
            # Create new
            db_summary = DocumentSummaryCacheDB(
                document_id=summary.document_id,
                channel_id=summary.channel_id,
                document_name=summary.document_name,
                summary=summary.summary,
            )
            self.db.add(db_summary)
            self.db.commit()
            self.db.refresh(db_summary)
            return self._to_dto(db_summary)

    def get_by_document_id(self, document_id: str) -> DocumentSummaryDTO | None:
        """Get summary by document ID.

        Args:
            document_id: The document's unique ID

        Returns:
            DocumentSummaryDTO or None if not found
        """
        db_summary = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.document_id == document_id
        ).first()

        return self._to_dto(db_summary) if db_summary else None

    def get_by_channel(
        self,
        channel_id: str,
        limit: int = 10,
    ) -> list[DocumentSummaryDTO]:
        """Get all summaries for a channel.

        Returns summaries ordered by creation date (newest first),
        limited to prevent prompt bloat.

        Args:
            channel_id: The channel (store) ID
            limit: Maximum number of summaries to return (default: 10)

        Returns:
            List of DocumentSummaryDTO for the channel
        """
        db_summaries = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.channel_id == channel_id
        ).order_by(
            DocumentSummaryCacheDB.created_at.desc()
        ).limit(limit).all()

        return [self._to_dto(s) for s in db_summaries]

    def delete_by_document_id(self, document_id: str) -> bool:
        """Delete a summary by document ID.

        Args:
            document_id: The document's unique ID

        Returns:
            True if deleted, False if not found
        """
        result = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.document_id == document_id
        ).delete()
        self.db.commit()
        return result > 0

    def delete_by_channel(self, channel_id: str) -> int:
        """Delete all summaries for a channel.

        Args:
            channel_id: The channel (store) ID

        Returns:
            Number of summaries deleted
        """
        count = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.channel_id == channel_id
        ).delete()
        self.db.commit()
        return count

    def _to_dto(self, db_model: DocumentSummaryCacheDB) -> DocumentSummaryDTO:
        """Convert database model to DTO.

        Args:
            db_model: Database model instance

        Returns:
            DocumentSummaryDTO
        """
        return DocumentSummaryDTO(
            document_id=db_model.document_id,
            channel_id=db_model.channel_id,
            document_name=db_model.document_name,
            summary=db_model.summary,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )
