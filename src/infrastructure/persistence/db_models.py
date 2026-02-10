# -*- coding: utf-8 -*-
"""SQLAlchemy database models — re-export shim.

All ORM models have been moved to their respective module persistence layers.
This file re-exports them for backward compatibility.
"""

# Re-export workspace models
from src.modules.workspace.infrastructure.persistence.models import (  # noqa: F401
    utc_now,
    ChannelMetadata,
    NoteDB,
    SearchHistoryDB,
    FavoriteDB,
    DocumentPreviewCacheDB,
    AudioOverviewDB,
    DocumentSummaryCacheDB,
)

# Re-export conversation models
from src.modules.conversation.infrastructure.persistence.models import (  # noqa: F401
    ChatMessageDB,
    ChatSessionDB,
    ChatSessionMemoryDB,
)
