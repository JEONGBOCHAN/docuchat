# -*- coding: utf-8 -*-
"""Gemini Conversation Summary Adapter.

Implements ConversationSummaryPort using Google Gemini API
for incremental rolling conversation summarization.
"""

import logging

from google import genai
from google.genai import types

from src.application.ports.conversation_summary import ConversationSummaryPort, SummaryResult
from src.core.config import get_settings, GeminiModels

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = """\
You are a conversation summarizer. Your job is to maintain a rolling summary
of a conversation between a user and an AI assistant.

## Rules
1. Preserve facts exactly — do NOT paraphrase numbers, dates, or proper nouns.
2. Prioritize: user preferences, decisions, constraints, and action items.
3. Do NOT speculate or infer information that was not explicitly stated.
4. Keep the summary concise — target the token budget provided.
5. If previous summary is empty, create a new summary from the turns provided.
6. If previous summary exists, merge it with the new turns, dropping stale or superseded information.

## Output format (use these exact section headers)
### Facts
- Key factual information from the conversation

### Decisions
- Decisions made during the conversation

### User Preferences
- User preferences and requirements

### Open Questions
- Unresolved questions or ambiguities

### Pending Actions
- Action items or next steps
"""


class GeminiConversationSummaryAdapter(ConversationSummaryPort):
    """ConversationSummaryPort implementation using Google Gemini."""

    def __init__(self, client: genai.Client | None = None):
        if client:
            self._client = client
        else:
            settings = get_settings()
            self._client = genai.Client(api_key=settings.google_api_key)

    def summarize_incremental(
        self,
        previous_summary: str,
        new_turns: list[dict[str, str]],
        max_tokens: int = 1200,
    ) -> SummaryResult:
        """Generate incremental summary using Gemini."""
        if not new_turns:
            return SummaryResult(summary=previous_summary, success=True)

        # Build conversation text from turns
        turns_text = "\n".join(
            f"[{turn.get('role', 'user')}]: {turn.get('content', '')}"
            for turn in new_turns
        )

        # Build the user prompt
        if previous_summary:
            user_prompt = (
                f"## Previous Summary\n{previous_summary}\n\n"
                f"## New Conversation Turns\n{turns_text}\n\n"
                f"Merge the previous summary with the new turns. "
                f"Target approximately {max_tokens} tokens."
            )
        else:
            user_prompt = (
                f"## Conversation Turns\n{turns_text}\n\n"
                f"Create a summary of this conversation. "
                f"Target approximately {max_tokens} tokens."
            )

        try:
            response = self._client.models.generate_content(
                model=GeminiModels.FAST,
                contents=[user_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=_SUMMARY_SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=max_tokens * 2,  # Buffer for structured output
                ),
            )
            result = response.text.strip() if response.text else ""
            if not result:
                logger.warning("Empty summary from Gemini, falling back to previous")
                return SummaryResult(
                    summary=previous_summary, success=False,
                    error="Empty response from Gemini",
                )
            return SummaryResult(summary=result, success=True)
        except Exception as e:
            logger.error("Failed to generate conversation summary", exc_info=True)
            return SummaryResult(
                summary=previous_summary, success=False,
                error=str(e),
            )
