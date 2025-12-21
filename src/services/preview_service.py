# -*- coding: utf-8 -*-
"""Document preview service for text extraction and display."""

import re
from functools import lru_cache

from sqlalchemy.orm import Session

from src.models.db_models import DocumentPreviewCacheDB
from src.models.preview import (
    DocumentPreviewResponse,
    TextHighlight,
    SourceLocation,
    SourceLocationResponse,
)
from src.services.gemini import GeminiService


# Default page size in characters
DEFAULT_PAGE_SIZE = 2000


class PreviewService:
    """Service for document preview functionality."""

    def __init__(self, db: Session, gemini: GeminiService):
        """Initialize preview service.

        Args:
            db: Database session
            gemini: Gemini service instance
        """
        self._db = db
        self._gemini = gemini

    def get_preview(
        self,
        channel_id: str,
        document_id: str,
        filename: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        search_term: str | None = None,
    ) -> DocumentPreviewResponse:
        """Get document preview with pagination and optional highlighting.

        Args:
            channel_id: Channel (store) ID
            document_id: Document file ID
            filename: Original filename
            page: Page number (1-based)
            page_size: Characters per page
            search_term: Optional search term to highlight

        Returns:
            Document preview response with content and highlights
        """
        # Get or create cache
        cached = self._get_cached_preview(document_id)

        if not cached:
            # Extract text using Gemini
            content = self._extract_text(channel_id, filename)
            cached = self._cache_preview(document_id, channel_id, filename, content)

        # Calculate pagination
        total_chars = cached.total_characters
        total_pages = max(1, (total_chars + page_size - 1) // page_size)

        # Validate page number
        page = max(1, min(page, total_pages))

        # Extract page content
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_chars)
        page_content = cached.content[start_idx:end_idx]

        # Find highlights if search term provided
        highlights = []
        if search_term:
            highlights = self._find_highlights(page_content, search_term)

        return DocumentPreviewResponse(
            document_id=document_id,
            filename=cached.filename,
            total_pages=total_pages,
            total_characters=total_chars,
            current_page=page,
            page_size=page_size,
            content=page_content,
            highlights=highlights,
            has_next=page < total_pages,
            has_previous=page > 1,
            cached_at=cached.created_at,
        )

    def find_source_location(
        self,
        channel_id: str,
        document_id: str,
        filename: str,
        source_text: str,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> SourceLocationResponse:
        """Find the location of a source citation in a document.

        Args:
            channel_id: Channel (store) ID
            document_id: Document file ID
            filename: Original filename
            source_text: The source text to find
            page_size: Characters per page for page calculation

        Returns:
            Source location response with page and position
        """
        # Get or create cache
        cached = self._get_cached_preview(document_id)

        if not cached:
            content = self._extract_text(channel_id, filename)
            cached = self._cache_preview(document_id, channel_id, filename, content)

        # Find the source text in content
        position = cached.content.lower().find(source_text.lower())

        if position == -1:
            # Try partial match (first 50 chars of source)
            partial = source_text[:50] if len(source_text) > 50 else source_text
            position = cached.content.lower().find(partial.lower())

        if position == -1:
            return SourceLocationResponse(found=False, location=None)

        # Calculate page number
        page_number = (position // page_size) + 1

        # Get context around the match
        context_start = max(0, position - 100)
        context_end = min(len(cached.content), position + len(source_text) + 100)
        context = cached.content[context_start:context_end]

        # Find highlights in context
        highlights = self._find_highlights(context, source_text)

        return SourceLocationResponse(
            found=True,
            location=SourceLocation(
                document_id=document_id,
                filename=filename,
                page_number=page_number,
                position=position,
                context=context,
                highlights=highlights,
            ),
        )

    def invalidate_cache(self, document_id: str) -> bool:
        """Invalidate cached preview for a document.

        Args:
            document_id: Document file ID

        Returns:
            True if cache was invalidated
        """
        cached = self._db.query(DocumentPreviewCacheDB).filter(
            DocumentPreviewCacheDB.document_id == document_id
        ).first()

        if cached:
            self._db.delete(cached)
            self._db.commit()
            return True
        return False

    def invalidate_channel_cache(self, channel_id: str) -> int:
        """Invalidate all cached previews for a channel.

        Args:
            channel_id: Channel (store) ID

        Returns:
            Number of caches invalidated
        """
        count = self._db.query(DocumentPreviewCacheDB).filter(
            DocumentPreviewCacheDB.channel_id == channel_id
        ).delete()
        self._db.commit()
        return count

    def _get_cached_preview(self, document_id: str) -> DocumentPreviewCacheDB | None:
        """Get cached preview from database.

        Args:
            document_id: Document file ID

        Returns:
            Cached preview or None
        """
        return self._db.query(DocumentPreviewCacheDB).filter(
            DocumentPreviewCacheDB.document_id == document_id
        ).first()

    def _cache_preview(
        self,
        document_id: str,
        channel_id: str,
        filename: str,
        content: str,
    ) -> DocumentPreviewCacheDB:
        """Cache document preview content.

        Args:
            document_id: Document file ID
            channel_id: Channel (store) ID
            filename: Original filename
            content: Extracted text content

        Returns:
            Created cache entry
        """
        cache = DocumentPreviewCacheDB(
            document_id=document_id,
            channel_id=channel_id,
            filename=filename,
            content=content,
            total_characters=len(content),
        )
        self._db.add(cache)
        self._db.commit()
        self._db.refresh(cache)
        return cache

    def _extract_text(self, channel_id: str, filename: str) -> str:
        """Extract text content from document using Gemini.

        Args:
            channel_id: Channel (store) ID
            filename: Document filename

        Returns:
            Extracted text content
        """
        prompt = f"""Extract and return the complete text content from the document "{filename}".

Instructions:
- Return ONLY the raw text content from the document
- Preserve the original structure (paragraphs, line breaks)
- Do not add any commentary, headers, or formatting
- Do not summarize - return the full text content
- If the document has multiple pages, include all pages
- Separate sections with blank lines

Return the extracted text content now:"""

        result = self._gemini.search_and_answer(
            store_name=channel_id,
            query=prompt,
            model="gemini-2.5-flash",
        )

        if result.get("error"):
            # Return error message as content for now
            return f"[Error extracting content: {result['error']}]"

        return result.get("response", "[No content extracted]")

    def _find_highlights(
        self,
        text: str,
        search_term: str,
    ) -> list[TextHighlight]:
        """Find all occurrences of search term in text.

        Args:
            text: Text to search in
            search_term: Term to find

        Returns:
            List of highlights with positions
        """
        highlights = []
        if not search_term:
            return highlights

        # Case-insensitive search
        pattern = re.compile(re.escape(search_term), re.IGNORECASE)

        for match in pattern.finditer(text):
            highlights.append(
                TextHighlight(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                )
            )

        return highlights


@lru_cache
def get_preview_service_factory():
    """Factory for creating preview service instances."""
    from src.services.gemini import get_gemini_service
    return get_gemini_service()


def get_preview_service(db: Session) -> PreviewService:
    """Get preview service instance with injected dependencies.

    Args:
        db: Database session

    Returns:
        PreviewService instance
    """
    gemini = get_preview_service_factory()
    return PreviewService(db, gemini)
