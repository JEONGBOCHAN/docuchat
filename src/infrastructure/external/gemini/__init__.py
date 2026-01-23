# -*- coding: utf-8 -*-
"""
Google Gemini Adapters.

Implementations of application ports using Google Gemini APIs.
"""

from src.infrastructure.external.gemini.document_search import GeminiDocumentSearchAdapter

__all__ = [
    "GeminiDocumentSearchAdapter",
]
