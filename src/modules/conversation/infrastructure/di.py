# -*- coding: utf-8 -*-
"""Conversation module DI container."""

import logging
import threading
from functools import lru_cache

from src.application.ports import (
    AgentRunnerPort,
    AgentEventSinkPort,
    DocumentSearchPort,
    WebSearchPort,
    ArxivSearchPort,
    SemanticScholarSearchPort,
    CrossrefSearchPort,
    GoogleScholarSearchPort,
    ChatHistoryRepositoryPort,
    ChatSessionRepositoryPort,
    TokenCounterPort,
)
from src.application.use_cases.process_query import ProcessQueryUseCase

_container_logger = logging.getLogger(__name__)
_compaction_runner_lock = threading.Lock()


# ============================================================
# Singleton Instances
# ============================================================

_event_store = None
_state_store_adapter = None
_checkpointer = None


def get_event_store():
    from src.infrastructure.observability.event_store import InMemoryEventStore
    global _event_store
    if _event_store is None:
        _event_store = InMemoryEventStore()
    return _event_store


def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        logger = logging.getLogger(__name__)
        try:
            import sqlite3
            import os
            from langgraph.checkpoint.sqlite import SqliteSaver
            from src.core.config import get_settings

            settings = get_settings()
            db_path = settings.checkpoint_db_path
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            conn = sqlite3.connect(db_path, check_same_thread=False)
            _checkpointer = SqliteSaver(conn)
            _checkpointer.setup()
            logger.info("Checkpointer initialized: SqliteSaver (path=%s)", db_path)
        except Exception:
            from src.core.config import get_settings
            settings = get_settings()
            if settings.strict_checkpointer:
                logger.error(
                    "SqliteSaver initialization failed and strict_checkpointer=True.",
                    exc_info=True,
                )
                raise RuntimeError(
                    "SqliteSaver initialization failed (strict_checkpointer=True)."
                )
            logger.error(
                "Failed to create SqliteSaver, falling back to MemorySaver.",
                exc_info=True,
            )
            from langgraph.checkpoint.memory import MemorySaver
            _checkpointer = MemorySaver()
    return _checkpointer


def _create_checkpoint_store():
    from src.infrastructure.agent.checkpoint_adapter import LangGraphCheckpointAdapter
    return LangGraphCheckpointAdapter(get_checkpointer())


def get_checkpointer_type() -> str:
    return type(get_checkpointer()).__name__


def get_state_store_adapter():
    from src.infrastructure.observability.state_store_adapter import StateStoreAdapter
    from src.mcp_server.state import get_global_state_store
    global _state_store_adapter
    if _state_store_adapter is None:
        _state_store_adapter = StateStoreAdapter(get_global_state_store())
    return _state_store_adapter


def create_dashboard_middleware():
    from src.agents.middlewares.dashboard import DashboardMiddleware
    from src.mcp_server.state import get_global_state_store
    return DashboardMiddleware(state_store=get_global_state_store())


# ============================================================
# Port Factories
# ============================================================

def create_token_counter(use_api: bool = False) -> TokenCounterPort:
    from src.infrastructure.external.gemini.token_counter import GeminiTokenCounterAdapter
    return GeminiTokenCounterAdapter(use_api=use_api)


def create_event_sink(use_legacy_dashboard: bool = True) -> AgentEventSinkPort:
    if use_legacy_dashboard:
        return get_state_store_adapter()
    return get_event_store()


def create_agent_runner(
    event_sink=None,
    dashboard_middleware=None,
    token_counter=None,
) -> AgentRunnerPort:
    from src.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
    return LangGraphAgentRunner(
        event_sink=event_sink,
        dashboard_middleware=dashboard_middleware,
        token_counter=token_counter,
        checkpointer=get_checkpointer(),
    )


def create_document_search() -> DocumentSearchPort:
    from src.infrastructure.external.gemini.document_search import GeminiDocumentSearchAdapter
    return GeminiDocumentSearchAdapter()


def create_web_search() -> WebSearchPort:
    from src.infrastructure.external.mcp.web_search import McpWebSearchAdapter
    return McpWebSearchAdapter()


def create_arxiv_search() -> ArxivSearchPort:
    from src.infrastructure.external.arxiv.mcp_adapter import ArxivMcpAdapter
    return ArxivMcpAdapter()


def create_semantic_scholar_search(api_key=None) -> SemanticScholarSearchPort:
    from src.infrastructure.external.semantic_scholar.adapter import SemanticScholarAdapter
    return SemanticScholarAdapter(api_key=api_key)


def create_crossref_search(email=None) -> CrossrefSearchPort:
    from src.infrastructure.external.crossref.adapter import CrossrefAdapter
    return CrossrefAdapter(email=email)


def create_google_scholar_search() -> GoogleScholarSearchPort:
    from src.infrastructure.external.google_scholar.mcp_adapter import GoogleScholarMcpAdapter
    return GoogleScholarMcpAdapter()


def create_conversation_summary_port():
    from src.infrastructure.external.gemini.conversation_summary import GeminiConversationSummaryAdapter
    return GeminiConversationSummaryAdapter()


# ============================================================
# Repository Port Factories
# ============================================================

def create_chat_history_repository_port(db) -> ChatHistoryRepositoryPort:
    from src.infrastructure.persistence.adapters import ChatHistoryRepositoryAdapter
    return ChatHistoryRepositoryAdapter(db)


def create_chat_session_repository_port(db) -> ChatSessionRepositoryPort:
    from src.core.config import get_settings
    from src.infrastructure.persistence.adapters import ChatSessionRepositoryAdapter
    settings = get_settings()
    return ChatSessionRepositoryAdapter(db, session_timeout_hours=settings.session_timeout_hours)


def create_session_memory_repository_port(db):
    from src.infrastructure.persistence.adapters import ChatSessionMemoryRepositoryAdapter
    return ChatSessionMemoryRepositoryAdapter(db)


# ============================================================
# Use Case Factories
# ============================================================

def create_process_query_use_case(
    use_legacy_dashboard: bool = True,
    include_web_search: bool = False,
    include_academic_search: bool = False,
    enable_realtime_tokens: bool = True,
) -> ProcessQueryUseCase:
    event_sink = create_event_sink(use_legacy_dashboard=use_legacy_dashboard)
    dashboard_middleware = create_dashboard_middleware() if use_legacy_dashboard else None
    token_counter = create_token_counter() if (enable_realtime_tokens and use_legacy_dashboard) else None

    agent_runner = create_agent_runner(
        event_sink=event_sink,
        dashboard_middleware=dashboard_middleware,
        token_counter=token_counter,
    )

    document_search = create_document_search()
    web_search = create_web_search() if include_web_search else None

    enabled_tools = ["search_documents"]
    if include_web_search:
        enabled_tools.append("web_search")
    if include_academic_search:
        enabled_tools.extend([
            "arxiv_search",
            "semantic_scholar_search",
            "crossref_search",
            "google_scholar_search",
        ])

    return ProcessQueryUseCase(
        agent_runner=agent_runner,
        event_sink=event_sink,
        document_search=document_search,
        web_search=web_search,
        enabled_tools=enabled_tools,
    )


@lru_cache(maxsize=1)
def get_default_use_case() -> ProcessQueryUseCase:
    return create_process_query_use_case(
        use_legacy_dashboard=True,
        include_web_search=True,
        include_academic_search=True,
    )


def reset_use_case_cache() -> None:
    get_default_use_case.cache_clear()


def create_conversation_memory_service(db):
    from src.application.use_cases.conversation_memory import ConversationMemoryService
    from src.core.config import get_settings
    settings = get_settings()
    return ConversationMemoryService(
        chat_history_repo=create_chat_history_repository_port(db),
        session_memory_repo=create_session_memory_repository_port(db),
        summary_port=create_conversation_summary_port(),
        token_counter=create_token_counter(),
        compaction_trigger_turns=settings.memory_compaction_trigger_turns,
        compaction_target_tokens=settings.memory_compaction_target_tokens,
    )


def _get_compaction_runner():
    instance = getattr(_get_compaction_runner, "_instance", None)
    if instance is not None:
        return instance
    with _compaction_runner_lock:
        instance = getattr(_get_compaction_runner, "_instance", None)
        if instance is not None:
            return instance
        from src.infrastructure.compaction.runner import CompactionRunner
        from src.core.database import SessionLocal
        instance = CompactionRunner(
            session_factory=SessionLocal,
            service_factory=create_conversation_memory_service,
        )
        _get_compaction_runner._instance = instance
        return instance


def shutdown_compaction_runner(wait: bool = False) -> None:
    with _compaction_runner_lock:
        instance = getattr(_get_compaction_runner, "_instance", None)
        if instance is None:
            return
        try:
            instance.shutdown(wait=wait)
            _container_logger.info("CompactionRunner shut down (wait=%s)", wait)
        except Exception:
            _container_logger.warning(
                "CompactionRunner shutdown failed", exc_info=True,
            )
        finally:
            if hasattr(_get_compaction_runner, "_instance"):
                delattr(_get_compaction_runner, "_instance")


def create_chat_use_case(db):
    from src.application.use_cases.chat import ChatUseCase
    from src.core.config import get_settings
    from src.modules.workspace.public import (
        create_channel_port,
        create_channel_repository_port,
        create_search_history_repository_port,
        create_cache_port,
        create_get_channel_summaries_use_case,
    )
    settings = get_settings()
    return ChatUseCase(
        channel_port=create_channel_port(),
        channel_repo=create_channel_repository_port(db),
        chat_history_repo=create_chat_history_repository_port(db),
        session_repo=create_chat_session_repository_port(db),
        search_history_repo=create_search_history_repository_port(db),
        cache=create_cache_port(),
        summaries_use_case=create_get_channel_summaries_use_case(db),
        process_query_factory=lambda: create_process_query_use_case(
            use_legacy_dashboard=True,
            include_web_search=True,
            include_academic_search=True,
        ),
        conversation_memory=create_conversation_memory_service(db),
        session_memory_repo=create_session_memory_repository_port(db),
        memory_mode=settings.memory_mode,
        memory_token_budget=settings.memory_token_budget,
        memory_recent_turns=settings.memory_recent_turns,
        compaction_runner=_get_compaction_runner(),
        checkpoint_store=_create_checkpoint_store(),
    )
