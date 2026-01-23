# -*- coding: utf-8 -*-
"""
RAG Agent using LangGraph create_react_agent pattern.

Implements a document-grounded Q&A agent with middleware support.
"""

from dataclasses import dataclass, field
from typing import Any

from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.tools.search_tools import (
    create_search_documents_tool,
    create_finish_tool,
)
from src.core.config import get_settings
from src.services.gemini import GeminiService


# ============================================================
# System Prompt
# ============================================================

RAG_AGENT_SYSTEM_PROMPT = """You are a document analysis assistant. Your task is to answer user questions based on uploaded documents.

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


# ============================================================
# Configuration
# ============================================================

@dataclass
class RAGAgentConfig:
    """Configuration for the RAG agent.

    Attributes:
        channel_id: The channel (FileSearchStore) ID to search in.
        max_iterations: Maximum number of tool calling iterations.
        model: The Gemini model to use for the agent.
        temperature: Temperature for model generation.
        system_prompt: Custom system prompt (uses default if None).
        middleware: List of middleware instances to apply.
    """
    channel_id: str
    max_iterations: int = 3
    model: str = "gemini-2.5-flash-preview-05-20"
    temperature: float = 0.0
    system_prompt: str | None = None
    middleware: list[Any] = field(default_factory=list)


# ============================================================
# Agent Factory
# ============================================================

def create_rag_agent(config: RAGAgentConfig) -> Any:
    """Create a RAG agent using LangGraph's create_react_agent.

    Args:
        config: RAGAgentConfig with channel_id and other settings.

    Returns:
        A compiled LangGraph agent.
    """
    settings = get_settings()
    gemini_service = GeminiService()

    # Create the LLM
    llm = ChatGoogleGenerativeAI(
        model=config.model,
        google_api_key=settings.google_api_key,
        temperature=config.temperature,
    )

    # Create tools bound to the specific channel
    search_tool = create_search_documents_tool(
        channel_id=config.channel_id,
        gemini_service=gemini_service,
    )
    finish_tool = create_finish_tool()

    # Use custom system prompt if provided, otherwise use default
    system_prompt = config.system_prompt or RAG_AGENT_SYSTEM_PROMPT

    # Create the agent using LangGraph's create_react_agent
    # Note: middleware is handled separately in run_rag_agent
    agent = create_react_agent(
        model=llm,
        tools=[search_tool, finish_tool],
        state_modifier=system_prompt,
    )

    return agent


# ============================================================
# Agent Runner
# ============================================================

def run_rag_agent(
    channel_id: str,
    query: str,
    conversation_history: list[dict] | None = None,
    max_iterations: int = 3,
    middleware: list[Any] | None = None,
) -> dict[str, Any]:
    """Run the RAG agent to answer a query.

    This function provides backward compatibility with the LangGraph-based
    implementation while using the new LangGraph create_react_agent pattern.

    Args:
        channel_id: The channel ID to search in.
        query: User's question.
        conversation_history: Previous messages for context.
        max_iterations: Maximum iterations (default 3).
        middleware: Optional list of middleware instances.

    Returns:
        Dict with 'response', 'sources', 'iterations', and optional 'error'.
    """
    from datetime import datetime

    config = RAGAgentConfig(
        channel_id=channel_id,
        max_iterations=max_iterations,
        middleware=middleware or [],
    )

    # Notify middleware of agent start
    for mw in config.middleware:
        if hasattr(mw, 'on_agent_start'):
            mw.on_agent_start({"query": query, "channel_id": channel_id})

    try:
        agent = create_rag_agent(config)

        # Build messages from conversation history
        messages = []
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(("user", content))
                else:
                    messages.append(("assistant", content))

        # Add the current query
        messages.append(("user", query))

        # Notify middleware of retrieve step
        for mw in config.middleware:
            if hasattr(mw, 'on_tool_start'):
                mw.on_tool_start("retrieve", {"query": query})

        # Run the agent with recursion limit
        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": max_iterations * 2 + 1}
        )

        # Notify middleware of retrieve complete
        for mw in config.middleware:
            if hasattr(mw, 'on_tool_end'):
                mw.on_tool_end("retrieve", {})

        # Extract the final response
        final_message = result.get("messages", [])[-1] if result.get("messages") else None

        if final_message:
            response_text = getattr(final_message, "content", str(final_message))
        else:
            response_text = "No response generated."

        # Extract sources from tool messages if available
        sources = []
        iterations = 0
        for msg in result.get("messages", []):
            # Count tool calls as iterations
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                iterations += 1
            # Extract sources from search results
            if hasattr(msg, "content") and isinstance(msg.content, str):
                if "[Source" in msg.content and "Found" in msg.content:
                    # Parse sources from search results
                    lines = msg.content.split("\n")
                    for line in lines:
                        if line.startswith("[Source"):
                            try:
                                source_part = line.split(":")[1].strip().rstrip("]")
                                if source_part and source_part not in [s.get("source") for s in sources]:
                                    sources.append({"source": source_part, "content": ""})
                            except (IndexError, AttributeError):
                                pass

        # Notify middleware of agent complete
        for mw in config.middleware:
            if hasattr(mw, 'on_agent_end'):
                mw.on_agent_end({
                    "response": response_text,
                    "sources": sources,
                    "iterations": iterations,
                })

        return {
            "response": response_text,
            "sources": sources,
            "iterations": iterations,
            "error": None,
        }

    except Exception as e:
        # Notify middleware of error
        for mw in config.middleware:
            if hasattr(mw, 'on_agent_error'):
                mw.on_agent_error(str(e))

        return {
            "response": f"Error: {str(e)}",
            "sources": [],
            "iterations": 0,
            "error": str(e),
        }
