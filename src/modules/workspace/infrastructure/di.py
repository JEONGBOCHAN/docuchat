# -*- coding: utf-8 -*-
"""Workspace module DI container."""

from src.application.ports import (
    ChannelPort,
    DocumentPort,
    ChannelRepositoryPort,
    NoteRepositoryPort,
    FavoriteRepositoryPort,
    SearchHistoryRepositoryPort,
    TrashRepositoryPort,
    DocumentPreviewCacheRepositoryPort,
    DocumentSummaryGenerationPort,
    DocumentSummaryCachePort,
    YouTubePort,
    CrawlerPort,
    CachePort,
)
from src.infrastructure.external.gemini.channel import GeminiChannelAdapter
from src.infrastructure.external.gemini.document import GeminiDocumentAdapter
from src.infrastructure.external.gemini.document_summary import GeminiDocumentSummaryAdapter


# ============================================================
# Port Factories
# ============================================================

def create_channel_port() -> ChannelPort:
    return GeminiChannelAdapter()


def create_document_port() -> DocumentPort:
    return GeminiDocumentAdapter()


def create_cache_port() -> CachePort:
    from src.infrastructure.cache.adapters import CacheAdapter
    return CacheAdapter()


def create_youtube_port() -> YouTubePort:
    from src.infrastructure.external.adapters import YouTubeAdapter
    return YouTubeAdapter()


def create_crawler_port() -> CrawlerPort:
    from src.infrastructure.external.adapters import CrawlerAdapter
    return CrawlerAdapter()


def create_document_summary_generation_port() -> DocumentSummaryGenerationPort:
    return GeminiDocumentSummaryAdapter()


# ============================================================
# Repository Port Factories
# ============================================================

def create_channel_repository_port(db) -> ChannelRepositoryPort:
    from src.infrastructure.persistence.adapters import ChannelRepositoryAdapter
    return ChannelRepositoryAdapter(db)


def create_note_repository_port(db) -> NoteRepositoryPort:
    from src.infrastructure.persistence.adapters import NoteRepositoryAdapter
    return NoteRepositoryAdapter(db)


def create_favorite_repository_port(db) -> FavoriteRepositoryPort:
    from src.infrastructure.persistence.adapters import FavoriteRepositoryAdapter
    return FavoriteRepositoryAdapter(db)


def create_search_history_repository_port(db) -> SearchHistoryRepositoryPort:
    from src.infrastructure.persistence.adapters import SearchHistoryRepositoryAdapter
    return SearchHistoryRepositoryAdapter(db)


def create_trash_repository_port(db) -> TrashRepositoryPort:
    from src.infrastructure.persistence.adapters import TrashRepositoryAdapter
    return TrashRepositoryAdapter(db)


def create_document_preview_cache_repository_port(db) -> DocumentPreviewCacheRepositoryPort:
    from src.infrastructure.persistence.adapters import DocumentPreviewCacheRepositoryAdapter
    return DocumentPreviewCacheRepositoryAdapter(db)


def create_document_summary_cache_port(db) -> DocumentSummaryCachePort:
    from src.infrastructure.persistence.document_summary_repository import (
        DocumentSummaryCacheRepository,
    )
    return DocumentSummaryCacheRepository(db)


# ============================================================
# Use Case Factories
# ============================================================

def create_channel_crud_use_case(db):
    from src.application.use_cases.channel_crud import ChannelCrudUseCase
    return ChannelCrudUseCase(
        channel_port=create_channel_port(),
        document_port=create_document_port(),
        channel_repo=create_channel_repository_port(db),
        fav_repo=create_favorite_repository_port(db),
        cache=create_cache_port(),
    )


def create_document_crud_use_case(db):
    from src.application.use_cases.document_crud import DocumentCrudUseCase
    from src.core.config import get_settings
    settings = get_settings()
    return DocumentCrudUseCase(
        channel_port=create_channel_port(),
        document_port=create_document_port(),
        cache=create_cache_port(),
        capacity_service=create_capacity_service(db),
        summary_use_case=create_generate_document_summary_use_case(db),
        crawler_port=create_crawler_port(),
        allowed_extensions=settings.allowed_extensions,
        max_file_size_mb=settings.max_file_size_mb,
    )


def create_note_crud_use_case(db):
    from src.application.use_cases.note_crud import NoteCrudUseCase
    return NoteCrudUseCase(
        channel_port=create_channel_port(),
        channel_repo=create_channel_repository_port(db),
        note_repo=create_note_repository_port(db),
        trash_repo=create_trash_repository_port(db),
    )


def create_favorite_crud_use_case(db):
    from src.application.use_cases.favorite_crud import FavoriteCrudUseCase
    return FavoriteCrudUseCase(
        channel_port=create_channel_port(),
        fav_repo=create_favorite_repository_port(db),
        note_repo=create_note_repository_port(db),
    )


def create_search_history_use_case(db):
    from src.application.use_cases.search_history import SearchHistoryUseCase
    return SearchHistoryUseCase(
        channel_port=create_channel_port(),
        channel_repo=create_channel_repository_port(db),
        search_history_repo=create_search_history_repository_port(db),
    )


def create_generate_document_summary_use_case(db):
    from src.application.use_cases.document_summary import GenerateDocumentSummaryUseCase
    return GenerateDocumentSummaryUseCase(
        generation_port=create_document_summary_generation_port(),
        cache_port=create_document_summary_cache_port(db),
    )


def create_get_channel_summaries_use_case(db):
    from src.application.use_cases.document_summary import GetChannelDocumentSummariesUseCase
    return GetChannelDocumentSummariesUseCase(
        cache_port=create_document_summary_cache_port(db),
    )


# ============================================================
# Service Factories
# ============================================================

def create_capacity_service(db):
    from src.application.services.capacity_service import CapacityService
    return CapacityService(
        channel_repo=create_channel_repository_port(db),
    )


def create_export_service(db):
    from src.application.services.export_service import ExportService
    from src.modules.conversation.public import create_chat_history_repository_port
    return ExportService(
        channel_repo=create_channel_repository_port(db),
        note_repo=create_note_repository_port(db),
        chat_repo=create_chat_history_repository_port(db),
    )


def create_preview_service(db):
    from src.application.services.preview_service import PreviewService
    from src.infrastructure.persistence.adapters import DocumentPreviewCacheRepositoryAdapter
    from src.infrastructure.external.gemini.document_search import GeminiDocumentSearchAdapter
    return PreviewService(
        preview_cache_repo=DocumentPreviewCacheRepositoryAdapter(db),
        document_search=GeminiDocumentSearchAdapter(),
    )
