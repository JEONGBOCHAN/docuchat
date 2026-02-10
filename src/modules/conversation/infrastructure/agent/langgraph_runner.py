# -*- coding: utf-8 -*-
"""
LangGraph Agent Runner.

Implements AgentRunnerPort using LangGraph's create_react_agent.
This adapter wraps LangGraph to provide a clean interface for the application layer.

This is the key infrastructure component that prevents LangGraph framework
details from leaking into the application layer.
"""

import logging
import warnings
from datetime import datetime
from typing import Any, Generator

# langgraph 1.0 deprecated this path in favor of langchain.agents.create_agent,
# but langchain package is not installed. Suppress until migration to LangGraph 2.0.
warnings.filterwarnings(
    "ignore",
    message="create_react_agent has been moved",
)
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
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
    create_semantic_scholar_search_tool,
    create_crossref_search_tool,
    create_google_scholar_search_tool,
)
from src.core.config import get_settings, GeminiModels
from src.application.ports.document_search import DocumentSearchPort
from src.application.ports.web_search import WebSearchPort
from src.application.ports.token_counter import TokenCounterPort
from src.agents.middlewares.dashboard import DashboardMiddleware


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
        token_counter: TokenCounterPort | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ):
        """Initialize the LangGraph runner.

        Args:
            event_sink: Optional event sink for observability.
            document_search: Optional DocumentSearchPort instance.
            model: The Gemini model to use.
            dashboard_middleware: Optional DashboardMiddleware for LLM node display.
            token_counter: Optional TokenCounterPort for real-time token counting.
            checkpointer: Optional checkpoint saver for conversation persistence.
        """
        self._event_sink = event_sink
        if document_search is None:
            # Lazy import to avoid circular dependency
            from src.modules.conversation.infrastructure.di import create_document_search
            document_search = create_document_search()
        self._document_search = document_search
        self._model = model
        self._settings = get_settings()
        self._dashboard_middleware = dashboard_middleware
        self._token_counter = token_counter
        self._checkpointer = checkpointer
        self._checkpoint_miss_count = 0
        self._checkpoint_hit_count = 0

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

        # Determine which tools to register based on config.tools
        # If config.tools is empty, register all tools (backward compatibility)
        # If config.tools is non-empty, only register listed tools
        enabled_tools = set(config.tools) if config.tools else None

        tools = []

        # search_documents is always available if enabled or no filter
        if enabled_tools is None or "search_documents" in enabled_tools:
            search_tool = create_search_documents_tool(
                channel_id=channel_id,
                document_search=self._document_search,
            )
            tools.append(search_tool)

        # External search tools: only create if enabled
        if enabled_tools is None or "web_search" in enabled_tools:
            from src.modules.conversation.infrastructure.di import create_web_search
            web_search_adapter = create_web_search()
            tools.append(create_web_search_tool(web_search_port=web_search_adapter))

        if enabled_tools is None or "arxiv_search" in enabled_tools:
            from src.modules.conversation.infrastructure.di import create_arxiv_search
            arxiv_search_adapter = create_arxiv_search()
            tools.append(create_arxiv_search_tool(arxiv_search_port=arxiv_search_adapter))

        if enabled_tools is None or "semantic_scholar_search" in enabled_tools:
            from src.modules.conversation.infrastructure.di import create_semantic_scholar_search
            semantic_scholar_adapter = create_semantic_scholar_search()
            tools.append(create_semantic_scholar_search_tool(
                semantic_scholar_port=semantic_scholar_adapter
            ))

        if enabled_tools is None or "crossref_search" in enabled_tools:
            from src.modules.conversation.infrastructure.di import create_crossref_search
            crossref_adapter = create_crossref_search()
            tools.append(create_crossref_search_tool(crossref_port=crossref_adapter))

        if enabled_tools is None or "google_scholar_search" in enabled_tools:
            from src.modules.conversation.infrastructure.di import create_google_scholar_search
            google_scholar_adapter = create_google_scholar_search()
            tools.append(create_google_scholar_search_tool(
                google_scholar_port=google_scholar_adapter
            ))

        # Use custom system prompt if provided, otherwise build from available tools
        system_prompt = config.system_prompt or self._build_system_prompt(tools)

        # Append document context if provided
        if config.document_context:
            system_prompt += f"""

## Channel Document Context
{config.document_context}

When the user asks about topics related to these documents, prioritize using search_documents tool.
If the question is clearly about external/current events not covered in these documents, use web_search.
"""

        # Create the agent with prompt parameter
        # Suppress LangGraph 1.0 deprecation at call site (pytest resets module-level filters)
        agent_kwargs = dict(model=llm, tools=tools, prompt=system_prompt)
        if self._checkpointer is not None:
            agent_kwargs["checkpointer"] = self._checkpointer

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="create_react_agent has been moved")
            agent = create_react_agent(**agent_kwargs)

        return agent

    @staticmethod
    def _build_system_prompt(tools: list) -> str:
        """Build a system prompt that only describes the actually registered tools.

        Args:
            tools: List of LangChain tool objects that are registered.

        Returns:
            System prompt string matching the available tools.
        """
        tool_names = {getattr(t, "name", "") for t in tools}

        # Build tool descriptions section dynamically
        tool_sections = []
        tool_number = 1

        if "search_documents" in tool_names:
            tool_sections.append(
                f"{tool_number}. **search_documents**: Search for relevant information in the uploaded documents\n"
                f"   - Use for questions about uploaded files, papers, or documents\n"
                f"   - Returns excerpts with source citations"
            )
            tool_number += 1

        if "web_search" in tool_names:
            tool_sections.append(
                f"{tool_number}. **web_search**: Search the internet for current information\n"
                f"   - Use for current events, news, real-world facts\n"
                f"   - Use for restaurants, places, weather, locations\n"
                f"   - Use for anything requiring up-to-date web data"
            )
            tool_number += 1

        if "arxiv_search" in tool_names:
            tool_sections.append(
                f"{tool_number}. **arxiv_search**: Search arXiv for academic papers and research\n"
                f"   - Use for academic papers, research, scientific studies\n"
                f"   - Use for latest research on specific topics\n"
                f"   - Returns paper titles, authors, summaries, and PDF links"
            )
            tool_number += 1

        if "semantic_scholar_search" in tool_names:
            tool_sections.append(
                f"{tool_number}. **semantic_scholar_search**: Search Semantic Scholar for citation analysis\n"
                f"   - Use for citation counts, h-index, and paper impact\n"
                f"   - Use for highly cited papers on a topic\n"
                f"   - Returns citation metrics and academic influence data"
            )
            tool_number += 1

        if "crossref_search" in tool_names:
            tool_sections.append(
                f"{tool_number}. **crossref_search**: Search Crossref for publication metadata\n"
                f"   - Use for DOI lookup and verification\n"
                f"   - Use for publication metadata (publisher, journal, volume, issue)\n"
                f"   - Returns official publication records"
            )
            tool_number += 1

        if "google_scholar_search" in tool_names:
            tool_sections.append(
                f"{tool_number}. **google_scholar_search**: Search Google Scholar for academic papers\n"
                f"   - Use for broad academic literature search across all disciplines\n"
                f"   - Use for citation counts and highly cited papers\n"
                f"   - Returns paper titles, authors, citations, and links"
            )
            tool_number += 1

        # Build routing instructions based on available tools
        instructions = []
        instructions.append("1. Analyze the user's question to determine which tool is most appropriate")
        inst_num = 2
        if "search_documents" in tool_names:
            instructions.append(f"{inst_num}. For document-related questions -> use search_documents")
            inst_num += 1
        if "web_search" in tool_names:
            instructions.append(f"{inst_num}. For real-world/current information -> use web_search")
            inst_num += 1
        if "arxiv_search" in tool_names:
            instructions.append(f"{inst_num}. For academic research/papers -> use arxiv_search")
            inst_num += 1
        if "semantic_scholar_search" in tool_names:
            instructions.append(f"{inst_num}. For citation analysis/paper impact -> use semantic_scholar_search")
            inst_num += 1
        if "crossref_search" in tool_names:
            instructions.append(f"{inst_num}. For DOI lookup/publication metadata -> use crossref_search")
            inst_num += 1
        if "google_scholar_search" in tool_names:
            instructions.append(f"{inst_num}. For broad academic literature/citation search -> use google_scholar_search")
            inst_num += 1
        instructions.append(f"{inst_num}. You can use multiple tools if needed")
        inst_num += 1
        instructions.append(f"{inst_num}. Once you have enough information, respond directly to the user with a complete answer")
        inst_num += 1
        instructions.append(f"{inst_num}. Always cite your sources in the answer")

        # Build citation examples based on available tools
        cite_parts = []
        if "search_documents" in tool_names:
            cite_parts.append("[Source 1] for documents")
        if "web_search" in tool_names:
            cite_parts.append("[Web 1] for web")
        if "arxiv_search" in tool_names:
            cite_parts.append("[Paper 1] for arXiv")
        if "semantic_scholar_search" in tool_names:
            cite_parts.append("[Scholar 1] for Semantic Scholar")
        if "crossref_search" in tool_names:
            cite_parts.append("[Crossref 1] for Crossref")
        if "google_scholar_search" in tool_names:
            cite_parts.append("[GScholar 1] for Google Scholar")
        cite_example = ", ".join(cite_parts) if cite_parts else ""

        return f"""You are an intelligent assistant with access to multiple tools. Choose the appropriate tool based on the user's question.

## Available Tools
{chr(10).join(tool_sections)}

## Instructions
{chr(10).join(instructions)}

## Important Rules
- Choose the right tool based on the question type
- After gathering information, respond directly - do NOT call unnecessary tools
- Include citations in your answer (e.g., {cite_example})
- If no relevant information is found, inform the user honestly
- Do not make up information - only use what you find from the tools
- Be efficient: gather what you need and provide your answer. Do not keep searching endlessly.
"""

    @staticmethod
    def _history_to_messages(
        history: list,
        query: str,
    ) -> list[tuple[str, str]]:
        """Convert conversation history to invoke-ready message tuples.

        Handles two formats:
        - Pre-assembled tuples from ConversationMemoryService (already includes query)
        - Legacy dicts with 'role'/'content' keys (query appended)
        """
        if not history:
            return [("user", query)]
        # Pre-assembled tuples from memory service (already includes query)
        if isinstance(history[0], tuple):
            return list(history)
        # Legacy dict format
        messages: list[tuple[str, str]] = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(("user", content))
            else:
                messages.append(("assistant", content))
        messages.append(("user", query))
        return messages

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
        conversation_history_raw = context.get("conversation_history", [])
        thread_id = context.get("thread_id")
        session_id = context.get("session_id") or generate_session_id()
        memory_mode = context.get("memory_mode")

        # Support lazy loading: callable defers DB query until actually needed
        if callable(conversation_history_raw):
            _load_history = conversation_history_raw
        else:
            _load_history = lambda: conversation_history_raw  # noqa: E731

        # Emit: Agent Started
        if self._event_sink:
            self._event_sink.emit(AgentStartedEvent(
                session_id=session_id,
                query=query,
                channel_id=channel_id,
            ))

        try:
            agent = self._create_agent(channel_id, config)

            # Build messages based on memory_mode
            if memory_mode == "hybrid_strict":
                # Always use assembled context (summary+recent+query), skip checkpoint
                conversation_history = _load_history()
                messages = self._history_to_messages(conversation_history, query)
            elif self._checkpointer and thread_id:
                checkpoint_config = {"configurable": {"thread_id": thread_id}}
                has_checkpoint = self._checkpointer.get_tuple(checkpoint_config) is not None
                if has_checkpoint:
                    # Checkpoint exists → only send new message (no DB query needed)
                    self._checkpoint_hit_count += 1
                    messages = [("user", query)]
                else:
                    # Checkpoint miss (e.g. server restart) → load history as fallback
                    self._checkpoint_miss_count += 1
                    logger.info(
                        "Checkpoint miss for thread_id=%s, using DB history fallback "
                        "(total misses=%d, hits=%d)",
                        thread_id, self._checkpoint_miss_count, self._checkpoint_hit_count,
                    )
                    conversation_history = _load_history()
                    messages = self._history_to_messages(conversation_history, query)
            else:
                conversation_history = _load_history()
                messages = self._history_to_messages(conversation_history, query)

            # Build invoke config
            invoke_config = {"recursion_limit": config.max_iterations * 2 + 1}
            if self._checkpointer and thread_id and memory_mode != "hybrid_strict":
                invoke_config["configurable"] = {"thread_id": thread_id}

            if memory_mode == "hybrid_strict":
                logger.debug("hybrid_strict: checkpoint_bypassed=true, thread_id not injected")

            # Run agent
            agent_start_time = datetime.now()
            result = agent.invoke(
                {"messages": messages},
                config=invoke_config,
            )
            agent_duration_ms = (datetime.now() - agent_start_time).total_seconds() * 1000

            # Analyze messages to emit proper LLM events for synchronous run
            # ReAct flow: llm_reasoning -> tool -> llm_observation -> tool -> ... -> llm_response
            if self._dashboard_middleware:
                result_messages = result.get("messages", [])
                llm_call_count = 0
                tool_call_count = 0

                # Count LLM phases first to distribute duration
                llm_phases = []
                for msg in result_messages:
                    msg_type = getattr(msg, "type", None) or type(msg).__name__.lower()
                    if "human" in str(msg_type).lower():
                        continue
                    if "ai" in str(msg_type).lower():
                        has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls
                        content = getattr(msg, "content", "")
                        if has_tool_calls:
                            llm_phases.append("tool_selection")
                        elif content:
                            llm_phases.append("response")

                # Distribute duration among LLM phases (equal distribution)
                num_phases = len(llm_phases) if llm_phases else 1
                duration_per_phase_ms = agent_duration_ms / num_phases

                for msg in result_messages:
                    # Get message type - support both real messages and mocks
                    msg_type = getattr(msg, "type", None) or type(msg).__name__.lower()

                    # Skip user/human messages
                    if "human" in str(msg_type).lower():
                        continue

                    # AIMessage with tool_calls - reasoning or observation phase
                    if "ai" in str(msg_type).lower() and hasattr(msg, "tool_calls") and msg.tool_calls:
                        if tool_call_count == 0:
                            # First tool selection - llm_reasoning
                            llm_role = "llm_reasoning"
                        else:
                            # After tool execution - llm_observation
                            llm_role = "llm_observation"

                        # Extract token usage from usage_metadata
                        usage = getattr(msg, "usage_metadata", None)
                        tokens = usage.get("total_tokens") if usage else None

                        self._dashboard_middleware.on_llm_start(llm_role, {"channel_id": channel_id})
                        # Use distributed duration for non-streaming mode
                        self._dashboard_middleware.on_llm_end(
                            llm_role,
                            {"channel_id": channel_id},
                            tokens=tokens,
                            duration_override_ms=duration_per_phase_ms
                        )
                        llm_call_count += 1
                        tool_call_count += len(msg.tool_calls)

                    # AIMessage with content (no tool_calls or empty) - final response
                    elif "ai" in str(msg_type).lower():
                        content = getattr(msg, "content", "")
                        has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls

                        if content and not has_tool_calls:
                            # Extract token usage from usage_metadata
                            usage = getattr(msg, "usage_metadata", None)
                            tokens = usage.get("total_tokens") if usage else None

                            # Final response with content
                            self._dashboard_middleware.on_llm_start("llm_response", {"channel_id": channel_id})
                            # Use distributed duration for non-streaming mode
                            self._dashboard_middleware.on_llm_end(
                                "llm_response",
                                {"channel_id": channel_id},
                                tokens=tokens,
                                duration_override_ms=duration_per_phase_ms
                            )

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

            # Count tokens from final response (for non-streaming dashboard update)
            total_tokens = 0
            if self._token_counter and response_text:
                total_tokens = self._token_counter.count_tokens(response_text)
                if self._dashboard_middleware:
                    self._dashboard_middleware.update_realtime_tokens(
                        total_tokens,
                        {"channel_id": channel_id},
                    )

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
        conversation_history_raw = context.get("conversation_history", [])
        thread_id = context.get("thread_id")
        session_id = context.get("session_id") or generate_session_id()
        memory_mode = context.get("memory_mode")

        # Support lazy loading: callable defers DB query until actually needed
        if callable(conversation_history_raw):
            _load_history = conversation_history_raw
        else:
            _load_history = lambda: conversation_history_raw  # noqa: E731

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

            # Build messages based on memory_mode
            if memory_mode == "hybrid_strict":
                # Always use assembled context (summary+recent+query), skip checkpoint
                conversation_history = _load_history()
                messages = self._history_to_messages(conversation_history, query)
            elif self._checkpointer and thread_id:
                checkpoint_config = {"configurable": {"thread_id": thread_id}}
                has_checkpoint = self._checkpointer.get_tuple(checkpoint_config) is not None
                if has_checkpoint:
                    # Checkpoint exists → no DB query needed
                    self._checkpoint_hit_count += 1
                    messages = [("user", query)]
                else:
                    self._checkpoint_miss_count += 1
                    logger.info(
                        "Checkpoint miss for thread_id=%s, using DB history fallback (stream) "
                        "(total misses=%d, hits=%d)",
                        thread_id, self._checkpoint_miss_count, self._checkpoint_hit_count,
                    )
                    conversation_history = _load_history()
                    messages = self._history_to_messages(conversation_history, query)
            else:
                conversation_history = _load_history()
                messages = self._history_to_messages(conversation_history, query)

            # Track tool calls dynamically
            tool_start_times: dict[str, datetime] = {}
            active_tools: set[str] = set()

            # Track LLM call state for dashboard middleware
            # - llm_reasoning: Initial reasoning when tool_calls present but no content
            # - llm_observation: After tool execution, observing results and deciding next action
            # - llm_response: Final response with content to user
            llm_reasoning_started = False
            llm_observation_started = False
            llm_response_started = False
            tool_just_completed = False  # Flag to detect observation phase
            last_tool_completed_time: datetime | None = None  # Track when last tool completed
            stream_start_time = datetime.now()  # Track stream start for reasoning duration

            # Track LLM phases for post-streaming token extraction
            # Maps message index to LLM role (for token extraction after streaming)
            llm_phase_message_indices: list[tuple[int, str]] = []
            current_ai_message_index = -1

            # Use stream mode "messages" for token-by-token streaming
            final_response = ""
            final_messages = []

            # Real-time token counting state
            accumulated_tokens = 0
            last_token_update_time = datetime.now()
            token_update_interval_ms = 100  # Throttle: update at most every 100ms

            # Build stream config
            stream_config = {"recursion_limit": config.max_iterations * 2 + 1}
            if self._checkpointer and thread_id and memory_mode != "hybrid_strict":
                stream_config["configurable"] = {"thread_id": thread_id}

            if memory_mode == "hybrid_strict":
                logger.debug("hybrid_strict stream: checkpoint_bypassed=true, thread_id not injected")

            for msg, metadata in agent.stream(
                {"messages": messages},
                config=stream_config,
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
                    # Track current AI message index for post-streaming token extraction
                    current_ai_message_index = len(final_messages) - 1

                    tool_calls = getattr(msg, "tool_calls", None)
                    if tool_calls:
                        # Determine LLM role based on context
                        if tool_just_completed:
                            # After tool execution, this is an observation/decision phase
                            llm_role = "llm_observation"
                            if not llm_observation_started and self._dashboard_middleware:
                                llm_observation_started = True
                                llm_phase_message_indices.append((current_ai_message_index, llm_role))
                                self._dashboard_middleware.on_llm_start(llm_role, {"channel_id": channel_id})
                        else:
                            # Initial reasoning phase (first tool selection)
                            llm_role = "llm_reasoning"
                            if not llm_reasoning_started and self._dashboard_middleware:
                                llm_reasoning_started = True
                                llm_phase_message_indices.append((current_ai_message_index, llm_role))
                                self._dashboard_middleware.on_llm_start(llm_role, {"channel_id": channel_id})

                        # End current LLM phase before tool execution starts
                        # This should happen once per phase, not per tool call
                        # Calculate duration from the appropriate start time
                        if llm_reasoning_started and not tool_just_completed and self._dashboard_middleware:
                            # For reasoning, measure from stream start to now
                            _now = datetime.now()
                            reasoning_duration_ms = (_now - stream_start_time).total_seconds() * 1000
                            self._dashboard_middleware.on_llm_end(
                                "llm_reasoning",
                                {"channel_id": channel_id},
                                tokens=None,
                                duration_override_ms=reasoning_duration_ms
                            )
                            llm_reasoning_started = False
                        elif llm_observation_started and self._dashboard_middleware:
                            # For observation, measure from last tool completion to now
                            if last_tool_completed_time:
                                observation_duration_ms = (datetime.now() - last_tool_completed_time).total_seconds() * 1000
                            else:
                                observation_duration_ms = None
                            self._dashboard_middleware.on_llm_end(
                                "llm_observation",
                                {"channel_id": channel_id},
                                tokens=None,
                                duration_override_ms=observation_duration_ms
                            )
                            llm_observation_started = False

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

                        # Mark that a tool just completed (for observation phase detection)
                        tool_just_completed = True
                        last_tool_completed_time = datetime.now()
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
                        llm_phase_message_indices.append((current_ai_message_index, "llm_response"))
                        self._dashboard_middleware.on_llm_start("llm_response", {"channel_id": channel_id})

                    final_response += content

                    # Real-time token counting during streaming
                    if self._token_counter and content:
                        accumulated_tokens = self._token_counter.count_tokens_incremental(
                            content, accumulated_tokens
                        )

                        # Throttle token updates to avoid excessive UI refreshes
                        now = datetime.now()
                        elapsed_ms = (now - last_token_update_time).total_seconds() * 1000
                        if elapsed_ms >= token_update_interval_ms:
                            last_token_update_time = now
                            if self._dashboard_middleware:
                                self._dashboard_middleware.update_realtime_tokens(
                                    accumulated_tokens,
                                    {"channel_id": channel_id},
                                )

                    yield {
                        "event": "content",
                        "content": content,
                        "tokens": accumulated_tokens if self._token_counter else None,
                    }

            # Final token update (ensure the last count is published)
            if self._token_counter and accumulated_tokens > 0 and self._dashboard_middleware:
                self._dashboard_middleware.update_realtime_tokens(
                    accumulated_tokens,
                    {"channel_id": channel_id},
                )

            # Finalize any remaining LLM phases (tokens extracted post-streaming)
            # LLM response completed - emit llm_end event via middleware
            if llm_response_started and self._dashboard_middleware:
                self._dashboard_middleware.on_llm_end("llm_response", {"channel_id": channel_id}, tokens=None)

            # Clean up any incomplete LLM phases (edge cases)
            # These should rarely happen, but if they do, we measure from their start time
            if llm_reasoning_started and self._dashboard_middleware:
                self._dashboard_middleware.on_llm_end("llm_reasoning", {"channel_id": channel_id}, tokens=None)
            if llm_observation_started and self._dashboard_middleware:
                self._dashboard_middleware.on_llm_end("llm_observation", {"channel_id": channel_id}, tokens=None)

            # Post-streaming token extraction: extract tokens from final_messages
            # In streaming mode, usage_metadata is not available on chunks.
            # After streaming completes, we scan final_messages for AIMessage objects
            # that contain usage_metadata and update the corresponding LLM steps.
            if self._dashboard_middleware and llm_phase_message_indices:
                self._extract_and_update_streaming_tokens(
                    final_messages, llm_phase_message_indices, channel_id
                )

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

    def _extract_and_update_streaming_tokens(
        self,
        final_messages: list,
        llm_phase_message_indices: list[tuple[int, str]],
        channel_id: str,
    ) -> None:
        """Extract token usage from final messages and update dashboard steps.

        In streaming mode, usage_metadata is not available on AIMessageChunks.
        After streaming completes, we analyze the collected messages to extract
        token information and retroactively update the corresponding LLM steps.

        If usage_metadata is not available, we use the token counter to estimate
        tokens based on message content.

        Args:
            final_messages: List of all messages from streaming.
            llm_phase_message_indices: List of (message_index, llm_role) tuples.
            channel_id: The channel ID for logging.
        """
        if not self._dashboard_middleware:
            return

        logger.debug(
            f"[TokenExtract] Starting extraction - "
            f"messages={len(final_messages)}, "
            f"phases={llm_phase_message_indices}, "
            f"has_token_counter={self._token_counter is not None}"
        )

        # Build a map of AI messages with their tokens (from usage_metadata or estimated)
        ai_messages_with_tokens: list[tuple[int, int]] = []
        for idx, msg in enumerate(final_messages):
            msg_type = getattr(msg, "type", None) or type(msg).__name__.lower()
            if "ai" in str(msg_type).lower():
                # Try usage_metadata first
                usage = getattr(msg, "usage_metadata", None)
                if usage and isinstance(usage, dict):
                    tokens = usage.get("total_tokens")
                    if isinstance(tokens, int) and tokens > 0:
                        ai_messages_with_tokens.append((idx, tokens))
                        logger.debug(f"[TokenExtract] Msg {idx}: usage_metadata tokens={tokens}")
                        continue

                # Fallback: estimate tokens from content using token counter
                if self._token_counter:
                    content = getattr(msg, "content", "")
                    if isinstance(content, list):
                        content = "".join(
                            part.get("text", "") if isinstance(part, dict) else str(part)
                            for part in content
                        )
                    if content and isinstance(content, str):
                        estimated_tokens = self._token_counter.count_tokens(content)
                        if isinstance(estimated_tokens, int) and estimated_tokens > 0:
                            ai_messages_with_tokens.append((idx, estimated_tokens))
                            logger.debug(f"[TokenExtract] Msg {idx}: estimated tokens={estimated_tokens} from {len(content)} chars")
                    else:
                        logger.debug(f"[TokenExtract] Msg {idx}: empty content, skipping")
                else:
                    logger.debug(f"[TokenExtract] Msg {idx}: no token_counter, skipping")

        logger.debug(f"[TokenExtract] AI messages with tokens: {ai_messages_with_tokens}")

        # Match token data to LLM phases
        # Strategy: For each LLM phase, sum ALL tokens from phase start to next phase (or end)
        # This handles streaming mode where each chunk has small partial content
        sorted_phases = sorted(llm_phase_message_indices, key=lambda x: x[0])

        for i, (phase_idx, llm_role) in enumerate(sorted_phases):
            # Determine the end index for this phase
            if i + 1 < len(sorted_phases):
                next_phase_idx = sorted_phases[i + 1][0]
            else:
                next_phase_idx = len(final_messages)

            # Sum all tokens from chunks in this phase's range
            phase_tokens = sum(
                tokens
                for msg_idx, tokens in ai_messages_with_tokens
                if phase_idx <= msg_idx < next_phase_idx
            )

            logger.debug(
                f"[TokenExtract] Phase '{llm_role}': idx={phase_idx}-{next_phase_idx}, "
                f"tokens={phase_tokens}"
            )

            if phase_tokens > 0:
                self._dashboard_middleware.update_step_tokens(llm_role, phase_tokens, channel_id)
                logger.debug(f"[TokenExtract] Updated step tokens for {llm_role}: {phase_tokens}")

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

            # Extract sources from search results (document, web, arxiv)
            if hasattr(msg, "content") and isinstance(msg.content, str):
                content = msg.content

                # Extract document sources: [Source X: filename]
                if "[Source" in content and "Found" in content:
                    lines = content.split("\n")
                    for line in lines:
                        if line.startswith("[Source"):
                            try:
                                source_part = line.split(":")[1].strip().rstrip("]")
                                if source_part and source_part not in [s.get("source") for s in sources]:
                                    sources.append({
                                        "source": source_part,
                                        "content": "",
                                        "source_type": "document",
                                        "url": None,
                                    })
                            except (IndexError, AttributeError):
                                pass

                # Extract web sources: [Web X] title\nURL: url\nsnippet
                if "[Web" in content and "Found" in content:
                    self._extract_web_sources(content, sources)

                # Extract arxiv sources: [Paper X] title\n...PDF: url
                if "[Paper" in content and "Found" in content:
                    self._extract_arxiv_sources(content, sources)

        return sources, iterations, tool_calls

    def _extract_web_sources(self, content: str, sources: list[dict]) -> None:
        """Extract web search sources from tool output.

        Parses format:
        [Web 1] Title
        URL: https://example.com
        Snippet text...

        Args:
            content: Tool output content.
            sources: List to append extracted sources to.
        """
        import re

        # Split by --- separator to get individual results
        sections = content.split("\n---\n")

        for section in sections:
            # Match [Web N] pattern
            web_match = re.search(r"\[Web \d+\]\s*(.+)", section)
            if not web_match:
                continue

            title = web_match.group(1).strip()

            # Extract URL
            url_match = re.search(r"URL:\s*(\S+)", section)
            url = url_match.group(1).strip() if url_match else None

            # Extract snippet (everything after URL line)
            snippet = ""
            lines = section.split("\n")
            capture_snippet = False
            for line in lines:
                if capture_snippet and line.strip():
                    snippet = line.strip()
                    break
                if line.startswith("URL:"):
                    capture_snippet = True

            # Avoid duplicates
            if title and title not in [s.get("source") for s in sources]:
                sources.append({
                    "source": title,
                    "content": snippet,
                    "source_type": "web",
                    "url": url,
                })

    def _extract_arxiv_sources(self, content: str, sources: list[dict]) -> None:
        """Extract arxiv paper sources from tool output.

        Parses format:
        [Paper 1] Title
        Authors: ...
        arXiv ID: ...
        Category: ...
        Published: ...
        PDF: https://arxiv.org/pdf/...
        Summary: ...

        Args:
            content: Tool output content.
            sources: List to append extracted sources to.
        """
        import re

        # Split by --- separator to get individual results
        sections = content.split("\n---\n")

        for section in sections:
            # Match [Paper N] pattern
            paper_match = re.search(r"\[Paper \d+\]\s*(.+)", section)
            if not paper_match:
                continue

            title = paper_match.group(1).strip()

            # Extract PDF URL
            pdf_match = re.search(r"PDF:\s*(\S+)", section)
            pdf_url = pdf_match.group(1).strip() if pdf_match else None

            # Extract summary for content
            summary_match = re.search(r"Summary:\s*(.+)", section, re.DOTALL)
            summary = summary_match.group(1).strip()[:200] if summary_match else ""

            # Avoid duplicates
            if title and title not in [s.get("source") for s in sources]:
                sources.append({
                    "source": title,
                    "content": summary,
                    "source_type": "arxiv",
                    "url": pdf_url,
                })

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
            AgentTool(
                name="semantic_scholar_search",
                description="Search Semantic Scholar for citation counts, h-index, and paper impact analysis",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "The search query for citation analysis",
                    }
                },
            ),
            AgentTool(
                name="crossref_search",
                description="Search Crossref for DOI lookup and publication metadata",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "The DOI or search query for publication metadata",
                    }
                },
            ),
            AgentTool(
                name="google_scholar_search",
                description="Search Google Scholar for academic papers across all disciplines",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "The search query for academic papers",
                    }
                },
            ),
        ]
