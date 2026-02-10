# -*- coding: utf-8 -*-
"""Workspace module document summary cache repository."""

from datetime import datetime, UTC

from src.shared.kernel.contracts.ports.document_summary import (
    DocumentSummaryCachePort,
    DocumentSummaryDTO,
)
from src.modules.workspace.infrastructure.persistence.models import DocumentSummaryCacheDB


class DocumentSummaryCacheRepository(DocumentSummaryCachePort):
    """Repository for document summary cache operations.

    Implements DocumentSummaryCachePort for persistence layer.
    Stores document summaries for efficient retrieval during chat.
    """

    def __init__(self, db):
        self.db = db

    def save(self, summary: DocumentSummaryDTO) -> DocumentSummaryDTO:
        existing = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.document_id == summary.document_id
        ).first()

        if existing:
            existing.channel_id = summary.channel_id
            existing.document_name = summary.document_name
            existing.summary = summary.summary
            existing.updated_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(existing)
            return self._to_dto(existing)

        row = DocumentSummaryCacheDB(
            document_id=summary.document_id,
            channel_id=summary.channel_id,
            document_name=summary.document_name,
            summary=summary.summary,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_dto(row)

    def get_by_document_id(self, document_id: str) -> DocumentSummaryDTO | None:
        row = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.document_id == document_id
        ).first()
        return self._to_dto(row) if row else None

    def get_by_channel(self, channel_id: str, limit: int = 10) -> list[DocumentSummaryDTO]:
        rows = (
            self.db.query(DocumentSummaryCacheDB)
            .filter(DocumentSummaryCacheDB.channel_id == channel_id)
            .order_by(DocumentSummaryCacheDB.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_dto(r) for r in rows]

    def delete_by_document_id(self, document_id: str) -> bool:
        count = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.document_id == document_id
        ).delete()
        self.db.commit()
        return count > 0

    def delete_by_channel(self, channel_id: str) -> int:
        count = self.db.query(DocumentSummaryCacheDB).filter(
            DocumentSummaryCacheDB.channel_id == channel_id
        ).delete()
        self.db.commit()
        return count

    @staticmethod
    def _to_dto(row: DocumentSummaryCacheDB) -> DocumentSummaryDTO:
        return DocumentSummaryDTO(
            document_id=row.document_id,
            channel_id=row.channel_id,
            document_name=row.document_name,
            summary=row.summary,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
