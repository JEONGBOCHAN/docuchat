# -*- coding: utf-8 -*-
"""
Gemini Document Summary Adapter.

Implements DocumentSummaryGenerationPort using Google Gemini API.
Generates concise summaries suitable for system prompt injection.
"""

from google import genai
from google.genai import types

from src.shared.kernel.contracts.ports.document_summary import DocumentSummaryGenerationPort
from src.core.config import get_settings, GeminiModels


class GeminiDocumentSummaryAdapter(DocumentSummaryGenerationPort):
    """DocumentSummaryGenerationPort implementation using Google Gemini.

    Generates concise document summaries (~100 tokens) that describe
    the key content and topics of a document. These summaries are
    injected into the agent's system prompt to help it choose the
    right tool (search_documents vs web_search).

    Example:
        adapter = GeminiDocumentSummaryAdapter()
        summary = adapter.generate_summary(
            channel_id="channel-123",
            document_name="attention_is_all_you_need.pdf",
        )
        # Returns: "This paper introduces the Transformer architecture..."
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

    def generate_summary(
        self,
        channel_id: str,
        document_name: str,
        max_tokens: int = 100,
        model: str = GeminiModels.DEFAULT,
    ) -> str:
        """Generate a concise summary for a document.

        Uses Gemini's File Search capability to read the document
        and generate a focused summary suitable for system prompt.

        Args:
            channel_id: The channel (store) containing the document
            document_name: Name of the document to summarize
            max_tokens: Maximum tokens for the summary (default: ~100)
            model: The model to use for generation

        Returns:
            Concise summary string (2-3 sentences, ~100 tokens)

        Raises:
            Exception: If summary generation fails
        """
        # Prompt optimized for concise, informative summaries
        prompt = f"""Summarize the document "{document_name}" in 2-3 sentences.
Focus on:
1. The main topic or subject
2. Key concepts, findings, or arguments
3. Document type (research paper, report, guide, etc.)

Be concise but informative. This summary will help decide if this document
is relevant to user questions. Maximum {max_tokens} tokens."""

        try:
            response = self._get_client().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[channel_id]
                            )
                        )
                    ],
                    # Higher limit needed when using file_search
                    # File search consumes tokens for internal reasoning
                    max_output_tokens=500,
                ),
            )

            summary = response.text if response.text else ""

            # Truncate if needed (shouldn't happen with max_output_tokens)
            if len(summary.split()) > max_tokens:
                words = summary.split()[:max_tokens]
                summary = " ".join(words) + "..."

            return summary.strip()

        except Exception as e:
            # Log the error but don't fail - graceful degradation
            raise Exception(f"Failed to generate summary for {document_name}: {str(e)}")
