# -*- coding: utf-8 -*-
"""Chat API endpoints."""

import json
from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistory,
    ChatMessage,
    GroundingSource,
)
from src.services.gemini import GeminiService, get_gemini_service
from src.core.database import get_db
from src.services.channel_repository import ChannelRepository, ChatHistoryRepository

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
)
def send_message(
    channel_id: Annotated[str, Query(description="Channel ID to query")],
    request: ChatRequest,
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    """Send a question and get an AI-generated answer.

    The response includes grounding sources from the documents in the channel.
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

    # Search and generate answer
    result = gemini.search_and_answer(channel_id, request.query)

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
        query=request.query,
        response=result.get("response", ""),
        sources=sources,
        created_at=datetime.now(UTC),
    )

    # Store in DB
    chat_repo = ChatHistoryRepository(db)

    # Add user message
    chat_repo.add_message(
        channel=channel_meta,
        role="user",
        content=request.query,
        sources=None,
    )

    # Add assistant message
    chat_repo.add_message(
        channel=channel_meta,
        role="assistant",
        content=response.response,
        sources=[{"source": s.source, "content": s.content} for s in sources],
    )

    return response


@router.get(
    "/history",
    response_model=ChatHistory,
    summary="Get chat history",
)
def get_chat_history(
    channel_id: Annotated[str, Query(description="Channel ID")],
    gemini: Annotated[GeminiService, Depends(get_gemini_service)],
    db: Annotated[Session, Depends(get_db)],
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
    db_messages = chat_repo.get_history(channel_meta)

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
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear chat history",
)
def clear_chat_history(
    channel_id: Annotated[str, Query(description="Channel ID")],
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
