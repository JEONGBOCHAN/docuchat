# -*- coding: utf-8 -*-
"""Tests for RAG workflow backward compatibility."""

import pytest
from unittest.mock import Mock, patch

from src.workflows.rag import (
    create_rag_agent,
    run_rag_agent,
    AgentState,
    RAG_AGENT_SYSTEM_PROMPT,
    RAGAgentConfig,
)


class TestWorkflowsRagModule:
    """Tests for the workflows.rag module exports."""

    def test_agent_state_is_typed_dict(self):
        """Test that AgentState is a proper TypedDict."""
        # Create a valid state
        state: AgentState = {
            "channel_id": "test-channel",
            "query": "What is machine learning?",
            "conversation_history": [],
            "iteration": 0,
            "max_iterations": 3,
            "tool_results": [],
            "sources": [],
            "final_answer": None,
            "error": None,
        }

        # Verify all fields exist
        assert state["channel_id"] == "test-channel"
        assert state["query"] == "What is machine learning?"
        assert state["conversation_history"] == []
        assert state["iteration"] == 0
        assert state["max_iterations"] == 3
        assert state["tool_results"] == []
        assert state["sources"] == []
        assert state["final_answer"] is None
        assert state["error"] is None

    def test_rag_agent_system_prompt_exists(self):
        """Test that system prompt is defined and non-empty."""
        assert RAG_AGENT_SYSTEM_PROMPT is not None
        assert len(RAG_AGENT_SYSTEM_PROMPT) > 0
        assert "document" in RAG_AGENT_SYSTEM_PROMPT.lower()

    def test_rag_agent_config_export(self):
        """Test that RAGAgentConfig is properly exported."""
        config = RAGAgentConfig(channel_id="test")
        assert config.channel_id == "test"
        assert config.max_iterations == 3


class TestCreateRagAgent:
    """Tests for create_rag_agent function."""

    @patch("src.agents.rag_agent.get_settings")
    @patch("src.agents.rag_agent.GeminiService")
    @patch("src.agents.rag_agent.ChatGoogleGenerativeAI")
    @patch("src.agents.rag_agent.create_react_agent")
    def test_create_rag_agent_with_config(
        self,
        mock_create_react_agent,
        mock_chat_model,
        mock_gemini_service,
        mock_get_settings,
    ):
        """Test creating agent with RAGAgentConfig."""
        mock_get_settings.return_value = Mock(google_api_key="test-key")
        mock_create_react_agent.return_value = Mock()

        config = RAGAgentConfig(channel_id="test-channel")
        agent = create_rag_agent(config=config)

        assert agent is not None
        mock_create_react_agent.assert_called_once()

    @patch("src.agents.rag_agent.get_settings")
    @patch("src.agents.rag_agent.GeminiService")
    @patch("src.agents.rag_agent.ChatGoogleGenerativeAI")
    @patch("src.agents.rag_agent.create_react_agent")
    def test_create_rag_agent_with_channel_id(
        self,
        mock_create_react_agent,
        mock_chat_model,
        mock_gemini_service,
        mock_get_settings,
    ):
        """Test creating agent with channel_id parameter (backward compat)."""
        mock_get_settings.return_value = Mock(google_api_key="test-key")
        mock_create_react_agent.return_value = Mock()

        agent = create_rag_agent(channel_id="test-channel")

        assert agent is not None
        mock_create_react_agent.assert_called_once()

    def test_create_rag_agent_without_params_raises(self):
        """Test that creating agent without params raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_rag_agent()

        assert "Either config or channel_id must be provided" in str(exc_info.value)


class TestRunRagAgent:
    """Tests for run_rag_agent function."""

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_basic(self, mock_create_agent):
        """Test basic agent run."""
        mock_agent = Mock()
        mock_message = Mock()
        mock_message.content = "Test response"
        mock_agent.invoke.return_value = {"messages": [mock_message]}
        mock_create_agent.return_value = mock_agent

        result = run_rag_agent(
            channel_id="test-channel",
            query="What is AI?",
        )

        assert result["response"] == "Test response"
        assert result["error"] is None

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_with_all_params(self, mock_create_agent):
        """Test agent run with all parameters."""
        mock_agent = Mock()
        mock_message = Mock()
        mock_message.content = "Response with history"
        mock_agent.invoke.return_value = {"messages": [mock_message]}
        mock_create_agent.return_value = mock_agent

        result = run_rag_agent(
            channel_id="test-channel",
            query="Follow-up question",
            conversation_history=[{"role": "user", "content": "Previous"}],
            max_iterations=5,
            middleware=[Mock()],
        )

        assert result["response"] == "Response with history"

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_returns_required_fields(self, mock_create_agent):
        """Test that run_rag_agent returns all required fields."""
        mock_agent = Mock()
        mock_message = Mock()
        mock_message.content = "Answer"
        mock_agent.invoke.return_value = {"messages": [mock_message]}
        mock_create_agent.return_value = mock_agent

        result = run_rag_agent(
            channel_id="test-channel",
            query="Test",
        )

        # Verify all required fields are present
        assert "response" in result
        assert "sources" in result
        assert "iterations" in result
        assert "error" in result

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_handles_empty_messages(self, mock_create_agent):
        """Test handling of empty messages from agent."""
        mock_agent = Mock()
        mock_agent.invoke.return_value = {"messages": []}
        mock_create_agent.return_value = mock_agent

        result = run_rag_agent(
            channel_id="test-channel",
            query="Test",
        )

        assert result["response"] == "No response generated."

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_handles_exception(self, mock_create_agent):
        """Test error handling when agent raises exception."""
        mock_create_agent.side_effect = Exception("Test error")

        result = run_rag_agent(
            channel_id="test-channel",
            query="Test",
        )

        assert "Error" in result["response"]
        assert result["error"] == "Test error"
        assert result["sources"] == []
        assert result["iterations"] == 0
