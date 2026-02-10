# -*- coding: utf-8 -*-
"""Citation API endpoints for inline citations and source navigation."""

import json
from collections.abc import Callable
from datetime import datetime, UTC
from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models.citation import (
    Citation,
    CitationLocation,
    CitedResponse,
    CitationRequest,
    CitationDetail,
)
from src.shared.kernel.contracts.ports.channel import ChannelPort
from src.shared.kernel.contracts.ports.persistence import ChannelRepositoryPort
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.modules.knowledge.application.use_cases.search_with_citations import SearchWithCitationsUseCase
from src.shared.kernel.contracts.ports.citation_search import CitationDTO
from src.modules.knowledge.public import create_search_with_citations_use_case
from src.modules.workspace.public import (
    create_channel_port,
    create_channel_repository_port,
)

router = APIRouter(prefix="/citations", tags=["citations"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


def _format_sse_event(data: dict) -> str:
    """Format data as SSE event."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _convert_citation_dto_to_model(dto: CitationDTO) -> Citation:
    """Convert CitationDTO to Citation model."""
    return Citation(
        index=dto.index,
        source=dto.source,
        content=dto.content,
        location=CitationLocation(
            page=dto.page,
            start_index=dto.start_index,
            end_index=dto.end_index,
        ),
    )


def _convert_to_citation(source: dict, idx: int) -> Citation:
    """Convert raw source dict to Citation model."""
    return Citation(
        index=source.get("index", idx),
        source=source.get("source") or "unknown",
        content=source.get("content") or "",
        location=CitationLocation(
            page=source.get("page"),
            start_index=source.get("start_index"),
            end_index=source.get("end_index"),
        ),
    )


def get_citations_use_case_factory() -> Callable[[], SearchWithCitationsUseCase]:
    """Dependency provider for SearchWithCitationsUseCase factory."""
    return create_search_with_citations_use_case


@router.post(
    "",
    response_model=CitedResponse,
    summary="Query with inline citations",
)
@limiter.limit(RateLimits.CHAT)
def query_with_citations(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID to query")],
    body: CitationRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    use_case_factory: Annotated[
        Callable[[], SearchWithCitationsUseCase],
        Depends(get_citations_use_case_factory),
    ],
) -> CitedResponse:
    """Send a question and get an AI-generated answer with inline citations.

    The response includes:
    - response: Text with inline citation markers [1], [2], etc.
    - response_plain: Text without citation markers
    - citations: Detailed list of citations with source info and navigation data
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Create use case after validation, execute
    use_case = use_case_factory()
    result = use_case.execute(channel_id, body.query)

    if result.error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {result.error}",
        )

    # Convert citations to models
    citations = [
        _convert_citation_dto_to_model(dto)
        for dto in result.citations
    ]

    return CitedResponse(
        query=body.query,
        response=result.response,
        response_plain=result.response_plain,
        citations=citations,
        created_at=datetime.now(UTC),
    )


@router.post(
    "/stream",
    summary="Query with inline citations (streaming)",
)
@limiter.limit(RateLimits.CHAT)
def query_with_citations_stream(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID to query")],
    body: CitationRequest,
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    use_case_factory: Annotated[
        Callable[[], SearchWithCitationsUseCase],
        Depends(get_citations_use_case_factory),
    ],
) -> StreamingResponse:
    """Send a question and get a streaming response with inline citations.

    Returns Server-Sent Events (SSE) with the following event types:
    - content: Text chunks of the response
    - citations: Final response with inline citations and source details
    - done: Signals completion
    - error: Error information if something went wrong
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Update last accessed time
    channel_repo.touch(channel_id)

    # Create use case after validation
    use_case = use_case_factory()

    def generate_stream() -> Generator[str, None, None]:
        """Generate SSE events from UseCase streaming response."""
        for event in use_case.execute_stream(channel_id, body.query):
            event_type = event.get("type")

            if event_type == "content":
                yield _format_sse_event(event)

            elif event_type == "citations":
                # Convert citations to serializable format
                citations = [
                    {
                        "index": src.get("index", idx),
                        "source": src.get("source", "unknown"),
                        "content": src.get("content", ""),
                        "location": {
                            "page": src.get("page"),
                            "start_index": src.get("start_index"),
                            "end_index": src.get("end_index"),
                        },
                    }
                    for idx, src in enumerate(event.get("citations", []), start=1)
                ]
                yield _format_sse_event({
                    "type": "citations",
                    "response_with_citations": event.get("response_with_citations", ""),
                    "citations": citations,
                })

            elif event_type == "done":
                yield _format_sse_event(event)

            elif event_type == "error":
                yield _format_sse_event(event)

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{citation_index}",
    response_model=CitationDetail,
    summary="Get citation details for navigation",
)
@limiter.limit(RateLimits.DEFAULT)
def get_citation_detail(
    request: Request,
    channel_id: Annotated[str, Query(description="Channel ID")],
    citation_index: int,
    source: Annotated[str, Query(description="Source file name")],
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
) -> CitationDetail:
    """Get detailed information about a citation for navigation.

    Returns information needed to navigate to and highlight the source in the
    original document, including:
    - Full quoted text
    - Surrounding context
    - Page/location information
    - Text to highlight
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # For now, return a basic response
    # In a full implementation, this would query the document store
    # to get the actual context around the citation
    return CitationDetail(
        index=citation_index,
        source=source,
        content="",
        context="",
        location=CitationLocation(),
        highlight_text="",
    )
