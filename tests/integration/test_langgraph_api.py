# -*- coding: utf-8 -*-
"""Integration test for LangGraph API compatibility.

This test verifies that create_react_agent is called with correct parameters
without mocking, to catch API changes like state_modifier -> prompt.
"""

import warnings

import pytest
from unittest.mock import Mock, patch

# Suppress langgraph 1.0 deprecation warning (langchain package not installed)
warnings.filterwarnings(
    "ignore",
    message="create_react_agent has been moved",
)


class TestLangGraphAPICompatibility:
    """Test LangGraph API compatibility without heavy mocking."""

    def test_create_react_agent_prompt_parameter(self):
        """Verify create_react_agent accepts 'prompt' parameter.

        This is the key test - if LangGraph API changed and 'prompt'
        is no longer valid, this test will fail.
        """
        from langgraph.prebuilt import create_react_agent
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.tools import tool

        # Create a minimal mock LLM
        mock_llm = Mock(spec=ChatGoogleGenerativeAI)
        mock_llm.bind_tools = Mock(return_value=mock_llm)

        # Create a simple tool
        @tool
        def dummy_tool(query: str) -> str:
            """A dummy tool for testing."""
            return "test result"

        # This should NOT raise TypeError about 'state_modifier'
        # If it does, the API has changed and we need to update our code
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="create_react_agent has been moved")
                agent = create_react_agent(
                    model=mock_llm,
                    tools=[dummy_tool],
                    prompt="You are a helpful assistant.",
                )
            assert agent is not None
        except TypeError as e:
            if "state_modifier" in str(e):
                pytest.fail(
                    "LangGraph API changed! 'state_modifier' is being used "
                    "somewhere instead of 'prompt'. Check all usages."
                )
            elif "prompt" in str(e):
                pytest.fail(
                    f"LangGraph API changed! 'prompt' parameter is no longer valid: {e}"
                )
            raise

    def test_langgraph_runner_creates_without_error(self):
        """Test that LangGraphAgentRunner doesn't raise state_modifier error."""
        from src.modules.conversation.infrastructure.agent.langgraph_runner import LangGraphAgentRunner
        from src.shared.kernel.contracts.ports.agent_runner import AgentConfig

        runner = LangGraphAgentRunner(
            event_sink=None,
            document_search=Mock(),
        )

        # Patch only the LLM to avoid API calls
        with patch("src.modules.conversation.infrastructure.agent.langgraph_runner.ChatGoogleGenerativeAI") as mock_llm_class, \
             patch("src.modules.conversation.infrastructure.agent.langgraph_runner.get_settings") as mock_settings:

            mock_settings.return_value = Mock(google_api_key="fake-key")
            mock_llm = Mock()
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm_class.return_value = mock_llm

            config = AgentConfig(max_iterations=3)

            try:
                agent = runner._create_agent("test-channel", config)
                assert agent is not None
            except TypeError as e:
                if "state_modifier" in str(e):
                    pytest.fail(
                        f"langgraph_runner.py still using 'state_modifier': {e}"
                    )
                raise
