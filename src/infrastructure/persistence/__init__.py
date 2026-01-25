# -*- coding: utf-8 -*-
"""Persistence layer - Database repositories.

This module contains all database repository implementations for the application.
Repositories provide a clean abstraction over database operations.
"""

from src.infrastructure.persistence.channel_repository import (
    ChannelRepository,
    ChatHistoryRepository,
    ChatSessionRepository,
)
from src.infrastructure.persistence.note_repository import NoteRepository
from src.infrastructure.persistence.favorite_repository import FavoriteRepository
from src.infrastructure.persistence.search_repository import SearchHistoryRepository
from src.infrastructure.persistence.trash_repository import TrashRepository
from src.infrastructure.persistence.audio_repository import (
    AudioRepository,
    to_response,
)
from src.infrastructure.persistence.adapters import (
    ChannelRepositoryAdapter,
    ChatHistoryRepositoryAdapter,
    ChatSessionRepositoryAdapter,
    NoteRepositoryAdapter,
    FavoriteRepositoryAdapter,
    SearchHistoryRepositoryAdapter,
    TrashRepositoryAdapter,
    AudioRepositoryAdapter,
    DocumentPreviewCacheRepositoryAdapter,
)

__all__ = [
    # Channel repositories
    "ChannelRepository",
    "ChatHistoryRepository",
    "ChatSessionRepository",
    # Note repository
    "NoteRepository",
    # Favorite repository
    "FavoriteRepository",
    # Search repository
    "SearchHistoryRepository",
    # Trash repository
    "TrashRepository",
    # Audio repository
    "AudioRepository",
    "to_response",
    # Repository adapters (Port implementations)
    "ChannelRepositoryAdapter",
    "ChatHistoryRepositoryAdapter",
    "ChatSessionRepositoryAdapter",
    "NoteRepositoryAdapter",
    "FavoriteRepositoryAdapter",
    "SearchHistoryRepositoryAdapter",
    "TrashRepositoryAdapter",
    "AudioRepositoryAdapter",
    "DocumentPreviewCacheRepositoryAdapter",
]
