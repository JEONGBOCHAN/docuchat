# -*- coding: utf-8 -*-
"""Text-to-Speech infrastructure using Edge TTS."""

from src.infrastructure.external.tts.tts_service import (
    TTSService,
    get_tts_service,
    get_voice_name,
    VOICE_MAP_KO,
    VOICE_MAP_EN,
    VOICE_RATES,
)

__all__ = [
    "TTSService",
    "get_tts_service",
    "get_voice_name",
    "VOICE_MAP_KO",
    "VOICE_MAP_EN",
    "VOICE_RATES",
]
