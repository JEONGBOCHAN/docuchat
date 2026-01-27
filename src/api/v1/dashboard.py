# -*- coding: utf-8 -*-
"""
Dashboard API - HTTP endpoint for MCP Apps dashboard.

This provides browser access to the agent dashboard UI for testing purposes.
In production, the dashboard is served via MCP protocol.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import json

from src.mcp_server.state import get_global_state_store
from src.core.config import GeminiModels

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the agent dashboard UI."""
    template_path = Path(__file__).parent.parent.parent / "mcp_server" / "templates" / "dashboard.html"

    if not template_path.exists():
        return HTMLResponse(
            content="<h1>Dashboard template not found</h1>",
            status_code=404
        )

    template = template_path.read_text(encoding="utf-8")

    # Inject current state
    state_store = get_global_state_store()
    current_state = state_store.get_state()
    state_json = json.dumps(current_state)

    html = template.replace("__INITIAL_STATE__", state_json)

    return HTMLResponse(content=html)


@router.get("/state")
async def get_dashboard_state(channel_id: str | None = None):
    """Get current agent state as JSON.

    Args:
        channel_id: Optional channel ID to get state for.
                   If not provided, returns the most recently active channel's state
                   or default idle state if none.
    """
    state_store = get_global_state_store()

    # If no channel_id provided, try to get the most recently active channel
    if channel_id is None:
        all_states = state_store.get_all_states()
        if all_states:
            # Find the most recently active (running or just completed)
            for cid, state in all_states.items():
                if state.get("status") in ["running", "complete"]:
                    return JSONResponse(content=state)
            # Fall back to first channel's state
            first_channel = next(iter(all_states.keys()))
            return JSONResponse(content=all_states[first_channel])

    return JSONResponse(content=state_store.get_state(channel_id))


@router.post("/reset")
async def reset_dashboard_state():
    """Reset agent state to initial idle state."""
    state_store = get_global_state_store()
    state_store.reset()
    return JSONResponse(content={"status": "reset", "state": state_store.get_state()})


@router.post("/simulate/{event_type}")
async def simulate_event(event_type: str):
    """Simulate agent events for testing the dashboard.

    Event types:
    - start: Start agent execution
    - model_start: Model inference started
    - model_complete: Model inference completed
    - tool_start: Tool execution started
    - tool_complete: Tool execution completed
    - complete: Agent completed successfully
    - error: Agent encountered an error
    """
    state_store = get_global_state_store()

    if event_type == "start":
        state_store.on_agent_start(query="테스트 질문입니다", channel_id="test-channel")
    elif event_type == "model_start":
        state_store.on_model_start(model_name=GeminiModels.DEFAULT)
    elif event_type == "model_complete":
        state_store.on_model_complete(
            model_name=GeminiModels.DEFAULT,
            input_tokens=100,
            output_tokens=50
        )
    elif event_type == "tool_start":
        state_store.on_tool_start(tool_name="search_documents", tool_input={"query": "test"})
    elif event_type == "tool_complete":
        state_store.on_tool_complete(tool_name="search_documents", tool_output={"results": []})
    elif event_type == "complete":
        state_store.on_agent_complete(response="테스트 응답입니다", sources=[])
    elif event_type == "error":
        state_store.on_agent_error(error="테스트 에러입니다")
    else:
        return JSONResponse(
            content={"error": f"Unknown event type: {event_type}"},
            status_code=400
        )

    return JSONResponse(content={"status": "simulated", "event": event_type, "state": state_store.get_state()})
