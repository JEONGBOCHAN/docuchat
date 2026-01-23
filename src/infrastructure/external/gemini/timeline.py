# -*- coding: utf-8 -*-
"""
Gemini Timeline Adapter.

Implements TimelinePort using Google Gemini API.
"""

import json

from google import genai
from google.genai import types

from src.application.ports.timeline import TimelinePort, TimelineEventDTO
from src.core.config import get_settings


class GeminiTimelineAdapter(TimelinePort):
    """TimelinePort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to extract
    timeline events from document stores.

    Example:
        adapter = GeminiTimelineAdapter()
        events = adapter.generate_timeline("channel-123", max_events=10)
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

    def generate_timeline(
        self,
        store_name: str,
        max_events: int = 20,
        model: str = "gemini-3-flash-preview",
    ) -> list[TimelineEventDTO]:
        """Generate a timeline of events using Gemini.

        Args:
            store_name: The document store to analyze
            max_events: Maximum number of events to extract (1-50)
            model: The model to use for generation

        Returns:
            List of TimelineEventDTO objects sorted chronologically

        Raises:
            Exception: If timeline generation fails with an error
        """
        prompt = f"""Analyze all documents in this knowledge base and extract a chronological timeline of key events, milestones, or important dates mentioned.

For each event, provide:
1. The date or time period (as specific as possible)
2. A brief title describing the event
3. A short description with relevant details
4. The source document (if identifiable)

Format your response as a JSON array with up to {max_events} events, sorted chronologically.
Each event should have: "date", "title", "description", and optionally "source".

Example format:
[
  {{"date": "January 2024", "title": "Project Launch", "description": "The project was officially launched...", "source": "project_overview.pdf"}},
  {{"date": "March 15, 2024", "title": "First Milestone", "description": "Completed the first phase..."}}
]

Return ONLY the JSON array, no other text. If no timeline events can be extracted, return an empty array []."""

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
                start = text.find("[")
                end = text.rfind("]") + 1
                if start != -1 and end > start:
                    parsed_events = json.loads(text[start:end])
                else:
                    parsed_events = []
            except json.JSONDecodeError:
                parsed_events = []

            events = []
            for event in parsed_events:
                events.append(
                    TimelineEventDTO(
                        date=event.get("date", "Unknown"),
                        title=event.get("title", ""),
                        description=event.get("description", ""),
                        source=event.get("source"),
                    )
                )

            return events

        except Exception as e:
            raise Exception(str(e))
