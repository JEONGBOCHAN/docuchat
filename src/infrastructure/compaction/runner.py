# -*- coding: utf-8 -*-
"""Compaction runner — executes compaction in a bounded thread pool.

Solves two problems:
1. Background compaction sharing request-scoped DB sessions — each job
   creates its own DB session via ``session_factory``.
2. Unbounded thread creation — uses ``ThreadPoolExecutor`` with a fixed
   ``max_workers`` cap and session-level coalescing to skip duplicate jobs.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from src.application.use_cases.conversation_memory import ConversationMemoryService

logger = logging.getLogger(__name__)


class CompactionRunner:
    """Runs compaction jobs in a bounded thread pool with independent DB sessions.

    Features:
      - Each job opens and closes its own DB session (request-safe).
      - ``ThreadPoolExecutor`` caps concurrent workers (default 2).
      - Per-session coalescing: if a job for the same ``session_id`` is
        already in flight, ``submit`` is a no-op.
    """

    def __init__(
        self,
        session_factory: Callable[[], Any],
        service_factory: Callable[[Any], ConversationMemoryService],
        max_workers: int = 2,
    ):
        """
        Args:
            session_factory: Creates a new DB session (e.g. ``SessionLocal``).
            service_factory: Given a DB session, returns a
                ``ConversationMemoryService`` wired with that session.
            max_workers: Maximum number of concurrent compaction threads.
        """
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="compaction",
        )
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def submit(self, session_id: str) -> None:
        """Submit a compaction job for background execution.

        If a job for the same ``session_id`` is already pending or running,
        the call is silently skipped (coalescing).
        """
        with self._lock:
            if session_id in self._pending:
                logger.debug(
                    "Compaction already pending for session %s, skipping",
                    session_id,
                )
                return
            self._pending.add(session_id)

        try:
            self._executor.submit(self._run, session_id)
        except Exception:
            with self._lock:
                self._pending.discard(session_id)
            logger.warning(
                "Compaction submit failed for session %s; pending entry cleared",
                session_id,
                exc_info=True,
            )

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
            with self._lock:
                self._pending.discard(session_id)

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the thread pool.

        Args:
            wait: If True, block until all pending jobs complete.
        """
        self._executor.shutdown(wait=wait)
