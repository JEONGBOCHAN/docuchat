# -*- coding: utf-8 -*-
"""Audio generation thread pool executor lifecycle.

Provides lazy-initialized bounded thread pool for background audio generation.
This module has no FastAPI/HTTP dependencies.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

_audio_executor: ThreadPoolExecutor | None = None
_audio_executor_lock = threading.Lock()
_logger = logging.getLogger(__name__)


def get_audio_executor() -> ThreadPoolExecutor:
    """Get or create the audio generation thread pool."""
    global _audio_executor
    if _audio_executor is not None:
        return _audio_executor
    with _audio_executor_lock:
        if _audio_executor is not None:
            return _audio_executor
        _audio_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="audio-gen")
        return _audio_executor


def shutdown_audio_executor(wait: bool = False) -> None:
    """Shut down the audio generation thread pool.

    Called during app lifespan shutdown. Sets the global to None so
    a fresh executor is created on next access.
    """
    global _audio_executor
    with _audio_executor_lock:
        executor = _audio_executor
        _audio_executor = None
    if executor is None:
        return
    try:
        executor.shutdown(wait=wait)
        _logger.info("Audio executor shut down (wait=%s)", wait)
    except Exception:
        _logger.warning("Audio executor shutdown failed", exc_info=True)
