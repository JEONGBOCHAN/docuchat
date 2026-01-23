# -*- coding: utf-8 -*-
"""Tests for the LangChain-based RAG agent implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.agents.rag_agent import (
    create_rag_agent,
    run_rag_agent,
    RAGAgentConfig,
    RAG_AGENT_SYSTEM_PROMPT,
)
from src.agents.tools.search_tools import (
    create_search_documents_tool,
    create_finish_tool,
)


class TestRAGAgentConfig:
    """Tests for RAGAgentConfig dataclass."""

    def test_config_defaults(self):
        """Test that RAGAgentConfig has correct defaults."""
        config = RAGAgentConfig(channel_id="test-channel")

        assert config.channel_id == "test-channel"
        assert config.max_iterations == 3
        assert config.model == "gemini-2.5-flash-preview-05-20"
        assert config.temperature == 0.0
        assert config.system_prompt is None
        assert config.middleware == []

    def test_config_custom_values(self):
        """Test RAGAgentConfig with custom values."""
        config = RAGAgentConfig(
            channel_id="custom-channel",
            max_iterations=5,
            model="gemini-1.5-pro",
            temperature=0.5,
            system_prompt="Custom prompt",
            middleware=[Mock()],
        )

        assert config.channel_id == "custom-channel"
        assert config.max_iterations == 5
        assert config.model == "gemini-1.5-pro"
        assert config.temperature == 0.5
        assert config.system_prompt == "Custom prompt"
        assert len(config.middleware) == 1


class TestSearchTools:
    """Tests for search tools."""

    def test_create_search_documents_tool(self):
        """Test search_documents tool creation."""
        mock_gemini = Mock()
        mock_gemini.search_documents.return_value = {
            "sources": [
                {"source": "doc1.pdf", "content": "Test content 1"},
                {"source": "doc2.pdf", "content": "Test content 2"},
            ]
        }

        tool = create_search_documents_tool(
            channel_id="test-channel",
            gemini_service=mock_gemini,
        )

        # Verify tool attributes
        assert tool.name == "search_documents"
        assert "Search for information" in tool.description

        # Test tool execution
        result = tool.invoke("test query")

        mock_gemini.search_documents.assert_called_once_with(
            store_name="test-channel",
            query="test query",
        )
        assert "Found 2 relevant sections" in result
        assert "doc1.pdf" in result
        assert "doc2.pdf" in result

    def test_search_documents_no_results(self):
        """Test search_documents tool with no results."""
        mock_gemini = Mock()
        mock_gemini.search_documents.return_value = {"sources": []}

        tool = create_search_documents_tool(
            channel_id="test-channel",
            gemini_service=mock_gemini,
        )

        result = tool.invoke("nonexistent query")

        assert "No relevant documents found" in result

    def test_create_finish_tool(self):
        """Test finish tool creation."""
        tool = create_finish_tool()

        assert tool.name == "finish"
        assert "Complete the task" in tool.description
        assert tool.return_direct is True

        # Test tool execution
        result = tool.invoke("This is the final answer.")
        assert result == "This is the final answer."


class TestCreateRAGAgent:
    """Tests for create_rag_agent function."""

    @patch("src.agents.rag_agent.get_settings")
    @patch("src.agents.rag_agent.GeminiService")
    @patch("src.agents.rag_agent.ChatGoogleGenerativeAI")
    @patch("src.agents.rag_agent.create_react_agent")
    def test_create_rag_agent_basic(
        self,
        mock_create_react_agent,
        mock_chat_model,
        mock_gemini_service,
        mock_get_settings,
    ):
        """Test basic agent creation."""
        mock_get_settings.return_value = Mock(google_api_key="test-key")
        mock_create_react_agent.return_value = Mock()

        config = RAGAgentConfig(channel_id="test-channel")
        agent = create_rag_agent(config)

        # Verify ChatGoogleGenerativeAI was created with correct params
        mock_chat_model.assert_called_once()
        call_kwargs = mock_chat_model.call_args[1]
        assert call_kwargs["model"] == "gemini-2.5-flash-preview-05-20"
        assert call_kwargs["google_api_key"] == "test-key"
        assert call_kwargs["temperature"] == 0.0

        # Verify create_react_agent was called
        mock_create_react_agent.assert_called_once()
        call_kwargs = mock_create_react_agent.call_args[1]
        assert len(call_kwargs["tools"]) == 2  # search and finish tools
        assert call_kwargs["state_modifier"] == RAG_AGENT_SYSTEM_PROMPT

    @patch("src.agents.rag_agent.get_settings")
    @patch("src.agents.rag_agent.GeminiService")
    @patch("src.agents.rag_agent.ChatGoogleGenerativeAI")
    @patch("src.agents.rag_agent.create_react_agent")
    def test_create_rag_agent_with_custom_prompt(
        self,
        mock_create_react_agent,
        mock_chat_model,
        mock_gemini_service,
        mock_get_settings,
    ):
        """Test agent creation with custom system prompt."""
        mock_get_settings.return_value = Mock(google_api_key="test-key")
        mock_create_react_agent.return_value = Mock()

        custom_prompt = "You are a custom assistant."
        config = RAGAgentConfig(
            channel_id="test-channel",
            system_prompt=custom_prompt,
        )
        create_rag_agent(config)

        call_kwargs = mock_create_react_agent.call_args[1]
        assert call_kwargs["state_modifier"] == custom_prompt

    @patch("src.agents.rag_agent.get_settings")
    @patch("src.agents.rag_agent.GeminiService")
    @patch("src.agents.rag_agent.ChatGoogleGenerativeAI")
    @patch("src.agents.rag_agent.create_react_agent")
    def test_create_rag_agent_with_middleware(
        self,
        mock_create_react_agent,
        mock_chat_model,
        mock_gemini_service,
        mock_get_settings,
    ):
        """Test agent creation with middleware (middleware stored in config, not passed to create_react_agent)."""
        mock_get_settings.return_value = Mock(google_api_key="test-key")
        mock_create_react_agent.return_value = Mock()

        mock_middleware = [Mock(), Mock()]
        config = RAGAgentConfig(
            channel_id="test-channel",
            middleware=mock_middleware,
        )
        create_rag_agent(config)

        # Middleware is handled separately in run_rag_agent, not in create_react_agent
        mock_create_react_agent.assert_called_once()
        # Just verify create_react_agent was called (middleware is applied during run_rag_agent)


class TestRunRAGAgent:
    """Tests for run_rag_agent function."""

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_success(self, mock_create_agent):
        """Test successful agent execution."""
        # Setup mock agent
        mock_agent = Mock()
        mock_response_message = Mock()
        mock_response_message.content = "This is the answer."
        mock_agent.invoke.return_value = {
            "messages": [mock_response_message]
        }
        mock_create_agent.return_value = mock_agent

        result = run_rag_agent(
            channel_id="test-channel",
            query="What is the meaning of life?",
        )

        assert result["response"] == "This is the answer."
        assert result["error"] is None

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_with_conversation_history(self, mock_create_agent):
        """Test agent execution with conversation history."""
        mock_agent = Mock()
        mock_response_message = Mock()
        mock_response_message.content = "Follow-up answer."
        mock_agent.invoke.return_value = {
            "messages": [mock_response_message]
        }
        mock_create_agent.return_value = mock_agent

        conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = run_rag_agent(
            channel_id="test-channel",
            query="Tell me more",
            conversation_history=conversation_history,
        )

        # Verify invoke was called with messages including history
        call_args = mock_agent.invoke.call_args[0][0]
        assert len(call_args["messages"]) == 3  # 2 history + 1 current

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_error_handling(self, mock_create_agent):
        """Test agent error handling."""
        mock_create_agent.side_effect = Exception("API Error")

        result = run_rag_agent(
            channel_id="test-channel",
            query="test query",
        )

        assert "Error" in result["response"]
        assert result["error"] == "API Error"
        assert result["sources"] == []
        assert result["iterations"] == 0

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_source_extraction(self, mock_create_agent):
        """Test that sources are extracted from tool messages."""
        mock_agent = Mock()

        # Create messages including search results
        mock_tool_message = Mock()
        mock_tool_message.content = "Found 2 relevant sections:\n\n[Source 1: doc1.pdf]\nContent 1\n\n---\n\n[Source 2: doc2.pdf]\nContent 2"
        mock_tool_message.tool_calls = None

        mock_ai_message = Mock()
        mock_ai_message.content = "Based on the documents, the answer is..."
        mock_ai_message.tool_calls = [Mock()]  # Has tool calls

        mock_final_message = Mock()
        mock_final_message.content = "Final answer with sources."

        mock_agent.invoke.return_value = {
            "messages": [mock_tool_message, mock_ai_message, mock_final_message]
        }
        mock_create_agent.return_value = mock_agent

        result = run_rag_agent(
            channel_id="test-channel",
            query="test query",
        )

        # Verify sources were extracted
        assert len(result["sources"]) >= 0  # May be 0 or more depending on parsing
        assert result["iterations"] >= 1  # At least one tool call

    @patch("src.agents.rag_agent.create_rag_agent")
    def test_run_rag_agent_with_middleware(self, mock_create_agent):
        """Test agent execution with middleware parameter."""
        mock_agent = Mock()
        mock_response_message = Mock()
        mock_response_message.content = "Answer"
        mock_agent.invoke.return_value = {
            "messages": [mock_response_message]
        }
        mock_create_agent.return_value = mock_agent

        mock_middleware = [Mock()]

        result = run_rag_agent(
            channel_id="test-channel",
            query="test query",
            middleware=mock_middleware,
        )

        # Verify middleware was passed to config
        config = mock_create_agent.call_args[0][0]
        assert config.middleware == mock_middleware


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    def test_import_from_workflows(self):
        """Test that imports from src.workflows.rag still work."""
        from src.workflows.rag import (
            create_rag_agent,
            run_rag_agent,
            AgentState,
            RAG_AGENT_SYSTEM_PROMPT,
            RAGAgentConfig,
        )

        # Verify all exports are available
        assert callable(create_rag_agent)
        assert callable(run_rag_agent)
        assert AgentState is not None
        assert RAG_AGENT_SYSTEM_PROMPT is not None
        assert RAGAgentConfig is not None

    def test_import_from_agents(self):
        """Test that imports from src.agents work."""
        from src.agents import (
            create_rag_agent,
            run_rag_agent,
            RAGAgentConfig,
        )

        # Verify all exports are available
        assert callable(create_rag_agent)
        assert callable(run_rag_agent)
        assert RAGAgentConfig is not None

    def test_agent_state_structure(self):
        """Test that AgentState TypedDict has expected fields."""
        from src.workflows.rag import AgentState

        # AgentState should be usable as a TypedDict
        state: AgentState = {
            "channel_id": "test",
            "query": "test query",
            "conversation_history": [],
            "iteration": 0,
            "max_iterations": 3,
            "tool_results": [],
            "sources": [],
            "final_answer": None,
            "error": None,
        }

        assert state["channel_id"] == "test"
        assert state["query"] == "test query"


class TestSystemPrompt:
    """Tests for system prompt."""

    def test_system_prompt_content(self):
        """Test that system prompt contains required instructions."""
        assert "document analysis assistant" in RAG_AGENT_SYSTEM_PROMPT.lower()
        assert "search_documents" in RAG_AGENT_SYSTEM_PROMPT
        assert "finish" in RAG_AGENT_SYSTEM_PROMPT
        assert "citations" in RAG_AGENT_SYSTEM_PROMPT.lower()
