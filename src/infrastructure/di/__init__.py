# -*- coding: utf-8 -*-
"""
Dependency Injection Module.

Provides factory functions for creating properly wired components.
"""

from src.infrastructure.di.container import (
    create_process_query_use_case,
    create_event_sink,
    create_agent_runner,
    create_document_search,
    create_web_search,
    create_arxiv_search,
    create_semantic_scholar_search,
    create_crossref_search,
    create_google_scholar_search,
    create_channel_port,
    create_document_port,
    get_default_use_case,
    get_event_store,
    get_state_store_adapter,
    reset_use_case_cache,
)

__all__ = [
    "create_process_query_use_case",
    "create_event_sink",
    "create_agent_runner",
    "create_document_search",
    "create_web_search",
    "create_arxiv_search",
    "create_semantic_scholar_search",
    "create_crossref_search",
    "create_google_scholar_search",
    "create_channel_port",
    "create_document_port",
    "get_default_use_case",
    "get_event_store",
    "get_state_store_adapter",
    "reset_use_case_cache",
]
