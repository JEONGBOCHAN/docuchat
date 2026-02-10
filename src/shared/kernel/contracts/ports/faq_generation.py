# -*- coding: utf-8 -*-
"""
FAQ Generation Port.

Defines the interface for FAQ generation from documents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FAQItemDTO:
    """A single FAQ item."""

    question: str
    answer: str


class FAQGenerationPort(ABC):
    """Abstract interface for FAQ generation.

    Implementations generate FAQ items from a document store.

    Example:
        # Using Gemini
        adapter = GeminiFAQAdapter(gemini_service)
        items = adapter.generate_faq("channel-123", count=5)

        # Can be replaced with different implementation
        adapter = OpenAIFAQAdapter(openai_client)
        items = adapter.generate_faq("channel-123", count=5)
    """

    @abstractmethod
    def generate_faq(
        self,
        store_name: str,
        count: int = 5,
    ) -> list[FAQItemDTO]:
        """Generate FAQ items from documents.

        Args:
            store_name: The document store to analyze
            count: Number of FAQ items to generate (1-20)

        Returns:
            List of FAQItemDTO objects
        """
        pass
