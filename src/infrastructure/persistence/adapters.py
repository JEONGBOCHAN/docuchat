# -*- coding: utf-8 -*-
"""Repository adapters — compatibility shim.

All adapter implementations have been moved to their respective modules:
- Workspace: src.modules.workspace.infrastructure.persistence.repositories
- Conversation: src.modules.conversation.infrastructure.persistence.repositories

This file re-exports them for backward compatibility only.
No new implementations should be added here.
"""

# Re-export workspace adapters for backward compatibility
from src.modules.workspace.infrastructure.persistence.repositories import (  # noqa: F401
    _channel_to_dto,
    _note_to_dto,
    _preview_cache_to_dto,
    ChannelRepositoryAdapter,
    NoteRepositoryAdapter,
    FavoriteRepositoryAdapter,
    SearchHistoryRepositoryAdapter,
    TrashRepositoryAdapter,
    AudioRepositoryAdapter,
    DocumentPreviewCacheRepositoryAdapter,
)

# Re-export conversation adapters for backward compatibility
from src.modules.conversation.infrastructure.persistence.repositories import (  # noqa: F401
    _chat_message_to_dto,
    _chat_session_to_dto,
    _session_memory_to_dto,
    ChatHistoryRepositoryAdapter,
    ChatSessionRepositoryAdapter,
    ChatSessionMemoryRepositoryAdapter,
)
