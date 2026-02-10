# -*- coding: utf-8 -*-
"""AudioJobDispatcherPort adapter backed by ThreadPoolExecutor."""

from collections.abc import Callable

from src.shared.kernel.contracts.ports.infrastructure import AudioJobDispatcherPort
from src.modules.knowledge.infrastructure.runtime.audio_executor import (
    get_audio_executor,
    shutdown_audio_executor,
)


class ThreadPoolAudioJobDispatcher(AudioJobDispatcherPort):
    """Adapter that delegates to the module-internal ThreadPoolExecutor."""

    def submit(self, fn: Callable, *args) -> None:  # noqa: D401
        get_audio_executor().submit(fn, *args)

    def shutdown(self, wait: bool = False) -> None:
        shutdown_audio_executor(wait=wait)
