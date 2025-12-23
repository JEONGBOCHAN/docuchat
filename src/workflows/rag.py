# -*- coding: utf-8 -*-
"""
RAG Agent workflow using LangGraph.

Implements the ReAct (Reasoning + Acting) pattern:
1. Think: LLM decides what to do next
2. Act: Execute the chosen tool
3. Observe: Record the result and update state
4. Repeat until finish or max iterations
"""

from typing import TypedDict, Literal, Any
from langgraph.graph import StateGraph, END

from src.services.gemini import GeminiService


# ============================================================
# State Definition
# ============================================================

class AgentState(TypedDict):
    """State for the RAG agent workflow.

    Attributes:
        channel_id: The channel (FileSearchStore) ID to search in
        query: User's question
        conversation_history: Previous messages for context
        iteration: Current iteration count
        max_iterations: Maximum allowed iterations
        tool_results: Accumulated results from tool executions
        sources: Sources found during search
        final_answer: The final answer to return
        error: Error message if any step fails
    """
    channel_id: str
    query: str
    conversation_history: list[dict]
    iteration: int
    max_iterations: int
    tool_results: list[dict]
    sources: list[dict]
    final_answer: str | None
    error: str | None


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
# Tool Definitions for Gemini Function Calling
# ============================================================

AGENT_TOOLS = [
    {
        "name": "search_documents",
        "description": "Search for information in the uploaded documents. Use this to find relevant content that can help answer the user's question.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant information in documents."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "finish",
        "description": "Call this when you have gathered enough information and are ready to provide the final answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The complete final answer to the user's question with citations."
                }
            },
            "required": ["answer"]
        }
    }
]


# ============================================================
# Node Functions
# ============================================================

def think(state: AgentState) -> AgentState:
    """Think node: LLM decides what to do next.

    Calls Gemini with tools to decide:
    - search_documents: Need more information
    - finish: Ready to provide answer
    """
    if state.get("error"):
        return state

    gemini = GeminiService()

    # Build prompt with context
    prompt_parts = [
        RAG_AGENT_SYSTEM_PROMPT,
        f"\n\nUser Question: {state['query']}"
    ]

    # Add previous tool results if any
    if state["tool_results"]:
        prompt_parts.append("\n\n## Previous Search Results:")
        for i, result in enumerate(state["tool_results"], 1):
            prompt_parts.append(f"\n### Search {i}: \"{result['query']}\"")
            prompt_parts.append(result["result"][:4000])  # Truncate long results

    prompt_parts.append("\n\nBased on the above, decide your next action.")
    prompt = "\n".join(prompt_parts)

    # Call Gemini with function calling
    response = gemini.call_with_tools(prompt=prompt, tools=AGENT_TOOLS)

    if "error" in response and response["error"]:
        return {**state, "error": response["error"]}

    # Store the LLM response in state for act node
    return {
        **state,
        "_llm_response": response,
        "iteration": state["iteration"] + 1,
    }


def act(state: AgentState) -> AgentState:
    """Act node: Execute the tool chosen by LLM.

    Executes either:
    - search_documents: Search and store results
    - finish: Set final answer
    """
    if state.get("error"):
        return state

    response = state.get("_llm_response", {})
    tool_call = response.get("tool_call")

    # If no tool call, LLM gave a direct text response
    if not tool_call:
        text_response = response.get("text", "")
        if text_response:
            return {**state, "final_answer": text_response}
        return {**state, "error": "LLM did not provide a response"}

    tool_name = tool_call.get("name")
    tool_args = tool_call.get("args", {})

    # Handle finish tool
    if tool_name == "finish":
        answer = tool_args.get("answer", "Task completed.")
        return {**state, "final_answer": answer}

    # Handle search_documents tool
    if tool_name == "search_documents":
        search_query = tool_args.get("query", state["query"])
        gemini = GeminiService()

        # Perform search
        search_result = gemini.search_documents(
            store_name=state["channel_id"],
            query=search_query,
        )

        # Format results
        sources = search_result.get("sources", [])
        if sources:
            formatted_parts = []
            for i, source in enumerate(sources, 1):
                source_name = source.get("source", "unknown")
                content = source.get("content", "")
                formatted_parts.append(f"[Source {i}: {source_name}]\n{content}")

                # Track sources
                if not any(s.get("source") == source_name for s in state["sources"]):
                    state["sources"].append(source)

            result_text = f"Found {len(sources)} relevant sections:\n\n" + "\n\n---\n\n".join(formatted_parts)
        else:
            result_text = "No relevant documents found for this query."

        # Store result
        new_tool_results = state["tool_results"] + [{
            "query": search_query,
            "result": result_text,
        }]

        return {**state, "tool_results": new_tool_results, "sources": state["sources"]}

    # Unknown tool
    return {**state, "error": f"Unknown tool: {tool_name}"}


def observe(state: AgentState) -> AgentState:
    """Observe node: Clean up state after action.

    Prepares state for next iteration or completion.
    """
    # Remove temporary LLM response from state
    new_state = {k: v for k, v in state.items() if not k.startswith("_")}
    return new_state


# ============================================================
# Routing Functions
# ============================================================

def should_continue(state: AgentState) -> Literal["think", "end"]:
    """Determine if the agent should continue or stop.

    Stops when:
    - final_answer is set (task complete)
    - error occurred
    - max_iterations reached
    """
    # Stop if error
    if state.get("error"):
        return "end"

    # Stop if final answer
    if state.get("final_answer"):
        return "end"

    # Stop if max iterations reached
    if state["iteration"] >= state["max_iterations"]:
        return "end"

    # Continue to next iteration
    return "think"


# ============================================================
# Workflow Creation
# ============================================================

def create_rag_agent() -> StateGraph:
    """Create the RAG agent workflow graph.

    Workflow:
        think → act → observe → (continue?) → think ... → END

    Returns:
        Compiled LangGraph workflow
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("think", think)
    workflow.add_node("act", act)
    workflow.add_node("observe", observe)

    # Set entry point
    workflow.set_entry_point("think")

    # Add edges
    workflow.add_edge("think", "act")
    workflow.add_edge("act", "observe")

    # Conditional edge: continue loop or end
    workflow.add_conditional_edges(
        "observe",
        should_continue,
        {
            "think": "think",  # Loop back
            "end": END,        # Exit
        }
    )

    return workflow.compile()


# ============================================================
# Agent Runner
# ============================================================

def run_rag_agent(
    channel_id: str,
    query: str,
    conversation_history: list[dict] | None = None,
    max_iterations: int = 3,
) -> dict[str, Any]:
    """Run the RAG agent to answer a query.

    Args:
        channel_id: The channel ID to search in
        query: User's question
        conversation_history: Previous messages for context
        max_iterations: Maximum iterations (default 3)

    Returns:
        Dict with 'response', 'sources', 'iterations', and optional 'error'
    """
    # Create initial state
    initial_state: AgentState = {
        "channel_id": channel_id,
        "query": query,
        "conversation_history": conversation_history or [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "tool_results": [],
        "sources": [],
        "final_answer": None,
        "error": None,
    }

    # Create and run workflow
    agent = create_rag_agent()
    final_state = agent.invoke(initial_state)

    # Handle max iterations without answer
    if not final_state.get("final_answer") and not final_state.get("error"):
        # Generate forced answer from accumulated results
        if final_state["tool_results"]:
            gemini = GeminiService()
            context = "\n\n".join([r["result"] for r in final_state["tool_results"]])
            prompt = f"Based on the following search results, answer the question: {query}\n\n{context}"
            result = gemini.generate(prompt)
            final_state["final_answer"] = result.get("text", "Unable to generate answer.")
        else:
            final_state["final_answer"] = "No relevant information found in the documents."

    return {
        "response": final_state.get("final_answer") or final_state.get("error") or "No response generated.",
        "sources": final_state.get("sources", []),
        "iterations": final_state.get("iteration", 0),
        "error": final_state.get("error"),
    }
