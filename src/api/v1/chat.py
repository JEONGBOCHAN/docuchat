# -*- coding: utf-8 -*-
"""Chat API endpoints."""

import json
from datetime import datetime, UTC
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
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.core.rate_limiter import limiter, RateLimits
from src.services.channel_repository import (
    ChannelRepository,
    ChatHistoryRepository,
    ChatSessionRepository,
)
from src.services.cache_service import CacheService, get_cache_service
from src.services.search_repository import SearchHistoryRepository
from src.workflows import run_rag_agent

router = APIRouter(prefix="/channels", tags=["chat"])


def _run_agent_chat(
    channel_id: str,
    query: str,
    conversation_history: list[dict[str, str]] | None = None,
    max_iterations: int = 3,
) -> dict:
    """Run the LangGraph agent to answer a query using documents in the channel.

    Args:
        channel_id: The channel ID to search in
        query: User's question
        conversation_history: Previous conversation for context
        max_iterations: Maximum agent iterations (default 3)

    Returns:
        Dict with 'response', 'sources', and 'iterations'
    """
    return run_rag_agent(
        channel_id=channel_id,
        query=query,
        conversation_history=conversation_history,
        max_iterations=max_iterations,
    )


def _format_sse_event(data: dict | str) -> str:
    """Format data as SSE event."""
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_conversation_history(
    chat_repo: ChatHistoryRepository,
    session,
) -> list[dict[str, str]]:
    """Get conversation history from session for context."""
    if not session:
        return []

    messages = chat_repo.get_session_history(session)
    return [{"role": msg.role, "content": msg.content} for msg in messages]


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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> ChatResponse:
    """Send a question and get an AI-generated answer.

    The response includes grounding sources from the documents in the channel.
    Supports multi-turn conversations when session_id is provided in the request body.
    Responses are cached for 1 hour when no session is used.
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get or create local channel metadata
    channel_repo = ChannelRepository(db)
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        # Create if not exists (for channels created before DB integration)
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=store.get("display_name", "unknown"),
        )
    else:
        # Update last accessed time
        channel_repo.touch(channel_id)

    # Handle session for multi-turn conversation
    session_repo = ChatSessionRepository(db)
    chat_repo = ChatHistoryRepository(db)
    session = None
    session_id_response = None

    if body.session_id:
        session, created = session_repo.get_or_create(
            channel=channel_meta,
            session_id=body.session_id,
        )
        session_id_response = session.session_id

    # Get conversation history for context
    conversation_history = _get_conversation_history(chat_repo, session)

    # Check cache for non-session queries
    cached_response = None
    use_cache = not body.session_id  # Only cache when no session

    if use_cache:
        cached_response = cache.get_chat_response(channel_id, body.query)

    if cached_response:
        # Return cached response
        sources = [
            GroundingSource(
                source=s.get("source", "unknown"),
                content=s.get("content", ""),
            )
            for s in cached_response.get("sources", [])
        ]

        response = ChatResponse(
            query=body.query,
            response=cached_response.get("response", ""),
            sources=sources,
            session_id=None,
            created_at=datetime.now(UTC),
        )
    else:
        # Use agent or direct search based on request
        if body.use_agent:
            # Use LangGraph agentic loop (ReAct pattern)
            result = _run_agent_chat(
                channel_id=channel_id,
                query=body.query,
                conversation_history=conversation_history,
                max_iterations=3,
            )
        else:
            # Direct search and answer (legacy mode)
            result = gemini.search_and_answer(
                channel_id,
                body.query,
                conversation_history=conversation_history,
            )

        if "error" in result and result["error"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate response: {result['error']}",
            )

        # Convert sources to GroundingSource models
        sources = [
            GroundingSource(
                source=s.get("source", "unknown"),
                content=s.get("content", ""),
            )
            for s in result.get("sources", [])
        ]

        response = ChatResponse(
            query=body.query,
            response=result.get("response", ""),
            sources=sources,
            session_id=session_id_response,
            created_at=datetime.now(UTC),
        )

        # Cache the response for non-session queries
        if use_cache:
            cache.set_chat_response(
                channel_id,
                body.query,
                {
                    "response": response.response,
                    "sources": [{"source": s.source, "content": s.content} for s in sources],
                },
            )

    # Save to search history
    search_repo = SearchHistoryRepository(db)
    search_repo.add_or_update(channel_meta, body.query)

    # Add user message
    chat_repo.add_message(
        channel=channel_meta,
        role="user",
        content=body.query,
        sources=None,
        session=session,
    )

    # Add assistant message
    chat_repo.add_message(
        channel=channel_meta,
        role="assistant",
        content=response.response,
        sources=[{"source": s.source, "content": s.content} for s in sources],
        session=session,
    )

    return response


@router.post(
    "/{channel_id:path}/chat/stream",
    summary="Send a chat message with streaming response",
)
@limiter.limit(RateLimits.CHAT)
def send_message_stream(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID to query")],
    body: ChatRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    """Send a question and get a streaming AI-generated answer.

    Returns Server-Sent Events (SSE) with the following event types:
    - content: Text chunks of the response
    - sources: Grounding sources from documents
    - session: Session ID for multi-turn (if session_id was provided)
    - done: Signals completion
    - error: Error information if something went wrong
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get or create local channel metadata
    channel_repo = ChannelRepository(db)
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=store.get("display_name", "unknown"),
        )
    else:
        channel_repo.touch(channel_id)

    # Handle session for multi-turn conversation
    session_repo = ChatSessionRepository(db)
    chat_repo = ChatHistoryRepository(db)
    session = None
    session_id_response = None

    if body.session_id:
        session, created = session_repo.get_or_create(
            channel=channel_meta,
            session_id=body.session_id,
        )
        session_id_response = session.session_id

    # Get conversation history for context
    conversation_history = _get_conversation_history(chat_repo, session)

    def generate_stream() -> Generator[str, None, None]:
        """Generate SSE events from Gemini streaming response."""
        full_response = ""
        all_sources = []

        # Send session ID first if available
        if session_id_response:
            yield _format_sse_event({"session_id": session_id_response})

        for event in gemini.search_and_answer_stream(
            channel_id,
            body.query,
            conversation_history=conversation_history,
        ):
            event_type = event.get("type")

            if event_type == "content":
                text = event.get("text", "")
                full_response += text
                # Send in format frontend expects: {"chunk": "..."}
                yield _format_sse_event({"chunk": text})

            elif event_type == "sources":
                all_sources = event.get("sources", [])
                # Send sources in format frontend expects: {"sources": [...]}
                yield _format_sse_event({"sources": all_sources})

            elif event_type == "done":
                # Store in DB before signaling done
                # Save to search history
                search_repo = SearchHistoryRepository(db)
                search_repo.add_or_update(channel_meta, body.query)

                # Add user message
                chat_repo.add_message(
                    channel=channel_meta,
                    role="user",
                    content=body.query,
                    sources=None,
                    session=session,
                )

                # Add assistant message
                chat_repo.add_message(
                    channel=channel_meta,
                    role="assistant",
                    content=full_response,
                    sources=all_sources,
                    session=session,
                )

                # Send done signal in format frontend expects: [DONE]
                yield _format_sse_event("[DONE]")

            elif event_type == "error":
                yield _format_sse_event({"error": event.get("error", "Unknown error")})

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
    "/{channel_id:path}/chat/history",
    response_model=ChatHistory,
    summary="Get chat history",
)
@limiter.limit(RateLimits.DEFAULT)
def get_chat_history(
    request: Request,
    channel_id: Annotated[str, Path(description="Channel ID")],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(description="Maximum number of messages", ge=1, le=500)] = 100,
) -> ChatHistory:
    """Get the chat history for a channel."""
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get channel metadata
    channel_repo = ChannelRepository(db)
    channel_meta = channel_repo.get_by_gemini_id(channel_id)

    if not channel_meta:
        # No local metadata means no chat history
        return ChatHistory(channel_id=channel_id, messages=[], total=0)

    # Get messages from DB
    chat_repo = ChatHistoryRepository(db)
    db_messages = chat_repo.get_history(channel_meta, limit=limit)

    # Convert to ChatMessage models
    messages = [
        ChatMessage(
            role=msg.role,
            content=msg.content,
            sources=[
                GroundingSource(source=s.get("source", ""), content=s.get("content", ""))
                for s in json.loads(msg.sources_json)
            ],
            created_at=msg.created_at,
        )
        for msg in db_messages
    ]

    return ChatHistory(
        channel_id=channel_id,
        messages=messages,
        total=len(messages),
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
):
    """Clear the chat history for a channel."""
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get channel metadata
    channel_repo = ChannelRepository(db)
    channel_meta = channel_repo.get_by_gemini_id(channel_id)

    if channel_meta:
        # Clear chat history from DB
        chat_repo = ChatHistoryRepository(db)
        chat_repo.clear_history(channel_meta)

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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatSession:
    """Create a new chat session for multi-turn conversation.

    Returns a session_id that can be used in subsequent chat requests
    to maintain conversation context.
    """
    # Validate channel exists
    store = gemini.get_store(channel_id)
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get or create local channel metadata
    channel_repo = ChannelRepository(db)
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=store.get("display_name", "unknown"),
        )

    # Create new session
    session_repo = ChatSessionRepository(db)
    session = session_repo.create(
        channel=channel_meta,
        context_window=body.context_window,
    )

    return ChatSession(
        session_id=session.session_id,
        channel_id=channel_id,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        context_window=session.context_window,
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
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatSession:
    """Get information about a chat session."""
    session_repo = ChatSessionRepository(db)
    session = session_repo.get_by_session_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    # Check if expired
    if session_repo.is_expired(session):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Session has expired: {session_id}",
        )

    # Get channel gemini_store_id
    channel_id = session.channel.gemini_store_id

    return ChatSession(
        session_id=session.session_id,
        channel_id=channel_id,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        context_window=session.context_window,
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
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(description="Maximum number of messages", ge=1, le=500)] = 100,
) -> ChatHistory:
    """Get the chat history for a specific session."""
    session_repo = ChatSessionRepository(db)
    session = session_repo.get_by_session_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    # Get messages from DB
    chat_repo = ChatHistoryRepository(db)
    db_messages = chat_repo.get_session_history(session, limit=limit)

    # Get channel gemini_store_id
    channel_id = session.channel.gemini_store_id

    # Convert to ChatMessage models
    messages = [
        ChatMessage(
            role=msg.role,
            content=msg.content,
            sources=[
                GroundingSource(source=s.get("source", ""), content=s.get("content", ""))
                for s in json.loads(msg.sources_json)
            ],
            created_at=msg.created_at,
        )
        for msg in db_messages
    ]

    return ChatHistory(
        channel_id=channel_id,
        messages=messages,
        total=len(messages),
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
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a chat session and its associated messages."""
    session_repo = ChatSessionRepository(db)

    if not session_repo.delete(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    return None
