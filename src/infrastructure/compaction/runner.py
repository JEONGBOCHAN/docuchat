# -*- coding: utf-8 -*-
"""Compaction runner — executes compaction in background with independent DB sessions.

Solves the problem of background compaction sharing request-scoped DB sessions:
the request's `get_db()` generator closes the session on response completion,
but the background thread may still be running. This runner creates a fresh
DB session per job, ensuring the compaction never uses a closed session.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from src.application.use_cases.conversation_memory import ConversationMemoryService

logger = logging.getLogger(__name__)


class CompactionRunner:
    """Runs compaction jobs in background threads with independent DB sessions.

    Each compaction job creates its own database session, builds a fresh
    ConversationMemoryService, executes ``maybe_compact``, and closes the
    session — regardless of the request lifecycle.
    """

    def __init__(
        self,
        session_factory: Callable[[], Any],
        service_factory: Callable[[Any], ConversationMemoryService],
    ):
        """
        Args:
            session_factory: Creates a new DB session (e.g. ``SessionLocal``).
            service_factory: Given a DB session, returns a
                ``ConversationMemoryService`` wired with that session.
        """
        self._session_factory = session_factory
        self._service_factory = service_factory

    def submit(self, session_id: str) -> None:
        """Submit a compaction job for background execution."""
        thread = threading.Thread(
            target=self._run,
            args=(session_id,),
            daemon=True,
        )
        thread.start()

    def _run(self, session_id: str) -> None:
        """Execute compaction with an independent DB session."""
        db = self._session_factory()
        try:
            service = self._service_factory(db)
            service.maybe_compact(session_id)
        except Exception:
            logger.warning(
                "Background compaction failed for session %s",
                session_id,
                exc_info=True,
            )
        finally:
            db.close()
