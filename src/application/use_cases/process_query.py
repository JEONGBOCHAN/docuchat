# -*- coding: utf-8 -*-
"""
Process Query Use Case.

This is the main use case for handling user queries. It orchestrates:
1. Agent execution (which decides what tools to use)
2. Event emission for observability
3. Response formatting

The LLM (through the AgentRunner) decides whether to:
- Answer directly (no tools needed)
- Search documents (RAG)
- Search the web
- Use multiple tools

This replaces rule-based routing with LLM-based decision making.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Generator

from src.application.ports import (
    AgentRunnerPort,
    AgentConfig,
    AgentEventSinkPort,
    DocumentSearchPort,
    WebSearchPort,
)
from src.application.dto.agent_event import (
    AgentErrorEvent,
    generate_session_id,
)


@dataclass
class QueryResult:
    """Result of processing a query.

    Attributes:
        response: The generated answer
        sources: List of sources used (documents, web pages)
        session_id: Session ID for tracking
        iterations: Number of agent iterations
        tools_used: Which tools were invoked
        metadata: Additional result metadata
    """

    response: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    session_id: str | None = None
    iterations: int = 0
    tools_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ProcessQueryUseCase:
    """Use case for processing user queries with an AI agent.

    This use case coordinates:
    1. AgentRunner - executes the AI agent (LangGraph abstracted away)
    2. EventSink - emits events for dashboard observability
    3. DocumentSearch - RAG search (when agent decides to use it)
    4. WebSearch - web search (when agent decides to use it)

    The key insight is that the LLM decides which tools to use, not
    hardcoded rules. This makes the system more flexible and intelligent.

    Example:
        use_case = ProcessQueryUseCase(
            agent_runner=langgraph_runner,
            event_sink=event_store,
            document_search=gemini_adapter,
            web_search=tavily_adapter,
        )

        result = use_case.execute(
            query="What does the document say about AI?",
            channel_id="channel-123",
        )
    """

    def __init__(
        self,
        agent_runner: AgentRunnerPort,
        event_sink: AgentEventSinkPort | None = None,
        document_search: DocumentSearchPort | None = None,
        web_search: WebSearchPort | None = None,
        enabled_tools: list[str] | None = None,
    ):
        """Initialize the use case with dependencies.

        Args:
            agent_runner: The agent execution engine
            event_sink: Optional event sink for observability
            document_search: Optional document search adapter
            web_search: Optional web search adapter
            enabled_tools: Explicit list of tool names to enable.
                If provided, overrides port-based detection.
                If None, falls back to checking document_search/web_search ports.
        """
        self.agent_runner = agent_runner
        self.event_sink = event_sink
        self.document_search = document_search
        self.web_search = web_search
        self._enabled_tools = enabled_tools

    def _resolve_tools(self) -> list[str]:
        """Resolve which tools should be available to the agent.

        If enabled_tools was explicitly provided, use it directly.
        Otherwise, fall back to port-based detection (backward compat).

        Returns:
            List of tool name strings.
        """
        if self._enabled_tools is not None:
            return list(self._enabled_tools)

        # Legacy port-based detection
        available_tools = []
        if self.document_search:
            available_tools.append("search_documents")
        if self.web_search:
            available_tools.append("web_search")
        return available_tools

    def execute(
        self,
        query: str,
        channel_id: str,
        conversation_history: list[dict[str, str]] | Callable[[], list[dict[str, str]]] | None = None,
        max_iterations: int = 15,
        session_id: str | None = None,
        document_context: str | None = None,
        thread_id: str | None = None,
    ) -> QueryResult:
        """Execute the query processing.

        The agent will autonomously decide:
        - Whether to search documents
        - Whether to search the web
        - Whether to answer directly
        - How many iterations to take

        Args:
            query: The user's question
            channel_id: The channel context for document search
            conversation_history: Previous conversation for context.
                Accepts a list of message dicts or a callable that returns one
                (lazy loading — the runner invokes it only when needed).
            max_iterations: Maximum agent iterations
            session_id: Optional session ID (generated if not provided)
            document_context: Optional document summaries to inject into prompt

        Returns:
            QueryResult with response, sources, and metadata
        """
        # Generate session ID if needed
        if not session_id:
            session_id = generate_session_id()

        try:
            # Determine available tools
            available_tools = self._resolve_tools()

            # Configure agent
            config = AgentConfig(
                max_iterations=max_iterations,
                tools=available_tools,
                document_context=document_context,
            )

            # Build context (include session_id so the runner uses the same one)
            context = {
                "channel_id": channel_id,
                "conversation_history": conversation_history or [],
                "session_id": session_id,
            }
            if thread_id:
                context["thread_id"] = thread_id

            # Run agent (runner emits start/complete/error events)
            agent_result = self.agent_runner.run(
                query=query,
                config=config,
                context=context,
            )

            # Build result
            result = QueryResult(
                response=agent_result.response,
                sources=agent_result.sources,
                session_id=session_id,
                iterations=agent_result.iterations,
                tools_used=[tc.get("name", "") for tc in agent_result.tool_calls],
                metadata=agent_result.metadata,
            )

            return result

        except Exception as e:
            return QueryResult(
                response=f"Error processing query: {str(e)}",
                session_id=session_id,
                error=str(e),
            )

    def execute_stream(
        self,
        query: str,
        channel_id: str,
        conversation_history: list[dict[str, str]] | Callable[[], list[dict[str, str]]] | None = None,
        max_iterations: int = 15,
        session_id: str | None = None,
        document_context: str | None = None,
        thread_id: str | None = None,
    ) -> Generator[dict, None, QueryResult]:
        """Execute query processing with streaming events.

        This method streams events as the agent processes the query,
        allowing real-time updates to be sent to clients via SSE.

        Args:
            query: The user's question
            channel_id: The channel context for document search
            conversation_history: Previous conversation for context.
                Accepts a list of message dicts or a callable (lazy loading).
            max_iterations: Maximum agent iterations
            session_id: Optional session ID (generated if not provided)
            document_context: Optional document summaries to inject into prompt

        Yields:
            Event dictionaries (agent_started, tool_started, content, etc.)

        Returns:
            QueryResult with response, sources, and metadata
        """
        # Generate session ID if needed
        if not session_id:
            session_id = generate_session_id()

        try:
            # Determine available tools
            available_tools = self._resolve_tools()

            # Configure agent
            config = AgentConfig(
                max_iterations=max_iterations,
                tools=available_tools,
                document_context=document_context,
            )

            # Build context (include session_id for runner)
            context = {
                "channel_id": channel_id,
                "conversation_history": conversation_history or [],
                "session_id": session_id,
            }
            if thread_id:
                context["thread_id"] = thread_id

            # Run agent with streaming - yield all events
            agent_result = None
            stream_generator = self.agent_runner.run_stream(
                query=query,
                config=config,
                context=context,
            )

            # Iterate through all events and yield them
            try:
                while True:
                    event = next(stream_generator)
                    yield event
            except StopIteration as e:
                # Generator returned the final AgentResult
                agent_result = e.value

            # Handle case where no result was returned
            if agent_result is None:
                agent_result = type(
                    "AgentResult",
                    (),
                    {
                        "response": "No response generated.",
                        "sources": [],
                        "tool_calls": [],
                        "iterations": 0,
                        "metadata": {},
                    },
                )()

            # Build result
            result = QueryResult(
                response=agent_result.response,
                sources=agent_result.sources,
                session_id=session_id,
                iterations=agent_result.iterations,
                tools_used=[tc.get("name", "") for tc in agent_result.tool_calls],
                metadata=agent_result.metadata,
            )

            return result

        except Exception as e:
            # Emit error event
            if self.event_sink:
                self.event_sink.emit(AgentErrorEvent(
                    session_id=session_id,
                    error=str(e),
                    error_type=type(e).__name__,
                ))

            # Yield error event for streaming clients
            yield {"event": "error", "error": str(e)}

            return QueryResult(
                response=f"Error processing query: {str(e)}",
                session_id=session_id,
                error=str(e),
            )
