# -*- coding: utf-8 -*-
"""
Gemini Study Guide Adapter.

Implements StudyGuidePort using Google Gemini API.
"""

import json

from google import genai
from google.genai import types

from src.application.ports.learning import (
    StudyGuidePort,
    StudyGuideDTO,
    StudySectionDTO,
    KeyConceptDTO,
)
from src.core.config import get_settings, GeminiModels


class GeminiStudyGuideAdapter(StudyGuidePort):
    """StudyGuidePort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to generate
    study guides from document stores.

    Example:
        adapter = GeminiStudyGuideAdapter()
        guide = adapter.generate_study_guide("channel-123", difficulty="medium")
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

    def generate_study_guide(
        self,
        store_name: str,
        include_concepts: bool = True,
        include_summary: bool = True,
        max_sections: int = 5,
        difficulty: str = "medium",
        model: str = GeminiModels.DEFAULT,
    ) -> StudyGuideDTO:
        """Generate a study guide using Gemini.

        Args:
            store_name: The document store to analyze
            include_concepts: Whether to include key concepts section
            include_summary: Whether to include overview summary
            max_sections: Maximum number of sections (1-10)
            difficulty: Target difficulty level (easy, medium, hard)
            model: The model to use for generation

        Returns:
            StudyGuideDTO with the generated study guide

        Raises:
            Exception: If study guide generation fails with an error
        """
        difficulty_instruction = {
            "easy": "Use simple language and focus on fundamental concepts. Avoid jargon.",
            "medium": "Balance depth and accessibility. Include some technical details.",
            "hard": "Provide in-depth analysis with technical details and advanced concepts.",
        }.get(difficulty, "Balance depth and accessibility.")

        concepts_instruction = ""
        if include_concepts:
            concepts_instruction = """
- "key_concepts": An array of important terms/concepts, each with:
  - "term": The concept name (string)
  - "definition": Clear explanation (string)
  - "importance": Why this concept matters (string, optional)"""

        prompt = f"""Analyze all documents in this knowledge base and create a comprehensive study guide.

{difficulty_instruction}

Structure your response as a JSON object with these fields:
- "title": A descriptive title for the study guide (string)
- "overview": A brief overview of what will be learned (1-2 paragraphs)
- "sections": An array of up to {max_sections} study sections, each with:
  - "title": Section title (string)
  - "content": Detailed explanation (string, multiple paragraphs)
  - "key_points": Array of key points to remember (strings){concepts_instruction}
- "study_tips": Array of 3-5 practical study tips for this material (strings)

Return ONLY the JSON object, no other text.

Example format:
{{
  "title": "Complete Guide to Machine Learning",
  "overview": "This study guide covers...",
  "sections": [
    {{
      "title": "Introduction to ML",
      "content": "Machine learning is...",
      "key_points": ["ML automates pattern recognition", "Supervised vs unsupervised learning"]
    }}
  ],
  "key_concepts": [
    {{"term": "Neural Network", "definition": "A computing system inspired by biological neural networks", "importance": "Foundation of deep learning"}}
  ],
  "study_tips": ["Start with the basics", "Practice with real datasets"]
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
                    guide = json.loads(text[start:end])
                else:
                    guide = {}
            except json.JSONDecodeError:
                guide = {}

            sections = []
            for section in guide.get("sections", []):
                sections.append(
                    StudySectionDTO(
                        title=section.get("title", ""),
                        content=section.get("content", ""),
                        key_points=section.get("key_points", []),
                    )
                )

            key_concepts = []
            if include_concepts:
                for concept in guide.get("key_concepts", []):
                    key_concepts.append(
                        KeyConceptDTO(
                            term=concept.get("term", ""),
                            definition=concept.get("definition", ""),
                            importance=concept.get("importance"),
                        )
                    )

            return StudyGuideDTO(
                title=guide.get("title", "Study Guide"),
                overview=guide.get("overview", ""),
                sections=sections,
                key_concepts=key_concepts,
                study_tips=guide.get("study_tips", []),
            )

        except Exception as e:
            raise Exception(str(e))
