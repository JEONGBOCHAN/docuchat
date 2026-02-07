# -*- coding: utf-8 -*-
"""Chat use case.

Orchestrates chat messaging, history management, and session management.
Coordinates channel validation, conversation context, agent execution,
caching, and persistence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Callable, Generator

from src.application.ports.channel import ChannelPort
from src.application.ports.persistence import (
    ChannelRepositoryPort,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    SearchHistoryRepositoryPort,
)
from src.application.ports.cache import CachePort
from src.application.use_cases.document_summary import GetChannelDocumentSummariesUseCase
from src.application.use_cases.process_query import ProcessQueryUseCase
from src.application.use_cases.exceptions import (
    ChannelNotFoundError,
    SessionNotFoundError,
    SessionExpiredError,
)

logger = logging.getLogger(__name__)


# ============================================================
# DTOs
# ============================================================

@dataclass
class SourceDTO:
    """A grounding source."""
    source: str
    content: str = ""
    url: str | None = None
    source_type: str = "document"


@dataclass
class ChatResultDTO:
    """Result of a chat message."""
    query: str
    response: str
    sources: list[SourceDTO]
    session_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ChatMessageInfoDTO:
    """Info about a chat message in history."""
    role: str
    content: str
    sources: list[SourceDTO]
    created_at: datetime


@dataclass
class ChatHistoryResultDTO:
    """Result of getting chat history."""
    channel_id: str
    messages: list[ChatMessageInfoDTO]
    total: int


@dataclass
class SessionInfoDTO:
    """Info about a chat session."""
    session_id: str
    channel_id: str
    created_at: datetime
    last_activity_at: datetime
    context_window: int


# ============================================================
# Exceptions
# ============================================================

class ChatAgentError(Exception):
    """Error from the chat agent."""
    pass


# ============================================================
# Use Case
# ============================================================

class ChatUseCase:
    """Orchestrates chat operations.

    Handles: channel validation, session management, conversation context,
    agent execution (via ProcessQueryUseCase factory), caching, and
    chat history persistence.
    """

    def __init__(
        self,
        channel_port: ChannelPort,
        channel_repo: ChannelRepositoryPort,
        chat_history_repo: ChatHistoryRepositoryPort,
        session_repo: ChatSessionRepositoryPort,
        search_history_repo: SearchHistoryRepositoryPort,
        cache: CachePort,
        summaries_use_case: GetChannelDocumentSummariesUseCase,
        process_query_factory: Callable[[], ProcessQueryUseCase],
    ):
        self._channel_port = channel_port
        self._channel_repo = channel_repo
        self._chat_history = chat_history_repo
        self._session_repo = session_repo
        self._search_history = search_history_repo
        self._cache = cache
        self._summaries = summaries_use_case
        self._process_query_factory = process_query_factory

    # ---- Private helpers ----

    def _validate_channel(self, channel_id: str):
        """Validate channel exists via external API."""
        channel = self._channel_port.get_channel(channel_id)
        if not channel:
            raise ChannelNotFoundError(channel_id)
        return channel

    def _get_or_create_channel_meta(self, channel_id: str, display_name: str | None = None):
        """Get or create local channel metadata."""
        meta = self._channel_repo.get_by_gemini_id(channel_id)
        if not meta:
            meta = self._channel_repo.create(
                gemini_store_id=channel_id,
                name=display_name or "unknown",
            )
        else:
            self._channel_repo.touch(channel_id)
        return meta

    def _resolve_session(self, channel_db_id: int, session_id: str | None):
        """Resolve session, returning the session_id for response."""
        if not session_id:
            return None
        session_dto, _ = self._session_repo.get_or_create(
            channel_id=channel_db_id,
            session_id=session_id,
        )
        return session_dto.session_id if session_dto else session_id

    def _get_conversation_history(self, session_id: str | None) -> list[dict[str, str]]:
        """Get conversation history for context."""
        if not session_id:
            return []
        messages = self._chat_history.get_session_history(session_id)
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _save_chat_messages(
        self,
        channel_db_id: int,
        query: str,
        response: str,
        source_dicts: list[dict] | None,
        session_id: str | None,
    ):
        """Save user and assistant messages to history."""
        self._chat_history.add_message(
            channel_id=channel_db_id,
            role="user",
            content=query,
            sources=None,
            session_id=session_id,
        )
        self._chat_history.add_message(
            channel_id=channel_db_id,
            role="assistant",
            content=response,
            sources=source_dicts,
            session_id=session_id,
        )

    @staticmethod
    def _normalize_response_content(content) -> str:
        """Normalize response content that might be a list."""
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        return content or ""

    @staticmethod
    def _dicts_to_sources(raw_sources: list[dict]) -> list[SourceDTO]:
        """Convert raw source dicts to SourceDTOs."""
        return [
            SourceDTO(
                source=s.get("source", "unknown"),
                content=s.get("content", ""),
                url=s.get("url"),
                source_type=s.get("source_type", "document"),
            )
            for s in raw_sources
        ]

    @staticmethod
    def _sources_to_dicts(sources: list[SourceDTO]) -> list[dict]:
        """Convert SourceDTOs to dicts for storage."""
        return [
            {
                "source": s.source,
                "content": s.content,
                "url": s.url,
                "source_type": s.source_type,
            }
            for s in sources
        ]

    # ---- Chat messaging ----

    def send_message(
        self,
        channel_id: str,
        query: str,
        session_id: str | None = None,
    ) -> ChatResultDTO:
        """Send a chat message and get AI response.

        Validates channel, manages session context, runs agent,
        caches result, and saves to history.

        Raises:
            ChannelNotFoundError: Channel not found.
            ChatAgentError: Agent returned an error.
        """
        channel = self._validate_channel(channel_id)
        channel_meta = self._get_or_create_channel_meta(
            channel_id, channel.display_name
        )

        session_id_response = self._resolve_session(channel_meta.id, session_id)
        conversation_history = self._get_conversation_history(session_id_response)
        document_context = self._summaries.build_context_string(channel_id)

        # Check cache (only for non-session queries)
        use_cache = not session_id
        if use_cache:
            cached = self._cache.get_chat_response(channel_id, query)
            if cached:
                sources = self._dicts_to_sources(cached.get("sources", []))
                self._search_history.add_or_update(channel_meta.id, query)
                self._save_chat_messages(
                    channel_meta.id, query, cached.get("response", ""),
                    cached.get("sources", []), session_id_response,
                )
                return ChatResultDTO(
                    query=query,
                    response=cached.get("response", ""),
                    sources=sources,
                    session_id=None,
                )

        # Run agent
        use_case = self._process_query_factory()
        result = use_case.execute(
            query=query,
            channel_id=channel_id,
            conversation_history=conversation_history,
            max_iterations=15,
            document_context=document_context,
        )

        if result.error:
            raise ChatAgentError(f"Failed to generate response: {result.error}")

        response_text = self._normalize_response_content(result.response)
        sources = self._dicts_to_sources(result.sources or [])

        # Cache the response
        if use_cache:
            self._cache.set_chat_response(
                channel_id, query,
                {"response": response_text, "sources": result.sources or []},
            )

        # Save to history
        self._search_history.add_or_update(channel_meta.id, query)
        self._save_chat_messages(
            channel_meta.id, query, response_text,
            self._sources_to_dicts(sources), session_id_response,
        )

        return ChatResultDTO(
            query=query,
            response=response_text,
            sources=sources,
            session_id=session_id_response,
        )

    def prepare_stream(
        self,
        channel_id: str,
        query: str,
        session_id: str | None = None,
    ) -> tuple[str | None, Generator[dict, None, dict | None]]:
        """Prepare streaming chat. Validates synchronously, returns generator.

        Validation (channel, session) happens synchronously so errors
        can be caught before StreamingResponse is created.

        Returns:
            Tuple of (session_id_response, event_generator).
            Events: {"type": "content", "chunk": str},
                    {"type": "sources", "sources": list},
                    {"type": "done"},
                    {"type": "error", "error": str}

        Raises:
            ChannelNotFoundError: Channel not found.
        """
        channel = self._validate_channel(channel_id)
        channel_meta = self._get_or_create_channel_meta(
            channel_id, channel.display_name
        )

        session_id_response = self._resolve_session(channel_meta.id, session_id)
        conversation_history = self._get_conversation_history(session_id_response)
        document_context = self._summaries.build_context_string(channel_id)

        def generate() -> Generator[dict, None, dict | None]:
            """Generate stream events."""
            use_case = self._process_query_factory()
            stream_gen = use_case.execute_stream(
                query=query,
                channel_id=channel_id,
                conversation_history=conversation_history,
                max_iterations=15,
                document_context=document_context,
            )

            accumulated_content = ""
            result = None

            try:
                while True:
                    event = next(stream_gen)
                    event_type = event.get("event")

                    if event_type == "content":
                        content = event.get("content", "")
                        if content:
                            accumulated_content += content
                            yield {"type": "content", "chunk": content}
                    elif event_type == "error":
                        yield {"type": "error", "error": event.get("error", "Unknown error")}
            except StopIteration as e:
                result = e.value

            if result:
                sources = result.sources or []
                if sources:
                    yield {"type": "sources", "sources": sources}

                # Save to DB
                self._search_history.add_or_update(channel_meta.id, query)
                self._save_chat_messages(
                    channel_meta.id, query,
                    accumulated_content or result.response or "",
                    sources, session_id_response,
                )

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
                return None

        return session_id_response, generate()

    # ---- Chat history ----

    def get_history(
        self, channel_id: str, limit: int = 100
    ) -> ChatHistoryResultDTO:
        """Get chat history for a channel.

        Raises:
            ChannelNotFoundError: Channel not found.
        """
        self._validate_channel(channel_id)

        channel_meta = self._channel_repo.get_by_gemini_id(channel_id)
        if not channel_meta:
            return ChatHistoryResultDTO(
                channel_id=channel_id, messages=[], total=0
            )

        msg_dtos = self._chat_history.get_history(channel_meta.id, limit=limit)
        messages = [
            ChatMessageInfoDTO(
                role=msg.role,
                content=msg.content,
                sources=self._dicts_to_sources(msg.sources),
                created_at=msg.created_at,
            )
            for msg in msg_dtos
        ]

        return ChatHistoryResultDTO(
            channel_id=channel_id, messages=messages, total=len(messages)
        )

    def clear_history(self, channel_id: str) -> None:
        """Clear chat history for a channel.

        Raises:
            ChannelNotFoundError: Channel not found.
        """
        self._validate_channel(channel_id)

        channel_meta = self._channel_repo.get_by_gemini_id(channel_id)
        if channel_meta:
            self._chat_history.clear_history(channel_meta.id)

    # ---- Session management ----

    def create_session(
        self, channel_id: str, context_window: int = 10
    ) -> SessionInfoDTO:
        """Create a new chat session.

        Raises:
            ChannelNotFoundError: Channel not found.
        """
        channel = self._validate_channel(channel_id)
        channel_meta = self._get_or_create_channel_meta(
            channel_id, channel.display_name
        )

        session_dto = self._session_repo.create(
            channel_id=channel_meta.id,
            context_window=context_window,
        )

        return SessionInfoDTO(
            session_id=session_dto.session_id,
            channel_id=channel_id,
            created_at=session_dto.created_at,
            last_activity_at=session_dto.last_activity_at,
            context_window=session_dto.context_window,
        )

    def get_session(
        self, channel_id: str, session_id: str
    ) -> SessionInfoDTO:
        """Get session info.

        Raises:
            SessionNotFoundError: Session not found.
            SessionExpiredError: Session has expired.
        """
        session_dto = self._session_repo.get_by_session_id(session_id)
        if not session_dto:
            raise SessionNotFoundError(session_id)

        if self._session_repo.is_expired(session_id):
            raise SessionExpiredError(session_id)

        return SessionInfoDTO(
            session_id=session_dto.session_id,
            channel_id=channel_id,
            created_at=session_dto.created_at,
            last_activity_at=session_dto.last_activity_at,
            context_window=session_dto.context_window,
        )

    def get_session_history(
        self, channel_id: str, session_id: str, limit: int = 100
    ) -> ChatHistoryResultDTO:
        """Get chat history for a specific session.

        Raises:
            SessionNotFoundError: Session not found.
        """
        session_dto = self._session_repo.get_by_session_id(session_id)
        if not session_dto:
            raise SessionNotFoundError(session_id)

        msg_dtos = self._chat_history.get_session_history(session_id, limit=limit)
        messages = [
            ChatMessageInfoDTO(
                role=msg.role,
                content=msg.content,
                sources=self._dicts_to_sources(msg.sources),
                created_at=msg.created_at,
            )
            for msg in msg_dtos
        ]

        return ChatHistoryResultDTO(
            channel_id=channel_id, messages=messages, total=len(messages)
        )

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session.

        Raises:
            SessionNotFoundError: Session not found.
        """
        if not self._session_repo.delete(session_id):
            raise SessionNotFoundError(session_id)
        return True
