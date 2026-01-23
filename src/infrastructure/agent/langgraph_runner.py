# -*- coding: utf-8 -*-
"""
LangGraph Agent Runner.

Implements AgentRunnerPort using LangGraph's create_react_agent.
This adapter wraps LangGraph to provide a clean interface for the application layer.

This is the key infrastructure component that prevents LangGraph framework
details from leaking into the application layer.
"""

from datetime import datetime
from typing import Any, Generator

from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from src.application.ports.agent_runner import (
    AgentRunnerPort,
    AgentConfig,
    AgentResult,
    AgentTool,
)
from src.application.ports.observability import AgentEventSinkPort
from src.application.dto.agent_event import (
    AgentStartedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    ToolStartedEvent,
    ToolCompletedEvent,
    generate_session_id,
)
from src.agents.tools.search_tools import (
    create_search_documents_tool,
    create_finish_tool,
)
from src.core.config import get_settings
from src.services.gemini import GeminiService


# Default system prompt for RAG agent
RAG_SYSTEM_PROMPT = """You are a document analysis assistant. Your task is to answer user questions based on uploaded documents.

## Available Tools
You have access to the following tools:
1. **search_documents**: Search for relevant information in the uploaded documents
2. **finish**: Complete the task and provide the final answer

## Instructions
1. When the user asks a question, use the search_documents tool to find relevant information
2. If the search results are insufficient, try searching with different keywords
3. Once you have enough information, use the finish tool to provide a complete answer
4. Always cite your sources in the answer

## Important Rules
- You MUST use the finish tool to complete the task
- Include citations from the documents in your final answer
- If no relevant information is found after searching, inform the user honestly
- Do not make up information - only use what you find in the documents
"""


class LangGraphAgentRunner(AgentRunnerPort):
    """AgentRunnerPort implementation using LangGraph.

    This runner creates a ReAct-style agent using LangGraph's
    create_react_agent function. It wraps LangGraph completely,
    exposing only the clean AgentRunnerPort interface.

    Example:
        runner = LangGraphAgentRunner(event_sink=event_sink)

        result = runner.run(
            query="What is AI?",
            config=AgentConfig(max_iterations=3),
            context={"channel_id": "channel-123"}
        )

    The caller doesn't need to know anything about LangGraph.
    """

    def __init__(
        self,
        event_sink: AgentEventSinkPort | None = None,
        gemini_service: GeminiService | None = None,
        model: str = "gemini-2.5-flash-preview-05-20",
    ):
        """Initialize the LangGraph runner.

        Args:
            event_sink: Optional event sink for observability.
            gemini_service: Optional GeminiService instance.
            model: The Gemini model to use.
        """
        self._event_sink = event_sink
        self._gemini_service = gemini_service or GeminiService()
        self._model = model
        self._settings = get_settings()

    def _create_agent(self, channel_id: str, config: AgentConfig):
        """Create a LangGraph agent for the specified channel.

        Args:
            channel_id: The channel to search in.
            config: Agent configuration.

        Returns:
            Compiled LangGraph agent.
        """
        # Create the LLM
        llm = ChatGoogleGenerativeAI(
            model=self._model,
            google_api_key=self._settings.google_api_key,
            temperature=config.temperature,
        )

        # Create tools
        search_tool = create_search_documents_tool(
            channel_id=channel_id,
            gemini_service=self._gemini_service,
        )
        finish_tool = create_finish_tool()

        tools = [search_tool, finish_tool]

        # Use custom system prompt if provided
        system_prompt = config.system_prompt or RAG_SYSTEM_PROMPT

        # Create the agent
        agent = create_react_agent(
            model=llm,
            tools=tools,
            state_modifier=system_prompt,
        )

        return agent

    def run(
        self,
        query: str,
        config: AgentConfig,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Run the agent to answer a query.

        Args:
            query: The user's question.
            config: Agent configuration.
            context: Context containing channel_id, conversation_history, etc.

        Returns:
            AgentResult with response and metadata.
        """
        context = context or {}
        channel_id = context.get("channel_id", "")
        conversation_history = context.get("conversation_history", [])
        session_id = context.get("session_id") or generate_session_id()

        # Emit: Agent Started
        if self._event_sink:
            self._event_sink.emit(AgentStartedEvent(
                session_id=session_id,
                query=query,
                channel_id=channel_id,
            ))

        try:
            agent = self._create_agent(channel_id, config)

            # Build messages
            messages = []
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(("user", content))
                    else:
                        messages.append(("assistant", content))

            messages.append(("user", query))

            # Emit: Tool Started
            tool_start_time = datetime.now()
            if self._event_sink:
                self._event_sink.emit(ToolStartedEvent(
                    session_id=session_id,
                    tool_name="search_documents",
                    tool_input={"query": query},
                ))

            # Run agent
            result = agent.invoke(
                {"messages": messages},
                config={"recursion_limit": config.max_iterations * 2 + 1}
            )

            # Calculate tool duration
            tool_duration_ms = (datetime.now() - tool_start_time).total_seconds() * 1000

            # Emit: Tool Completed
            if self._event_sink:
                self._event_sink.emit(ToolCompletedEvent(
                    session_id=session_id,
                    tool_name="search_documents",
                    duration_ms=tool_duration_ms,
                ))

            # Extract response
            final_message = result.get("messages", [])[-1] if result.get("messages") else None
            response_text = getattr(final_message, "content", str(final_message)) if final_message else "No response generated."

            # Extract sources and iterations
            sources, iterations, tool_calls = self._extract_metadata(result)

            # Emit: Agent Completed
            if self._event_sink:
                self._event_sink.emit(AgentCompletedEvent(
                    session_id=session_id,
                    response=response_text,
                    sources=sources,
                    iterations=iterations,
                ))

            return AgentResult(
                response=response_text,
                sources=sources,
                tool_calls=tool_calls,
                iterations=iterations,
                session_id=session_id,
                metadata={"channel_id": channel_id},
            )

        except Exception as e:
            # Emit: Agent Error
            if self._event_sink:
                self._event_sink.emit(AgentErrorEvent(
                    session_id=session_id,
                    error=str(e),
                    error_type=type(e).__name__,
                ))

            return AgentResult(
                response=f"Error: {str(e)}",
                sources=[],
                tool_calls=[],
                iterations=0,
                session_id=session_id,
                metadata={"error": str(e), "channel_id": channel_id},
            )

    def run_stream(
        self,
        query: str,
        config: AgentConfig,
        context: dict[str, Any] | None = None,
    ) -> Generator[dict, None, AgentResult]:
        """Run the agent with streaming events.

        Args:
            query: The user's question.
            config: Agent configuration.
            context: Context containing channel_id, etc.

        Yields:
            Event dictionaries.

        Returns:
            Final AgentResult.
        """
        context = context or {}
        channel_id = context.get("channel_id", "")
        conversation_history = context.get("conversation_history", [])
        session_id = context.get("session_id") or generate_session_id()

        # Emit: Agent Started
        if self._event_sink:
            self._event_sink.emit(AgentStartedEvent(
                session_id=session_id,
                query=query,
                channel_id=channel_id,
            ))

        yield {"event": "agent_started", "session_id": session_id}

        try:
            agent = self._create_agent(channel_id, config)

            # Build messages
            messages = []
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(("user", content))
                    else:
                        messages.append(("assistant", content))

            messages.append(("user", query))

            # Emit: Tool Started
            tool_start_time = datetime.now()
            if self._event_sink:
                self._event_sink.emit(ToolStartedEvent(
                    session_id=session_id,
                    tool_name="search_documents",
                    tool_input={"query": query},
                ))

            yield {"event": "tool_started", "tool": "search_documents"}

            # Use stream mode
            collected_chunks = []
            for chunk in agent.stream(
                {"messages": messages},
                config={"recursion_limit": config.max_iterations * 2 + 1},
                stream_mode="values",
            ):
                collected_chunks.append(chunk)
                # Yield intermediate updates
                if "messages" in chunk:
                    last_msg = chunk["messages"][-1] if chunk["messages"] else None
                    if last_msg and hasattr(last_msg, "content"):
                        yield {
                            "event": "content",
                            "content": getattr(last_msg, "content", ""),
                        }

            # Get final result from collected chunks
            result = collected_chunks[-1] if collected_chunks else {"messages": []}

            # Calculate tool duration
            tool_duration_ms = (datetime.now() - tool_start_time).total_seconds() * 1000

            # Emit: Tool Completed
            if self._event_sink:
                self._event_sink.emit(ToolCompletedEvent(
                    session_id=session_id,
                    tool_name="search_documents",
                    duration_ms=tool_duration_ms,
                ))

            yield {"event": "tool_completed", "tool": "search_documents"}

            # Extract final response
            final_message = result.get("messages", [])[-1] if result.get("messages") else None
            response_text = getattr(final_message, "content", str(final_message)) if final_message else "No response generated."

            # Extract metadata
            sources, iterations, tool_calls = self._extract_metadata(result)

            # Emit: Agent Completed
            if self._event_sink:
                self._event_sink.emit(AgentCompletedEvent(
                    session_id=session_id,
                    response=response_text,
                    sources=sources,
                    iterations=iterations,
                ))

            yield {"event": "agent_completed", "response": response_text}

            return AgentResult(
                response=response_text,
                sources=sources,
                tool_calls=tool_calls,
                iterations=iterations,
                session_id=session_id,
                metadata={"channel_id": channel_id},
            )

        except Exception as e:
            # Emit: Agent Error
            if self._event_sink:
                self._event_sink.emit(AgentErrorEvent(
                    session_id=session_id,
                    error=str(e),
                    error_type=type(e).__name__,
                ))

            yield {"event": "error", "error": str(e)}

            return AgentResult(
                response=f"Error: {str(e)}",
                sources=[],
                tool_calls=[],
                iterations=0,
                session_id=session_id,
                metadata={"error": str(e), "channel_id": channel_id},
            )

    def _extract_metadata(self, result: dict) -> tuple[list[dict], int, list[dict]]:
        """Extract sources, iterations, and tool calls from result.

        Args:
            result: LangGraph execution result.

        Returns:
            Tuple of (sources, iterations, tool_calls).
        """
        sources = []
        tool_calls = []
        iterations = 0

        for msg in result.get("messages", []):
            # Count tool calls as iterations
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                iterations += 1
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {}),
                    })

            # Extract sources from search results
            if hasattr(msg, "content") and isinstance(msg.content, str):
                if "[Source" in msg.content and "Found" in msg.content:
                    lines = msg.content.split("\n")
                    for line in lines:
                        if line.startswith("[Source"):
                            try:
                                source_part = line.split(":")[1].strip().rstrip("]")
                                if source_part and source_part not in [s.get("source") for s in sources]:
                                    sources.append({"source": source_part, "content": ""})
                            except (IndexError, AttributeError):
                                pass

        return sources, iterations, tool_calls

    def get_available_tools(self) -> list[AgentTool]:
        """Get list of tools available to this agent.

        Returns:
            List of AgentTool definitions.
        """
        return [
            AgentTool(
                name="search_documents",
                description="Search for relevant information in uploaded documents",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
            ),
            AgentTool(
                name="finish",
                description="Complete the task and provide the final answer",
                parameters={
                    "answer": {
                        "type": "string",
                        "description": "The final answer to the user's question",
                    }
                },
            ),
        ]
