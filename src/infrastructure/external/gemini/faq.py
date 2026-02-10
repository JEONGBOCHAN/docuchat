# -*- coding: utf-8 -*-
"""
Gemini FAQ Adapter.

Implements FAQGenerationPort using Google Gemini API.
"""

import json
from typing import Any

from google import genai
from google.genai import types

from src.shared.kernel.contracts.ports.faq_generation import FAQGenerationPort, FAQItemDTO
from src.core.config import get_settings, GeminiModels


class GeminiFAQAdapter(FAQGenerationPort):
    """FAQGenerationPort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to generate FAQ items
    from document stores.

    Example:
        adapter = GeminiFAQAdapter()
        items = adapter.generate_faq("channel-123", count=5)
    """

    def __init__(self, client: genai.Client | None = None):
        """Initialize adapter with Gemini client.

        Args:
            client: Optional Gemini client instance.
                   Creates one if not provided.
        """
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is None:
            settings = get_settings()
            self._client = genai.Client(api_key=settings.google_api_key)
        return self._client

    def generate_faq(
        self,
        store_name: str,
        count: int = 5,
        model: str = GeminiModels.DEFAULT,
    ) -> list[FAQItemDTO]:
        """Generate FAQ items using Gemini.

        Args:
            store_name: The document store to analyze
            count: Number of FAQ items to generate (1-20)
            model: The model to use for generation

        Returns:
            List of FAQItemDTO objects
        """
        prompt = f"""Based on the documents in this knowledge base, generate exactly {count} frequently asked questions (FAQ) that users might ask about the content.

For each question:
1. Create a clear, specific question that someone might naturally ask
2. Provide a comprehensive answer based on the document content

Format your response as a JSON array with objects containing "question" and "answer" fields.
Example format:
[
  {{"question": "What is X?", "answer": "X is..."}},
  {{"question": "How does Y work?", "answer": "Y works by..."}}
]

Generate exactly {count} FAQ items. Return ONLY the JSON array, no other text."""

        try:
            response = self._get_client().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name]
                            )
                        )
                    ],
                ),
            )

            # Parse the JSON response
            try:
                text = response.text or ""
                start = text.find("[")
                end = text.rfind("]") + 1
                if start != -1 and end > start:
                    parsed_items = json.loads(text[start:end])
                else:
                    parsed_items = []
            except json.JSONDecodeError:
                parsed_items = []

            # Convert dict results to FAQItemDTO dataclasses
            items = []
            for item in parsed_items:
                items.append(
                    FAQItemDTO(
                        question=item.get("question", ""),
                        answer=item.get("answer", ""),
                    )
                )

            return items

        except Exception as e:
            print(f"Gemini FAQ generation error: {e}")
            return []
