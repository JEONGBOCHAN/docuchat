# -*- coding: utf-8 -*-
"""
Dependency Injection Container — Facade / Compatibility Shim.

This file now delegates ALL creation logic to per-module DI containers.
No new factory logic should be added here; add it to the appropriate
module under src/modules/<module>/infrastructure/di.py instead.

Existing callers can continue to import from this file — each function
forwards to the real implementation in the module DI layer.
"""

# ============================================================
# Conversation module (chat, agent, checkpointer, compaction)
# ============================================================

from src.modules.conversation.public import (
    get_event_store,
    get_checkpointer,
    get_checkpointer_type,
    get_state_store_adapter,
    create_dashboard_middleware,
    shutdown_compaction_runner,
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
    create_chat_history_repository_port,
    create_chat_session_repository_port,
    create_session_memory_repository_port,
    create_process_query_use_case,
    get_default_use_case,
    reset_use_case_cache,
    create_conversation_memory_service,
    create_chat_use_case,
)

# ============================================================
# Workspace module (channel, document, note, favorites, etc.)
# ============================================================

from src.modules.workspace.public import (
    create_channel_port,
    create_document_port,
    create_cache_port,
    create_youtube_port,
    create_crawler_port,
    create_document_summary_generation_port,
    create_channel_repository_port,
    create_note_repository_port,
    create_favorite_repository_port,
    create_search_history_repository_port,
    create_trash_repository_port,
    create_document_preview_cache_repository_port,
    create_document_summary_cache_port,
    create_channel_crud_use_case,
    create_document_crud_use_case,
    create_note_crud_use_case,
    create_favorite_crud_use_case,
    create_search_history_use_case,
    create_generate_document_summary_use_case,
    create_get_channel_summaries_use_case,
    create_capacity_service,
    create_export_service,
    create_preview_service,
)

# ============================================================
# Knowledge module (FAQ, summarize, timeline, study, audio)
# ============================================================

from src.modules.knowledge.public import (
    create_citation_search,
    create_faq_generation,
    create_summarization,
    create_timeline,
    create_briefing,
    create_study_guide,
    create_quiz,
    create_podcast_script,
    create_tts_port,
    create_audio_repository_port,
    create_search_with_citations_use_case,
    create_generate_faq_use_case,
    create_summarize_channel_use_case,
    create_summarize_document_use_case,
    create_generate_timeline_use_case,
    create_generate_briefing_use_case,
    create_generate_study_guide_use_case,
    create_generate_quiz_use_case,
    create_generate_podcast_script_use_case,
    create_generate_audio_use_case,
)

# ============================================================
# Ops module (admin, scheduler, metrics)
# ============================================================

from src.modules.ops.public import (
    create_api_metrics_port,
    create_scheduler_port,
    create_admin_stats_service,
)

# ============================================================
# Suppress "unused import" warnings — these are re-exports.
# ============================================================

__all__ = [
    # Conversation
    "get_event_store",
    "get_checkpointer",
    "get_checkpointer_type",
    "get_state_store_adapter",
    "create_dashboard_middleware",
    "shutdown_compaction_runner",
    "create_token_counter",
    "create_event_sink",
    "create_agent_runner",
    "create_document_search",
    "create_web_search",
    "create_arxiv_search",
    "create_semantic_scholar_search",
    "create_crossref_search",
    "create_google_scholar_search",
    "create_conversation_summary_port",
    "create_chat_history_repository_port",
    "create_chat_session_repository_port",
    "create_session_memory_repository_port",
    "create_process_query_use_case",
    "get_default_use_case",
    "reset_use_case_cache",
    "create_conversation_memory_service",
    "create_chat_use_case",
    # Workspace
    "create_channel_port",
    "create_document_port",
    "create_cache_port",
    "create_youtube_port",
    "create_crawler_port",
    "create_document_summary_generation_port",
    "create_channel_repository_port",
    "create_note_repository_port",
    "create_favorite_repository_port",
    "create_search_history_repository_port",
    "create_trash_repository_port",
    "create_document_preview_cache_repository_port",
    "create_document_summary_cache_port",
    "create_channel_crud_use_case",
    "create_document_crud_use_case",
    "create_note_crud_use_case",
    "create_favorite_crud_use_case",
    "create_search_history_use_case",
    "create_generate_document_summary_use_case",
    "create_get_channel_summaries_use_case",
    "create_capacity_service",
    "create_export_service",
    "create_preview_service",
    # Knowledge
    "create_citation_search",
    "create_faq_generation",
    "create_summarization",
    "create_timeline",
    "create_briefing",
    "create_study_guide",
    "create_quiz",
    "create_podcast_script",
    "create_tts_port",
    "create_audio_repository_port",
    "create_search_with_citations_use_case",
    "create_generate_faq_use_case",
    "create_summarize_channel_use_case",
    "create_summarize_document_use_case",
    "create_generate_timeline_use_case",
    "create_generate_briefing_use_case",
    "create_generate_study_guide_use_case",
    "create_generate_quiz_use_case",
    "create_generate_podcast_script_use_case",
    "create_generate_audio_use_case",
    # Ops
    "create_api_metrics_port",
    "create_scheduler_port",
    "create_admin_stats_service",
]
