# -*- coding: utf-8 -*-
"""Knowledge module public API.

Other modules MUST only import from this file.
Direct imports into knowledge internals are forbidden.
"""

from src.modules.knowledge.infrastructure.di import (  # noqa: F401
    # Port factories
    create_citation_search,
    create_faq_generation,
    create_summarization,
    create_timeline,
    create_briefing,
    create_study_guide,
    create_quiz,
    create_podcast_script,
    create_tts_port,
    create_audio_repository_port,
    # Use case factories
    create_search_with_citations_use_case,
    create_generate_faq_use_case,
    create_summarize_channel_use_case,
    create_summarize_document_use_case,
    create_generate_timeline_use_case,
    create_generate_briefing_use_case,
    create_generate_study_guide_use_case,
    create_generate_quiz_use_case,
    create_generate_podcast_script_use_case,
    create_generate_audio_use_case,
)

__all__ = [
    "create_citation_search",
    "create_faq_generation",
    "create_summarization",
    "create_timeline",
    "create_briefing",
    "create_study_guide",
    "create_quiz",
    "create_podcast_script",
    "create_tts_port",
    "create_audio_repository_port",
    "create_search_with_citations_use_case",
    "create_generate_faq_use_case",
    "create_summarize_channel_use_case",
    "create_summarize_document_use_case",
    "create_generate_timeline_use_case",
    "create_generate_briefing_use_case",
    "create_generate_study_guide_use_case",
    "create_generate_quiz_use_case",
    "create_generate_podcast_script_use_case",
    "create_generate_audio_use_case",
]
