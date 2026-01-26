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
from typing import Any, Generator

from src.application.ports import (
    AgentRunnerPort,
    AgentConfig,
    AgentEventSinkPort,
    DocumentSearchPort,
    WebSearchPort,
)
from src.application.dto.agent_event import (
    AgentStartedEvent,
    AgentCompletedEvent,
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
    ):
        """Initialize the use case with dependencies.

        Args:
            agent_runner: The agent execution engine
            event_sink: Optional event sink for observability
            document_search: Optional document search adapter
            web_search: Optional web search adapter
        """
        self.agent_runner = agent_runner
        self.event_sink = event_sink
        self.document_search = document_search
        self.web_search = web_search

    def _build_enhanced_system_prompt(self, document_context: str | None) -> str | None:
        """Build enhanced system prompt with document context.

        Args:
            document_context: Optional document summaries string

        Returns:
            Enhanced system prompt or None if no context
        """
        if not document_context:
            return None

        # Import here to avoid circular dependency
        from src.infrastructure.agent.langgraph_runner import RAG_SYSTEM_PROMPT

        # Inject document context into the system prompt
        enhanced_prompt = f"""{RAG_SYSTEM_PROMPT}

## Channel Document Context
{document_context}

When the user asks about topics related to these documents, prioritize using search_documents tool.
If the question is clearly about external/current events not covered in these documents, use web_search.
"""
        return enhanced_prompt

    def execute(
        self,
        query: str,
        channel_id: str,
        conversation_history: list[dict[str, str]] | None = None,
        max_iterations: int = 15,
        session_id: str | None = None,
        document_context: str | None = None,
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
            conversation_history: Previous conversation for context
            max_iterations: Maximum agent iterations
            session_id: Optional session ID (generated if not provided)
            document_context: Optional document summaries to inject into prompt

        Returns:
            QueryResult with response, sources, and metadata
        """
        # Generate session ID if needed
        if not session_id:
            session_id = generate_session_id()

        # Emit start event
        if self.event_sink:
            self.event_sink.emit(AgentStartedEvent(
                session_id=session_id,
                query=query,
                channel_id=channel_id,
            ))

        try:
            # Determine available tools
            available_tools = []
            if self.document_search:
                available_tools.append("search_documents")
            if self.web_search:
                available_tools.append("web_search")

            # Build enhanced system prompt with document context
            system_prompt = self._build_enhanced_system_prompt(document_context)

            # Configure agent
            config = AgentConfig(
                max_iterations=max_iterations,
                tools=available_tools,
                system_prompt=system_prompt,
            )

            # Build context
            context = {
                "channel_id": channel_id,
                "conversation_history": conversation_history or [],
            }

            # Run agent
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
                tools_used=[tc.get("tool", "") for tc in agent_result.tool_calls],
                metadata=agent_result.metadata,
            )

            # Emit completion event
            if self.event_sink:
                self.event_sink.emit(AgentCompletedEvent(
                    session_id=session_id,
                    response=result.response,
                    sources=result.sources,
                    iterations=result.iterations,
                ))

            return result

        except Exception as e:
            # Emit error event
            if self.event_sink:
                self.event_sink.emit(AgentErrorEvent(
                    session_id=session_id,
                    error=str(e),
                    error_type=type(e).__name__,
                ))

            return QueryResult(
                response=f"Error processing query: {str(e)}",
                session_id=session_id,
                error=str(e),
            )

    def execute_stream(
        self,
        query: str,
        channel_id: str,
        conversation_history: list[dict[str, str]] | None = None,
        max_iterations: int = 15,
        session_id: str | None = None,
        document_context: str | None = None,
    ) -> Generator[dict, None, QueryResult]:
        """Execute query processing with streaming events.

        This method streams events as the agent processes the query,
        allowing real-time updates to be sent to clients via SSE.

        Args:
            query: The user's question
            channel_id: The channel context for document search
            conversation_history: Previous conversation for context
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
            available_tools = []
            if self.document_search:
                available_tools.append("search_documents")
            if self.web_search:
                available_tools.append("web_search")

            # Build enhanced system prompt with document context
            system_prompt = self._build_enhanced_system_prompt(document_context)

            # Configure agent
            config = AgentConfig(
                max_iterations=max_iterations,
                tools=available_tools,
                system_prompt=system_prompt,
            )

            # Build context (include session_id for runner)
            context = {
                "channel_id": channel_id,
                "conversation_history": conversation_history or [],
                "session_id": session_id,
            }

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
                tools_used=[tc.get("tool", "") for tc in agent_result.tool_calls],
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
