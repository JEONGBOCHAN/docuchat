# -*- coding: utf-8 -*-
"""
Google Gemini Adapters.

Implementations of application ports using Google Gemini APIs.
"""

from src.infrastructure.external.gemini.document_search import GeminiDocumentSearchAdapter
from src.infrastructure.external.gemini.citation import GeminiCitationAdapter
from src.infrastructure.external.gemini.faq import GeminiFAQAdapter
from src.infrastructure.external.gemini.summarization import GeminiSummarizationAdapter
from src.infrastructure.external.gemini.timeline import GeminiTimelineAdapter
from src.infrastructure.external.gemini.briefing import GeminiBriefingAdapter
from src.infrastructure.external.gemini.study_guide import GeminiStudyGuideAdapter
from src.infrastructure.external.gemini.quiz import GeminiQuizAdapter
from src.infrastructure.external.gemini.podcast import GeminiPodcastAdapter
from src.infrastructure.external.gemini.token_counter import GeminiTokenCounterAdapter

__all__ = [
    "GeminiDocumentSearchAdapter",
    "GeminiCitationAdapter",
    "GeminiFAQAdapter",
    "GeminiSummarizationAdapter",
    "GeminiTimelineAdapter",
    "GeminiBriefingAdapter",
    "GeminiStudyGuideAdapter",
    "GeminiQuizAdapter",
    "GeminiPodcastAdapter",
    "GeminiTokenCounterAdapter",
]
