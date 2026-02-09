# -*- coding: utf-8 -*-
"""Tests for GeminiConversationSummaryAdapter."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.external.gemini.conversation_summary import (
    GeminiConversationSummaryAdapter,
)


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def adapter(mock_client):
    return GeminiConversationSummaryAdapter(client=mock_client)


class TestGeminiConversationSummaryAdapter:
    """Tests for the Gemini conversation summary adapter."""

    def test_summarize_incremental_first_summary(self, adapter, mock_client):
        """First summary (no previous) should create new summary."""
        mock_response = MagicMock()
        mock_response.text = "### Facts\n- User wants to learn Python"
        mock_client.models.generate_content.return_value = mock_response

        result = adapter.summarize_incremental(
            previous_summary="",
            new_turns=[
                {"role": "user", "content": "I want to learn Python"},
                {"role": "assistant", "content": "Great! Python is a versatile language."},
            ],
        )

        assert result.success
        assert "Facts" in result.summary
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert "Conversation Turns" in call_args.kwargs.get("contents", call_args[1].get("contents", [""]))[0]

    def test_summarize_incremental_with_previous(self, adapter, mock_client):
        """Merge with previous summary."""
        mock_response = MagicMock()
        mock_response.text = "### Facts\n- User wants Python web dev\n### Decisions\n- Using FastAPI"
        mock_client.models.generate_content.return_value = mock_response

        result = adapter.summarize_incremental(
            previous_summary="### Facts\n- User wants to learn Python",
            new_turns=[
                {"role": "user", "content": "I want to build web apps"},
                {"role": "assistant", "content": "FastAPI is a good choice for Python web development."},
            ],
        )

        assert result.success
        assert "Decisions" in result.summary
        call_args = mock_client.models.generate_content.call_args
        content = call_args.kwargs.get("contents", call_args[1].get("contents", [""]))[0]
        assert "Previous Summary" in content

    def test_summarize_empty_turns_returns_previous(self, adapter, mock_client):
        """Empty turns should return previous summary unchanged."""
        result = adapter.summarize_incremental(
            previous_summary="existing summary",
            new_turns=[],
        )
        assert result.success
        assert result.summary == "existing summary"
        mock_client.models.generate_content.assert_not_called()

    def test_summarize_api_error_returns_previous(self, adapter, mock_client):
        """API error should fallback to previous summary."""
        mock_client.models.generate_content.side_effect = Exception("API error")

        result = adapter.summarize_incremental(
            previous_summary="safe fallback",
            new_turns=[{"role": "user", "content": "test"}],
        )
        assert not result.success
        assert result.summary == "safe fallback"
        assert result.error is not None

    def test_summarize_empty_response_returns_previous(self, adapter, mock_client):
        """Empty API response should fallback to previous summary."""
        mock_response = MagicMock()
        mock_response.text = ""
        mock_client.models.generate_content.return_value = mock_response

        result = adapter.summarize_incremental(
            previous_summary="fallback",
            new_turns=[{"role": "user", "content": "test"}],
        )
        assert not result.success
        assert result.summary == "fallback"

    def test_max_tokens_passed_to_prompt(self, adapter, mock_client):
        """max_tokens should appear in the prompt."""
        mock_response = MagicMock()
        mock_response.text = "summary"
        mock_client.models.generate_content.return_value = mock_response

        adapter.summarize_incremental(
            previous_summary="",
            new_turns=[{"role": "user", "content": "test"}],
            max_tokens=500,
        )

        call_args = mock_client.models.generate_content.call_args
        content = call_args.kwargs.get("contents", call_args[1].get("contents", [""]))[0]
        assert "500" in content
