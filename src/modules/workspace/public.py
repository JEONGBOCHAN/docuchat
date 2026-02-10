# -*- coding: utf-8 -*-
"""Workspace module public API.

Other modules MUST only import from this file.
Direct imports into workspace internals are forbidden.
"""

from src.modules.workspace.infrastructure.di import (  # noqa: F401
    # Port factories
    create_channel_port,
    create_document_port,
    create_cache_port,
    create_youtube_port,
    create_crawler_port,
    create_document_summary_generation_port,
    # Repository port factories
    create_channel_repository_port,
    create_note_repository_port,
    create_favorite_repository_port,
    create_search_history_repository_port,
    create_trash_repository_port,
    create_document_preview_cache_repository_port,
    create_document_summary_cache_port,
    # Use case factories
    create_channel_crud_use_case,
    create_document_crud_use_case,
    create_note_crud_use_case,
    create_favorite_crud_use_case,
    create_search_history_use_case,
    create_generate_document_summary_use_case,
    create_get_channel_summaries_use_case,
    # Service factories
    create_capacity_service,
    create_export_service,
    create_preview_service,
)
