# -*- coding: utf-8 -*-
"""
Gemini Summarization Adapter.

Implements SummarizationPort using Google Gemini API.
"""

from google import genai
from google.genai import types

from src.application.ports.summarization import SummarizationPort, SummaryDTO
from src.core.config import get_settings, GeminiModels


class GeminiSummarizationAdapter(SummarizationPort):
    """SummarizationPort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to generate summaries
    from document stores.

    Example:
        adapter = GeminiSummarizationAdapter()
        result = adapter.summarize_channel("channel-123", summary_type="short")
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

    def summarize_channel(
        self,
        store_name: str,
        summary_type: str = "short",
        model: str = GeminiModels.DEFAULT,
    ) -> SummaryDTO:
        """Summarize all documents in a channel using Gemini.

        Args:
            store_name: The document store to summarize
            summary_type: 'short' (2-3 sentences) or 'detailed' (comprehensive)
            model: The model to use for generation

        Returns:
            SummaryDTO with the generated summary

        Raises:
            Exception: If summarization fails with an error
        """
        if summary_type == "detailed":
            prompt = """Provide a comprehensive summary of all the documents in this knowledge base.

Structure your summary as follows:
1. **Overview**: A brief introduction to what the documents cover
2. **Key Topics**: Main subjects and themes discussed
3. **Important Points**: Significant findings, facts, or conclusions
4. **Additional Details**: Any other notable information

Be thorough but concise. Use the document content to provide accurate information."""
        else:
            prompt = """Summarize all the documents in this knowledge base in 2-3 concise sentences.
Focus on the main topic and the most important points. Be clear and informative."""

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
                    ]
                ),
            )

            return SummaryDTO(summary=response.text if response.text else "")

        except Exception as e:
            raise Exception(str(e))

    def summarize_document(
        self,
        store_name: str,
        document_name: str,
        summary_type: str = "short",
        model: str = GeminiModels.DEFAULT,
    ) -> SummaryDTO:
        """Summarize a specific document using Gemini.

        Args:
            store_name: The document store containing the document
            document_name: The name of the document to summarize
            summary_type: 'short' (2-3 sentences) or 'detailed' (comprehensive)
            model: The model to use for generation

        Returns:
            SummaryDTO with the generated summary

        Raises:
            Exception: If summarization fails with an error
        """
        if summary_type == "detailed":
            prompt = f"""Provide a comprehensive summary of the document named "{document_name}".

Structure your summary as follows:
1. **Overview**: What the document is about
2. **Key Points**: Main topics and important information
3. **Details**: Significant findings or conclusions
4. **Summary**: Brief closing statement

Focus only on the content from this specific document."""
        else:
            prompt = f"""Summarize the document named "{document_name}" in 2-3 concise sentences.
Focus on the main topic and the most important points from this specific document."""

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
                    ]
                ),
            )

            return SummaryDTO(summary=response.text if response.text else "")

        except Exception as e:
            raise Exception(str(e))
