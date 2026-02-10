# -*- coding: utf-8 -*-
"""
Gemini Podcast Script Adapter.

Implements PodcastScriptPort using Google Gemini API.
"""

import json

from google import genai
from google.genai import types

from src.shared.kernel.contracts.ports.podcast import (
    PodcastScriptPort,
    PodcastScriptDTO,
    DialogueLineDTO,
)
from src.core.config import get_settings, GeminiModels


class GeminiPodcastAdapter(PodcastScriptPort):
    """PodcastScriptPort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to generate
    podcast scripts from document stores.

    Example:
        adapter = GeminiPodcastAdapter()
        script = adapter.generate_podcast_script(
            "channel-123",
            duration_minutes=5,
            style="conversational",
        )
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

    def generate_podcast_script(
        self,
        store_name: str,
        duration_minutes: int = 5,
        style: str = "conversational",
        language: str = "ko",
        model: str = GeminiModels.DEFAULT,
    ) -> PodcastScriptDTO:
        """Generate a podcast script using Gemini.

        Args:
            store_name: The document store to analyze
            duration_minutes: Target duration in minutes (1-15)
            style: 'conversational' (casual) or 'professional' (formal)
            language: Language code (ko, en, ja, etc.)
            model: The model to use for generation

        Returns:
            PodcastScriptDTO with the generated script

        Raises:
            Exception: If script generation fails with an error
        """
        target_words = duration_minutes * 150

        if style == "professional":
            style_instruction = """Use a professional, formal tone. The hosts should sound like news anchors or documentary narrators. Avoid colloquialisms and maintain a serious, informative demeanor."""
        else:
            style_instruction = """Use a casual, conversational tone. The hosts should sound like friends having an engaging discussion. Include natural reactions, brief interruptions, and informal language to make it feel authentic."""

        language_instruction = {
            "ko": "모든 대화는 한국어로 작성하세요. 자연스러운 한국어 표현을 사용하세요.",
            "en": "Write all dialogue in English. Use natural English expressions.",
            "ja": "すべての会話を日本語で書いてください。自然な日本語表現を使用してください。",
        }.get(language, "Write all dialogue in the appropriate language for natural expression.")

        prompt = f"""Analyze all documents in this knowledge base and create an engaging podcast script with two hosts discussing the content.

{style_instruction}
{language_instruction}

The podcast should be approximately {duration_minutes} minutes long (about {target_words} words total).

Host A is the main presenter who introduces topics and asks questions.
Host B is the expert who provides explanations and insights.

Structure your response as a JSON object with these fields:
- "title": An engaging podcast episode title (string)
- "introduction": A brief introduction that Host A will read to open the show (string, 2-3 sentences)
- "dialogue": An array of dialogue lines, each with:
  - "speaker": "Host A" or "Host B" (string)
  - "text": The dialogue text (string)
- "conclusion": Closing remarks summarizing key points (string, 2-3 sentences)
- "estimated_duration_seconds": Estimated duration in seconds (integer)

Guidelines:
- Start with Host A introducing the topic
- Alternate between hosts naturally
- Include questions from Host A that Host B answers
- Add reactions like "That's interesting!" or "I see" for natural flow
- Cover the main points from the documents
- End with a summary and call-to-action

Return ONLY the JSON object, no other text.

Example format:
{{
  "title": "Understanding Machine Learning: A Deep Dive",
  "introduction": "Welcome to today's episode! We're exploring the fascinating world of machine learning...",
  "dialogue": [
    {{"speaker": "Host A", "text": "So, let's start with the basics. What exactly is machine learning?"}},
    {{"speaker": "Host B", "text": "Great question! Machine learning is essentially..."}}
  ],
  "conclusion": "That wraps up our discussion on machine learning. Remember, the key takeaways are...",
  "estimated_duration_seconds": 300
}}"""

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

            try:
                text = response.text or ""
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    script = json.loads(text[start:end])
                else:
                    script = {}
            except json.JSONDecodeError:
                script = {}

            dialogue = []
            for line in script.get("dialogue", []):
                dialogue.append(
                    DialogueLineDTO(
                        speaker=line.get("speaker", "Host A"),
                        text=line.get("text", ""),
                    )
                )

            return PodcastScriptDTO(
                title=script.get("title", "Podcast Episode"),
                introduction=script.get("introduction", ""),
                dialogue=dialogue,
                conclusion=script.get("conclusion", ""),
                estimated_duration_seconds=script.get(
                    "estimated_duration_seconds",
                    duration_minutes * 60,
                ),
            )

        except Exception as e:
            raise Exception(str(e))
