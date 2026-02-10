# -*- coding: utf-8 -*-
"""AudioGenerationTaskPort adapter.

Moves the background execution logic (SessionLocal, event loop, use case wiring)
out of the presentation layer into an infrastructure adapter.
"""

import asyncio

from src.shared.kernel.contracts.ports.infrastructure import AudioGenerationTaskPort
from src.modules.knowledge.application.use_cases.audio_generation import AudioGenerationRequest


class ThreadPoolAudioGenerationTask(AudioGenerationTaskPort):
    """Adapter that runs audio generation in the background thread pool.

    Combines the AudioJobDispatcherPort (for thread submission) with the
    session/event-loop setup that was previously in the router.
    """

    def __init__(self, dispatcher):
        self._dispatcher = dispatcher

    def enqueue(self, request: AudioGenerationRequest) -> None:
        """Enqueue an audio generation request."""
        self._dispatcher.submit(_run_audio_generation_in_background, request)


def _run_audio_generation_in_background(request: AudioGenerationRequest) -> None:
    """Run audio generation use case in a background thread.

    Uses the shared DB session factory for thread safety, wires up the use case
    via the DI container, and runs it in a new event loop (required per-thread).
    """
    from src.core.database import SessionLocal
    from src.modules.knowledge.infrastructure.di import create_generate_audio_use_case

    db = SessionLocal()

    try:
        use_case = create_generate_audio_use_case(db)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(use_case.execute(request))
        finally:
            loop.close()
    finally:
        db.close()
