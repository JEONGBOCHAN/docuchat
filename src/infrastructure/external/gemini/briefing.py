# -*- coding: utf-8 -*-
"""
Gemini Briefing Adapter.

Implements BriefingPort using Google Gemini API.
"""

import json

from google import genai
from google.genai import types

from src.application.ports.timeline import BriefingPort, BriefingDTO, BriefingSectionDTO
from src.core.config import get_settings, GeminiModels


class GeminiBriefingAdapter(BriefingPort):
    """BriefingPort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to generate
    briefing documents from document stores.

    Example:
        adapter = GeminiBriefingAdapter()
        briefing = adapter.generate_briefing("channel-123", style="executive")
    """

    def __init__(self, client: genai.Client | None = None):
        """Initialize adapter with Gemini client.

        Args:
            client: Optional Gemini client instance.
                   Creates one if not provided.
        """
        if client:
            self._client = client
        else:
            settings = get_settings()
            self._client = genai.Client(api_key=settings.google_api_key)

    def generate_briefing(
        self,
        store_name: str,
        style: str = "executive",
        max_sections: int = 5,
        model: str = GeminiModels.DEFAULT,
    ) -> BriefingDTO:
        """Generate a briefing document using Gemini.

        Args:
            store_name: The document store to analyze
            style: 'executive' (concise) or 'detailed' (comprehensive)
            max_sections: Maximum number of sections (1-10)
            model: The model to use for generation

        Returns:
            BriefingDTO with the generated briefing

        Raises:
            Exception: If briefing generation fails with an error
        """
        if style == "detailed":
            style_instruction = "Provide comprehensive details with in-depth analysis for each section."
        else:
            style_instruction = "Keep it concise and focused on key insights. This is for busy executives."

        prompt = f"""Analyze all documents in this knowledge base and create a professional briefing document.

{style_instruction}

Structure your response as a JSON object with these fields:
- "title": A clear, descriptive title for the briefing (string)
- "executive_summary": A brief overview of the key findings (2-3 sentences)
- "sections": An array of up to {max_sections} sections, each with:
  - "title": Section title (string)
  - "content": Section content (string, 1-3 paragraphs)
- "key_points": An array of 3-5 key takeaways (strings)

Return ONLY the JSON object, no other text.

Example format:
{{
  "title": "Q4 2024 Performance Briefing",
  "executive_summary": "This briefing covers...",
  "sections": [
    {{"title": "Overview", "content": "The documents indicate..."}},
    {{"title": "Key Findings", "content": "Several important findings..."}}
  ],
  "key_points": [
    "Revenue increased by 15%",
    "Budget utilization at 75%",
    "Three major risks identified"
  ]
}}"""

        try:
            response = self._client.models.generate_content(
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

            try:
                text = response.text or ""
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    briefing = json.loads(text[start:end])
                else:
                    briefing = {}
            except json.JSONDecodeError:
                briefing = {}

            sections = []
            for section in briefing.get("sections", []):
                sections.append(
                    BriefingSectionDTO(
                        title=section.get("title", ""),
                        content=section.get("content", ""),
                    )
                )

            return BriefingDTO(
                title=briefing.get("title", "Briefing"),
                executive_summary=briefing.get("executive_summary", ""),
                sections=sections,
                key_points=briefing.get("key_points", []),
            )

        except Exception as e:
            raise Exception(str(e))
