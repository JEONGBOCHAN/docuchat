# -*- coding: utf-8 -*-
"""
Document Domain Entities.

Pure Python representations of document-related business concepts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DocumentChunk:
    """A chunk of a document used for retrieval.

    Attributes:
        content: The text content of the chunk
        source: Source document identifier
        chunk_index: Position in the original document
        score: Relevance score (when retrieved)
        metadata: Additional chunk metadata
    """

    content: str
    source: str
    chunk_index: int = 0
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    """A document in the system.

    Attributes:
        id: Unique document identifier
        name: Display name of the document
        channel_id: The channel this document belongs to
        content_type: MIME type of the document
        size_bytes: File size in bytes
        created_at: When the document was uploaded
        chunks: Document chunks for retrieval (if processed)
        metadata: Additional document metadata
    """

    id: str
    name: str
    channel_id: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    chunks: list[DocumentChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pdf(self) -> bool:
        """Check if document is a PDF."""
        return self.content_type == "application/pdf"

    @property
    def is_text(self) -> bool:
        """Check if document is plain text."""
        return self.content_type.startswith("text/")
