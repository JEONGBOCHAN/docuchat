# -*- coding: utf-8 -*-
"""Conversation module public API.

Other modules MUST only import from this file.
Direct imports into conversation internals are forbidden.
"""

from src.modules.conversation.infrastructure.di import (  # noqa: F401
    # Singletons
    get_event_store,
    get_checkpointer,
    get_checkpointer_type,
    get_state_store_adapter,
    create_dashboard_middleware,
    shutdown_compaction_runner,
    # Port factories
    create_token_counter,
    create_event_sink,
    create_agent_runner,
    create_document_search,
    create_web_search,
    create_arxiv_search,
    create_semantic_scholar_search,
    create_crossref_search,
    create_google_scholar_search,
    create_conversation_summary_port,
    # Repository port factories
    create_chat_history_repository_port,
    create_chat_session_repository_port,
    create_session_memory_repository_port,
    # Use case factories
    create_process_query_use_case,
    get_default_use_case,
    reset_use_case_cache,
    create_conversation_memory_service,
    create_chat_use_case,
)
