# -*- coding: utf-8 -*-
"""
LangGraph Agent Runner.

Implements AgentRunnerPort using LangGraph's create_react_agent.
This adapter wraps LangGraph to provide a clean interface for the application layer.

This is the key infrastructure component that prevents LangGraph framework
details from leaking into the application layer.
"""

import logging
from datetime import datetime
from typing import Any, Generator

from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

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
    create_web_search_tool,
    create_arxiv_search_tool,
)
from src.core.config import get_settings, GeminiModels
from src.application.ports.document_search import DocumentSearchPort
from src.application.ports.web_search import WebSearchPort
from src.agents.middlewares.dashboard import DashboardMiddleware


# Default system prompt for RAG agent
RAG_SYSTEM_PROMPT = """You are an intelligent assistant with access to multiple tools. Choose the appropriate tool based on the user's question.

## Available Tools
1. **search_documents**: Search for relevant information in the uploaded documents
   - Use for questions about uploaded files, papers, or documents
   - Returns excerpts with source citations

2. **web_search**: Search the internet for current information
   - Use for current events, news, real-world facts
   - Use for restaurants, places, weather, locations
   - Use for anything requiring up-to-date web data

3. **arxiv_search**: Search arXiv for academic papers and research
   - Use for academic papers, research, scientific studies
   - Use for latest research on specific topics
   - Use for technical papers in AI, ML, physics, math, computer science, etc.
   - Returns paper titles, authors, summaries, and PDF links

## Instructions
1. Analyze the user's question to determine which tool is most appropriate
2. For document-related questions → use search_documents
3. For real-world/current information → use web_search
4. For academic research/papers → use arxiv_search
5. You can use multiple tools if needed (e.g., search documents first, then arxiv for related research)
6. Once you have enough information, respond directly to the user with a complete answer
7. Always cite your sources in the answer

## Important Rules
- Choose the right tool based on the question type
- After gathering information, respond directly - do NOT call unnecessary tools
- Include citations in your answer (e.g., [Source 1] for documents, [Web 1] for web results, [Paper 1] for arXiv)
- If no relevant information is found, inform the user honestly
- Do not make up information - only use what you find from the tools
- Be efficient: gather what you need and provide your answer. Do not keep searching endlessly.
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
            config=AgentConfig(),  # defaults to max_iterations=15
            context={"channel_id": "channel-123"}
        )

    The caller doesn't need to know anything about LangGraph.
    """

    def __init__(
        self,
        event_sink: AgentEventSinkPort | None = None,
        document_search: DocumentSearchPort | None = None,
        model: str = GeminiModels.DEFAULT,
        dashboard_middleware: DashboardMiddleware | None = None,
    ):
        """Initialize the LangGraph runner.

        Args:
            event_sink: Optional event sink for observability.
            document_search: Optional DocumentSearchPort instance.
            model: The Gemini model to use.
            dashboard_middleware: Optional DashboardMiddleware for LLM node display.
        """
        self._event_sink = event_sink
        if document_search is None:
            # Lazy import to avoid circular dependency
            from src.infrastructure.di import create_document_search
            document_search = create_document_search()
        self._document_search = document_search
        self._model = model
        self._settings = get_settings()
        self._dashboard_middleware = dashboard_middleware

    def _create_agent(self, channel_id: str, config: AgentConfig, streaming: bool = False):
        """Create a LangGraph agent for the specified channel.

        Args:
            channel_id: The channel to search in.
            config: Agent configuration.
            streaming: Whether to enable token-by-token streaming.

        Returns:
            Compiled LangGraph agent.
        """
        # Create the LLM with streaming option
        llm = ChatGoogleGenerativeAI(
            model=self._model,
            google_api_key=self._settings.google_api_key,
            temperature=config.temperature,
            streaming=streaming,
        )

        # Create tools
        search_tool = create_search_documents_tool(
            channel_id=channel_id,
            document_search=self._document_search,
        )

        # Create web search tool (import locally to avoid circular dependency)
        from src.infrastructure.di import create_web_search, create_arxiv_search
        web_search_adapter = create_web_search()
        web_tool = create_web_search_tool(web_search_port=web_search_adapter)

        # Create arxiv search tool
        arxiv_search_adapter = create_arxiv_search()
        arxiv_tool = create_arxiv_search_tool(arxiv_search_port=arxiv_search_adapter)

        tools = [search_tool, web_tool, arxiv_tool]

        # Use custom system prompt if provided
        system_prompt = config.system_prompt or RAG_SYSTEM_PROMPT

        # Create the agent with prompt parameter
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
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

            # Emit LLM start event for synchronous run
            if self._dashboard_middleware:
                self._dashboard_middleware.on_llm_start("llm_response", {"channel_id": channel_id})

            # Run agent
            agent_start_time = datetime.now()
            result = agent.invoke(
                {"messages": messages},
                config={"recursion_limit": config.max_iterations * 2 + 1}
            )
            agent_duration_ms = (datetime.now() - agent_start_time).total_seconds() * 1000

            # Emit LLM end event for synchronous run
            if self._dashboard_middleware:
                self._dashboard_middleware.on_llm_end("llm_response", {"channel_id": channel_id})

            # Emit tool events based on actual tool calls in result
            if self._event_sink:
                for msg in result.get("messages", []):
                    # AIMessage with tool_calls indicates tool usage
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = tc.get("name", "")
                            tool_args = tc.get("args", {})
                            self._event_sink.emit(ToolStartedEvent(
                                session_id=session_id,
                                tool_name=tool_name,
                                tool_input=tool_args,
                            ))
                            # Immediately emit completed (since invoke is synchronous)
                            self._event_sink.emit(ToolCompletedEvent(
                                session_id=session_id,
                                tool_name=tool_name,
                                duration_ms=agent_duration_ms / max(1, len(msg.tool_calls)),
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
            agent = self._create_agent(channel_id, config, streaming=True)

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

            # Track tool calls dynamically
            tool_start_times: dict[str, datetime] = {}
            active_tools: set[str] = set()

            # Track LLM response state for dashboard middleware
            llm_response_started = False
            current_llm_role = "llm_response"

            # Use stream mode "messages" for token-by-token streaming
            final_response = ""
            final_messages = []
            for msg, metadata in agent.stream(
                {"messages": messages},
                config={"recursion_limit": config.max_iterations * 2 + 1},
                stream_mode="messages",
            ):
                final_messages.append(msg)

                # Get message type
                msg_type = getattr(msg, "type", None) or type(msg).__name__.lower()

                # Skip HumanMessage (user's query)
                if "human" in str(msg_type).lower():
                    continue

                # Detect tool calls from AIMessage (agent deciding to use a tool)
                if "ai" in str(msg_type).lower():
                    tool_calls = getattr(msg, "tool_calls", None)
                    if tool_calls:
                        for tc in tool_calls:
                            tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                            if tool_name and tool_name not in active_tools:
                                active_tools.add(tool_name)
                                tool_start_times[tool_name] = datetime.now()

                                # Emit: Tool Started
                                if self._event_sink:
                                    tool_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                                    self._event_sink.emit(ToolStartedEvent(
                                        session_id=session_id,
                                        tool_name=tool_name,
                                        tool_input=tool_args,
                                    ))
                                yield {"event": "tool_started", "tool": tool_name}

                # Detect ToolMessage (tool execution completed)
                if "tool" in str(msg_type).lower():
                    tool_name = getattr(msg, "name", "")
                    if tool_name and tool_name in active_tools:
                        active_tools.discard(tool_name)
                        start_time = tool_start_times.pop(tool_name, datetime.now())
                        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                        # Emit: Tool Completed
                        if self._event_sink:
                            self._event_sink.emit(ToolCompletedEvent(
                                session_id=session_id,
                                tool_name=tool_name,
                                duration_ms=duration_ms,
                            ))
                        yield {"event": "tool_completed", "tool": tool_name}
                    continue  # Skip tool message content from final response

                # Get content from the message chunk
                content = getattr(msg, "content", "")

                # Handle content that might be a list (multi-part messages from AI)
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    )

                # For AIMessageChunk, yield the content token (direct LLM response)
                if content and "ai" in str(msg_type).lower():
                    # LLM response started - emit llm_start event via middleware
                    if not llm_response_started and self._dashboard_middleware:
                        llm_response_started = True
                        self._dashboard_middleware.on_llm_start(current_llm_role, {"channel_id": channel_id})

                    final_response += content
                    yield {
                        "event": "content",
                        "content": content,
                    }

            # LLM response completed - emit llm_end event via middleware
            if llm_response_started and self._dashboard_middleware:
                self._dashboard_middleware.on_llm_end(current_llm_role, {"channel_id": channel_id})

            # Build result from collected messages
            result = {"messages": final_messages, "response": final_response}

            # Use accumulated response from streaming
            response_text = result.get("response", "") or "No response generated."

            # Handle response that might be a list
            if isinstance(response_text, list):
                response_text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in response_text
                )

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
                name="web_search",
                description="Search the internet for current information, news, places, etc.",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "The web search query",
                    }
                },
            ),
            AgentTool(
                name="arxiv_search",
                description="Search arXiv for academic papers, research, and scientific studies",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "The search query for academic papers",
                    }
                },
            ),
        ]
