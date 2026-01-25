# -*- coding: utf-8 -*-
"""Chat API endpoints."""

import json
import re
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
from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import (
    ChannelRepositoryPort,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    SearchHistoryRepositoryPort,
)
from src.application.ports.cache import CachePort
from src.core.database import get_db
from src.infrastructure.di.container import (
    create_channel_port,
    create_channel_repository_port,
    create_chat_history_repository_port,
    create_chat_session_repository_port,
    create_search_history_repository_port,
    create_cache_port,
    create_process_query_use_case,
)
from src.core.rate_limiter import limiter, RateLimits

router = APIRouter(prefix="/channels", tags=["chat"])


def get_channel_port() -> ChannelPort:
    """Get channel port instance."""
    return create_channel_port()


def get_channel_repo_port(db: Session = Depends(get_db)) -> ChannelRepositoryPort:
    """Get channel repository port instance."""
    return create_channel_repository_port(db)


def get_chat_history_port(db: Session = Depends(get_db)) -> ChatHistoryRepositoryPort:
    """Get chat history repository port instance."""
    return create_chat_history_repository_port(db)


def get_chat_session_port(db: Session = Depends(get_db)) -> ChatSessionRepositoryPort:
    """Get chat session repository port instance."""
    return create_chat_session_repository_port(db)


def get_search_history_port(db: Session = Depends(get_db)) -> SearchHistoryRepositoryPort:
    """Get search history repository port instance."""
    return create_search_history_repository_port(db)


def get_cache_port() -> CachePort:
    """Get cache port instance."""
    return create_cache_port()


# =============================================================================
# Query Routing - Determine if RAG is needed
# =============================================================================

# Patterns that indicate simple questions not needing RAG
SIMPLE_QUERY_PATTERNS = [
    # Math expressions
    r"^\d+\s*[\+\-\*\/\^]\s*\d+",  # 1+1, 2*3, etc.
    r"^[\d\s\+\-\*\/\^\(\)\.]+[=\?]?$",  # pure math expression
    # Greetings
    r"^(안녕|하이|헬로|hi|hello|hey)\s*[\?!\.]*$",
    # Simple factual questions
    r"^(오늘|지금)\s*(날짜|시간|몇\s*시)",
    # Yes/no questions about capabilities
    r"^(너|you)\s*(는|are)\s*(뭐|무엇|who|what)",
]

# Keywords that indicate document-related questions (need RAG)
RAG_KEYWORDS = [
    "문서", "파일", "업로드", "자료", "내용", "찾아", "검색",
    "document", "file", "upload", "content", "search", "find",
    "어디", "무엇이", "설명해", "알려줘", "요약", "정리",
    "according to", "based on", "in the", "from the",
]


def needs_rag(query: str) -> bool:
    """Determine if a query needs RAG (document retrieval).

    Args:
        query: The user's question

    Returns:
        True if RAG is needed, False for simple questions
    """
    query_lower = query.lower().strip()

    # Check for RAG keywords first - these always need RAG
    for keyword in RAG_KEYWORDS:
        if keyword in query_lower:
            return True

    # Check for simple query patterns - these don't need RAG
    for pattern in SIMPLE_QUERY_PATTERNS:
        if re.match(pattern, query_lower, re.IGNORECASE):
            return False

    # Default: assume RAG is needed for ambiguous queries
    # This is safer for a document Q&A application
    return True


def _run_agent_chat(
    channel_id: str,
    query: str,
    conversation_history: list[dict[str, str]] | None = None,
    max_iterations: int = 15,
) -> dict:
    """Run the agent to answer a query using documents in the channel.

    Uses Clean Architecture ProcessQueryUseCase which:
    - Abstracts LangGraph via AgentRunnerPort
    - Emits events via AgentEventSinkPort
    - Bridges to legacy dashboard via StateStoreAdapter

    Args:
        channel_id: The channel ID to search in
        query: User's question
        conversation_history: Previous conversation for context
        max_iterations: Maximum agent iterations (default 15)

    Returns:
        Dict with 'response', 'sources', 'iterations', and 'session_id'
    """
    # Use Clean Architecture: ProcessQueryUseCase
    use_case = create_process_query_use_case(
        use_legacy_dashboard=True,
        include_web_search=False,
    )

    result = use_case.execute(
        query=query,
        channel_id=channel_id,
        conversation_history=conversation_history,
        max_iterations=max_iterations,
    )

    # Convert QueryResult to dict for backward compatibility
    return {
        "response": result.response,
        "sources": result.sources,
        "iterations": result.iterations,
        "session_id": result.session_id,
        "error": result.error,
    }


def _run_agent_chat_stream(
    channel_id: str,
    query: str,
    conversation_history: list[dict[str, str]] | None = None,
    max_iterations: int = 15,
) -> Generator[dict, None, dict]:
    """Run the agent with streaming, yielding events for SSE.

    Uses Clean Architecture ProcessQueryUseCase.execute_stream() which:
    - Abstracts LangGraph streaming via AgentRunnerPort
    - Emits events via AgentEventSinkPort
    - Bridges to legacy dashboard via StateStoreAdapter

    Args:
        channel_id: The channel ID to search in
        query: User's question
        conversation_history: Previous conversation for context
        max_iterations: Maximum agent iterations (default 15)

    Yields:
        Event dicts for SSE: {"chunk": text}, {"sources": [...]}, etc.

    Returns:
        Final result dict with 'response', 'sources', 'iterations', etc.
    """
    use_case = create_process_query_use_case(
        use_legacy_dashboard=True,
        include_web_search=False,
    )

    stream_gen = use_case.execute_stream(
        query=query,
        channel_id=channel_id,
        conversation_history=conversation_history,
        max_iterations=max_iterations,
    )

    accumulated_content = ""
    sources = []
    result = None

    try:
        while True:
            event = next(stream_gen)
            event_type = event.get("event")

            if event_type == "content":
                # Yield content chunks for streaming text
                content = event.get("content", "")
                if content:
                    accumulated_content += content
                    yield {"type": "content", "chunk": content}

            elif event_type == "agent_completed":
                # Agent completed - will extract final result after loop
                pass

            elif event_type == "error":
                # Yield error event
                yield {"type": "error", "error": event.get("error", "Unknown error")}

    except StopIteration as e:
        # Generator returned final QueryResult
        result = e.value

    # Build final result dict
    if result:
        sources = result.sources or []
        # Yield sources if any
        if sources:
            yield {"type": "sources", "sources": sources}

        # Yield done signal
        yield {"type": "done"}

        return {
            "response": result.response,
            "sources": sources,
            "iterations": result.iterations,
            "session_id": result.session_id,
            "error": result.error,
        }
    else:
        yield {"type": "error", "error": "No result from agent"}
        return {
            "response": accumulated_content or "No response generated.",
            "sources": [],
            "iterations": 0,
            "session_id": None,
            "error": "No result from agent",
        }


def _format_sse_event(data: dict | str) -> str:
    """Format data as SSE event."""
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_conversation_history(
    chat_history_port: ChatHistoryRepositoryPort,
    session_id: str | None,
) -> list[dict[str, str]]:
    """Get conversation history from session for context."""
    if not session_id:
        return []

    messages = chat_history_port.get_session_history(session_id)
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    chat_history: Annotated[ChatHistoryRepositoryPort, Depends(get_chat_history_port)],
    session_repo: Annotated[ChatSessionRepositoryPort, Depends(get_chat_session_port)],
    search_history: Annotated[SearchHistoryRepositoryPort, Depends(get_search_history_port)],
    cache: Annotated[CachePort, Depends(get_cache_port)],
) -> ChatResponse:
    """Send a question and get an AI-generated answer.

    The response includes grounding sources from the documents in the channel.
    Supports multi-turn conversations when session_id is provided in the request body.
    Responses are cached for 1 hour when no session is used.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get or create local channel metadata
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        # Create if not exists (for channels created before DB integration)
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=channel.display_name or "unknown",
        )
    else:
        # Update last accessed time
        channel_repo.touch(channel_id)

    # Handle session for multi-turn conversation
    session_dto = None
    session_id_response = None

    if body.session_id:
        session_dto, _ = session_repo.get_or_create(
            channel_id=channel_meta.id,
            session_id=body.session_id,
        )
        session_id_response = session_dto.session_id if session_dto else body.session_id

    # Get conversation history for context
    conversation_history = _get_conversation_history(chat_history, session_id_response)

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
        # Use LangGraph agent for RAG
        result = _run_agent_chat(
            channel_id=channel_id,
            query=body.query,
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

        # Handle response that might be a list (multipart message from LangGraph)
        response_content = result.get("response", "")
        if isinstance(response_content, list):
            response_content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in response_content
            )

        response = ChatResponse(
            query=body.query,
            response=response_content,
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

    # Save to search history (using database ID)
    search_history.add_or_update(channel_meta.id, body.query)

    # Add user message
    chat_history.add_message(
        channel_id=channel_meta.id,
        role="user",
        content=body.query,
        sources=None,
        session_id=session_id_response,
    )

    # Add assistant message
    chat_history.add_message(
        channel_id=channel_meta.id,
        role="assistant",
        content=response.response,
        sources=[{"source": s.source, "content": s.content} for s in sources],
        session_id=session_id_response,
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    chat_history: Annotated[ChatHistoryRepositoryPort, Depends(get_chat_history_port)],
    session_repo: Annotated[ChatSessionRepositoryPort, Depends(get_chat_session_port)],
    search_history: Annotated[SearchHistoryRepositoryPort, Depends(get_search_history_port)],
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
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get or create local channel metadata
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=channel.display_name or "unknown",
        )
    else:
        channel_repo.touch(channel_id)

    # Handle session for multi-turn conversation
    session_dto = None
    session_id_response = None

    if body.session_id:
        session_dto, _ = session_repo.get_or_create(
            channel_id=channel_meta.id,
            session_id=body.session_id,
        )
        session_id_response = session_dto.session_id if session_dto else body.session_id

    # Get conversation history for context
    conversation_history = _get_conversation_history(chat_history, session_id_response)

    def generate_stream() -> Generator[str, None, None]:
        """Generate SSE events using Clean Architecture ProcessQueryUseCase.

        Dashboard state updates are handled automatically by the UseCase
        via StateStoreAdapter (AgentEventSinkPort implementation).
        """
        full_response = ""
        all_sources = []

        # Send session ID first if available
        if session_id_response:
            yield _format_sse_event({"session_id": session_id_response})

        # Use Clean Architecture streaming
        stream_gen = _run_agent_chat_stream(
            channel_id=channel_id,
            query=body.query,
            conversation_history=conversation_history,
        )

        final_result = None
        try:
            while True:
                event = next(stream_gen)
                event_type = event.get("type")

                if event_type == "content":
                    chunk = event.get("chunk", "")
                    full_response += chunk
                    # Send in format frontend expects: {"chunk": "..."}
                    yield _format_sse_event({"chunk": chunk})

                elif event_type == "sources":
                    all_sources = event.get("sources", [])
                    # Send sources in format frontend expects: {"sources": [...]}
                    yield _format_sse_event({"sources": all_sources})

                elif event_type == "done":
                    # Store in DB before signaling done (using database ID)
                    search_history.add_or_update(channel_meta.id, body.query)

                    # Add user message
                    chat_history.add_message(
                        channel_id=channel_meta.id,
                        role="user",
                        content=body.query,
                        sources=None,
                        session_id=session_id_response,
                    )

                    # Add assistant message
                    chat_history.add_message(
                        channel_id=channel_meta.id,
                        role="assistant",
                        content=full_response,
                        sources=all_sources,
                        session_id=session_id_response,
                    )

                    # Send done signal in format frontend expects: [DONE]
                    yield _format_sse_event("[DONE]")

                elif event_type == "error":
                    yield _format_sse_event({"error": event.get("error", "Unknown error")})

        except StopIteration as e:
            # Generator returned final result
            final_result = e.value

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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    chat_history: Annotated[ChatHistoryRepositoryPort, Depends(get_chat_history_port)],
    limit: Annotated[int, Query(description="Maximum number of messages", ge=1, le=500)] = 100,
) -> ChatHistory:
    """Get the chat history for a channel."""
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get channel metadata
    channel_meta = channel_repo.get_by_gemini_id(channel_id)

    if not channel_meta:
        # No local metadata means no chat history
        return ChatHistory(channel_id=channel_id, messages=[], total=0)

    # Get messages from DB (returns DTOs) - use database ID
    msg_dtos = chat_history.get_history(channel_meta.id, limit=limit)

    # Convert to ChatMessage models
    messages = [
        ChatMessage(
            role=msg.role,
            content=msg.content,
            sources=[
                GroundingSource(source=s.get("source", ""), content=s.get("content", ""))
                for s in msg.sources
            ],
            created_at=msg.created_at,
        )
        for msg in msg_dtos
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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    chat_history: Annotated[ChatHistoryRepositoryPort, Depends(get_chat_history_port)],
):
    """Clear the chat history for a channel."""
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get channel metadata
    channel_meta = channel_repo.get_by_gemini_id(channel_id)

    if channel_meta:
        # Clear chat history from DB (use database ID)
        chat_history.clear_history(channel_meta.id)

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
    channel_port: Annotated[ChannelPort, Depends(get_channel_port)],
    channel_repo: Annotated[ChannelRepositoryPort, Depends(get_channel_repo_port)],
    session_repo: Annotated[ChatSessionRepositoryPort, Depends(get_chat_session_port)],
) -> ChatSession:
    """Create a new chat session for multi-turn conversation.

    Returns a session_id that can be used in subsequent chat requests
    to maintain conversation context.
    """
    # Validate channel exists
    channel = channel_port.get_channel(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel not found: {channel_id}",
        )

    # Get or create local channel metadata
    channel_meta = channel_repo.get_by_gemini_id(channel_id)
    if not channel_meta:
        channel_meta = channel_repo.create(
            gemini_store_id=channel_id,
            name=channel.display_name or "unknown",
        )

    # Create new session
    session_dto = session_repo.create(
        channel_id=channel_meta.id,
        context_window=body.context_window,
    )

    return ChatSession(
        session_id=session_dto.session_id,
        channel_id=channel_id,
        created_at=session_dto.created_at,
        last_activity_at=session_dto.last_activity_at,
        context_window=session_dto.context_window,
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
    session_repo: Annotated[ChatSessionRepositoryPort, Depends(get_chat_session_port)],
) -> ChatSession:
    """Get information about a chat session."""
    session_dto = session_repo.get_by_session_id(session_id)

    if not session_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    # Check if expired
    if session_repo.is_expired(session_id):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Session has expired: {session_id}",
        )

    return ChatSession(
        session_id=session_dto.session_id,
        channel_id=channel_id,  # Use path param (gemini_store_id string), not DTO's database id
        created_at=session_dto.created_at,
        last_activity_at=session_dto.last_activity_at,
        context_window=session_dto.context_window,
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
    session_repo: Annotated[ChatSessionRepositoryPort, Depends(get_chat_session_port)],
    chat_history: Annotated[ChatHistoryRepositoryPort, Depends(get_chat_history_port)],
    limit: Annotated[int, Query(description="Maximum number of messages", ge=1, le=500)] = 100,
) -> ChatHistory:
    """Get the chat history for a specific session."""
    session_dto = session_repo.get_by_session_id(session_id)

    if not session_dto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    # Get messages from DB (returns DTOs)
    msg_dtos = chat_history.get_session_history(session_id, limit=limit)

    # Convert to ChatMessage models
    messages = [
        ChatMessage(
            role=msg.role,
            content=msg.content,
            sources=[
                GroundingSource(source=s.get("source", ""), content=s.get("content", ""))
                for s in msg.sources
            ],
            created_at=msg.created_at,
        )
        for msg in msg_dtos
    ]

    return ChatHistory(
        channel_id=channel_id,  # Use path param (gemini_store_id string), not DTO's database id
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
    session_repo: Annotated[ChatSessionRepositoryPort, Depends(get_chat_session_port)],
):
    """Delete a chat session and its associated messages."""
    if not session_repo.delete(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    return None
