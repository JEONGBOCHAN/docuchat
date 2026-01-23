# -*- coding: utf-8 -*-
"""
Gemini FAQ Adapter.

Implements FAQGenerationPort using Google Gemini API.
This adapter wraps the existing GeminiService to conform to the port interface.
"""

from src.application.ports.faq_generation import FAQGenerationPort, FAQItemDTO
from src.services.gemini import GeminiService


class GeminiFAQAdapter(FAQGenerationPort):
    """FAQGenerationPort implementation using Google Gemini.

    This adapter wraps the existing GeminiService and exposes it through
    the clean architecture port interface. This allows the application
    layer to use FAQ generation without coupling to Gemini specifics.

    Example:
        gemini_service = GeminiService()
        adapter = GeminiFAQAdapter(gemini_service)

        items = adapter.generate_faq("channel-123", count=5)
    """

    def __init__(self, gemini_service: GeminiService | None = None):
        """Initialize adapter with GeminiService.

        Args:
            gemini_service: Optional GeminiService instance.
                           Creates one if not provided.
        """
        self._service = gemini_service or GeminiService()

    def generate_faq(
        self,
        store_name: str,
        count: int = 5,
    ) -> list[FAQItemDTO]:
        """Generate FAQ items using Gemini.

        Args:
            store_name: The document store to analyze
            count: Number of FAQ items to generate (1-20)

        Returns:
            List of FAQItemDTO objects
        """
        try:
            # Use GeminiService's generate_faq method
            result = self._service.generate_faq(store_name, count=count)

            # Convert dict results to FAQItemDTO dataclasses
            items = []
            for item in result.get("items", []):
                items.append(
                    FAQItemDTO(
                        question=item.get("question", ""),
                        answer=item.get("answer", ""),
                    )
                )

            return items

        except Exception as e:
            # Log error and return empty list
            print(f"Gemini FAQ generation error: {e}")
            return []
