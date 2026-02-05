# -*- coding: utf-8 -*-
"""
Agent Runner Port.

Defines the interface for agent execution.
This abstracts the actual agent framework (LangGraph, AutoGen, etc.)

This is the key port that prevents framework leakage into the application layer.
The ProcessQueryUseCase calls AgentRunnerPort without knowing whether
LangGraph, AutoGen, or any other framework is used underneath.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class AgentTool:
    """Definition of a tool available to the agent.

    Attributes:
        name: Tool identifier
        description: What the tool does (for the agent to understand)
        parameters: Tool parameter schema
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result of an agent execution.

    Attributes:
        response: The final answer/response
        sources: Sources used (for RAG)
        tool_calls: List of tools that were called
        iterations: Number of reasoning iterations
        session_id: Session identifier for tracking
        metadata: Additional execution metadata
    """

    response: str
    sources: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    iterations: int = 0
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for agent execution.

    Attributes:
        max_iterations: Maximum reasoning iterations
        temperature: LLM temperature
        tools: List of tools available to the agent
        system_prompt: Custom system prompt
    """

    max_iterations: int = 15
    temperature: float = 0.0
    tools: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    document_context: str | None = None


class AgentRunnerPort(ABC):
    """Abstract interface for agent execution.

    Implementations of this port handle running AI agents with
    tool-calling capabilities. This allows the application to use
    different agent frameworks without changing business logic.

    The key benefit is that LangGraph, AutoGen, or any other framework
    stays in the infrastructure layer, while the application only
    deals with this clean interface.

    Example:
        # Using LangGraph
        runner = LangGraphAgentRunner(llm, tools)
        result = runner.run("What documents mention AI?", config)

        # Can be replaced with AutoGen
        runner = AutoGenAgentRunner(llm, tools)
        result = runner.run("What documents mention AI?", config)
    """

    @abstractmethod
    def run(
        self,
        query: str,
        config: AgentConfig,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Run the agent to answer a query.

        Args:
            query: The user's question
            config: Agent configuration
            context: Additional context (channel_id, history, etc.)

        Returns:
            AgentResult with response and metadata
        """
        pass

    @abstractmethod
    def run_stream(
        self,
        query: str,
        config: AgentConfig,
        context: dict[str, Any] | None = None,
    ) -> Generator[dict, None, AgentResult]:
        """Run the agent with streaming events.

        Args:
            query: The user's question
            config: Agent configuration
            context: Additional context

        Yields:
            Event dictionaries (tool_start, tool_end, content, etc.)

        Returns:
            Final AgentResult
        """
        pass

    @abstractmethod
    def get_available_tools(self) -> list[AgentTool]:
        """Get list of tools available to this agent.

        Returns:
            List of AgentTool definitions
        """
        pass
