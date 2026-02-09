# -*- coding: utf-8 -*-
"""Chat API endpoints (thin controller).

All business logic is delegated to ChatUseCase.
This router handles HTTP concerns: request parsing, response formatting,
SSE streaming, and error code translation.
"""

import json
from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistory,
    ChatMessage,
    ChatSession,
    CreateSessionRequest,
    GroundingSource,
)
from src.application.use_cases.chat import ChatUseCase, ChatAgentError
from src.application.use_cases.exceptions import (
    ChannelNotFoundError,
    SessionNotFoundError,
    SessionExpiredError,
)
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/channels", tags=["chat"])


def get_chat_use_case(
    db: Session = Depends(get_db),
) -> ChatUseCase:
    """Get chat use case instance."""
    from src.infrastructure.di.container import create_chat_use_case
    return create_chat_use_case(db)


def _format_sse_event(data: dict | str) -> str:
    """Format data as SSE event."""
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sources_to_grounding(sources):
    """Convert SourceDTOs to GroundingSource models."""
    return [
        GroundingSource(
            source=s.source,
            content=s.content,
            url=s.url,
            source_type=s.source_type,
        )
        for s in sources
    ]


def _messages_to_chat_messages(messages):
    """Convert ChatMessageInfoDTOs to ChatMessage models."""
    return [
        ChatMessage(
            role=msg.role,
            content=msg.content,
            sources=_sources_to_grounding(msg.sources),
            created_at=msg.created_at,
        )
        for msg in messages
    ]


@router.post(
    "/{channel_id:path}/chat",
    response_model=ChatResponse,
    summary="Send a chat message",
)
@limiter.limit(RateLimits.CHAT)
def send_message(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID to query")],
    body: ChatRequest,
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
) -> ChatResponse:
    """Send a question and get an AI-generated answer.

    The response includes grounding sources from the documents in the channel.
    Supports multi-turn conversations when session_id is provided in the request body.
    Responses are cached for 1 hour when no session is used.
    """
    try:
        result = use_case.send_message(channel_id, body.query, body.session_id)
        return ChatResponse(
            query=result.query,
            response=result.response,
            sources=_sources_to_grounding(result.sources),
            session_id=result.session_id,
            session_renewed=result.session_renewed,
            old_session_id=result.old_session_id,
            created_at=result.created_at,
        )
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    except ChatAgentError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{channel_id:path}/chat/stream",
    summary="Send a chat message with streaming response",
)
@limiter.limit(RateLimits.CHAT)
def send_message_stream(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID to query")],
    body: ChatRequest,
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
) -> StreamingResponse:
    """Send a question and get a streaming AI-generated answer.

    Returns Server-Sent Events (SSE) with the following event types:
    - content: Text chunks of the response
    - sources: Grounding sources from documents
    - session: Session ID for multi-turn (if session_id was provided)
    - done: Signals completion
    - error: Error information if something went wrong
    """
    try:
        session_id_response, session_renewed, old_session_id, stream_gen = use_case.prepare_stream(
            channel_id, body.query, body.session_id
        )
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    def generate_sse() -> Generator[str, None, None]:
        """Generate SSE events from use case stream."""
        if session_id_response:
            session_event = {"session_id": session_id_response}
            if session_renewed:
                session_event["session_renewed"] = True
                if old_session_id:
                    session_event["old_session_id"] = old_session_id
            yield _format_sse_event(session_event)

        try:
            while True:
                event = next(stream_gen)
                event_type = event.get("type")

                if event_type == "content":
                    yield _format_sse_event({"chunk": event.get("chunk", "")})
                elif event_type == "sources":
                    yield _format_sse_event({"sources": event.get("sources", [])})
                elif event_type == "done":
                    yield _format_sse_event("[DONE]")
                elif event_type == "error":
                    yield _format_sse_event({"error": event.get("error", "Unknown error")})
        except StopIteration:
            pass

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{channel_id:path}/chat/history",
    response_model=ChatHistory,
    summary="Get chat history",
)
@limiter.limit(RateLimits.DEFAULT)
def get_chat_history(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID")],
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
    limit: Annotated[int, Query(description="Maximum number of messages", ge=1, le=500)] = 100,
) -> ChatHistory:
    """Get the chat history for a channel."""
    try:
        result = use_case.get_history(channel_id, limit=limit)
        return ChatHistory(
            channel_id=result.channel_id,
            messages=_messages_to_chat_messages(result.messages),
            total=result.total,
        )
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )


@router.delete(
    "/{channel_id:path}/chat/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear chat history",
)
@limiter.limit(RateLimits.DEFAULT)
def clear_chat_history(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID")],
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
):
    """Clear the chat history for a channel."""
    try:
        use_case.clear_history(channel_id)
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )
    return None


# ========== Session Management Endpoints ==========


@router.post(
    "/{channel_id:path}/chat/sessions",
    response_model=ChatSession,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
@limiter.limit(RateLimits.DEFAULT)
def create_session(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID")],
    body: CreateSessionRequest,
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
) -> ChatSession:
    """Create a new chat session for multi-turn conversation.

    Returns a session_id that can be used in subsequent chat requests
    to maintain conversation context.
    """
    try:
        result = use_case.create_session(channel_id, body.context_window)
        return ChatSession(
            session_id=result.session_id,
            channel_id=result.channel_id,
            created_at=result.created_at,
            last_activity_at=result.last_activity_at,
            context_window=result.context_window,
        )
    except ChannelNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )


@router.get(
    "/{channel_id:path}/chat/sessions/{session_id}",
    response_model=ChatSession,
    summary="Get session information",
)
@limiter.limit(RateLimits.DEFAULT)
def get_session(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID")],
    session_id: str,
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
) -> ChatSession:
    """Get information about a chat session."""
    try:
        result = use_case.get_session(channel_id, session_id)
        return ChatSession(
            session_id=result.session_id,
            channel_id=result.channel_id,
            created_at=result.created_at,
            last_activity_at=result.last_activity_at,
            context_window=result.context_window,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    except SessionExpiredError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Session has expired: {session_id}",
        )


@router.get(
    "/{channel_id:path}/chat/sessions/{session_id}/history",
    response_model=ChatHistory,
    summary="Get session chat history",
)
@limiter.limit(RateLimits.DEFAULT)
def get_session_history(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID")],
    session_id: str,
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
    limit: Annotated[int, Query(description="Maximum number of messages", ge=1, le=500)] = 100,
) -> ChatHistory:
    """Get the chat history for a specific session."""
    try:
        result = use_case.get_session_history(channel_id, session_id, limit=limit)
        return ChatHistory(
            channel_id=result.channel_id,
            messages=_messages_to_chat_messages(result.messages),
            total=result.total,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )


@router.delete(
    "/{channel_id:path}/chat/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
)
@limiter.limit(RateLimits.DEFAULT)
def delete_session(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID")],
    session_id: str,
    use_case: Annotated[ChatUseCase, Depends(get_chat_use_case)],
):
    """Delete a chat session and its associated messages."""
    try:
        use_case.delete_session(channel_id, session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return None
