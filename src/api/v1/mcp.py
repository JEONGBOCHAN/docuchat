# -*- coding: utf-8 -*-
"""
MCP Streamable HTTP Transport Endpoint.

Implements MCP (Model Context Protocol) Streamable HTTP transport,
the modern standard for browser-compatible MCP communication.

Specification: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
"""

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from src.mcp_server.server import mcp_server
from src.mcp_server.state import get_global_state_store


router = APIRouter(prefix="/mcp", tags=["mcp"])


# ============================================================
# Session Management
# ============================================================

# In-memory session store with TTL and capacity limit
_sessions: dict[str, dict[str, Any]] = {}

SESSION_TTL_SECONDS = 3600  # 1 hour
MAX_SESSIONS = 1000


def _cleanup_expired_sessions() -> None:
    """Remove sessions that have exceeded the TTL."""
    now = time.monotonic()
    expired = [
        sid for sid, data in _sessions.items()
        if now - data.get("_last_seen", 0) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _sessions[sid]


def get_or_create_session(session_id: str | None) -> tuple[str, dict[str, Any]]:
    """Get existing session or create a new one.

    Args:
        session_id: Existing session ID or None for new session.

    Returns:
        Tuple of (session_id, session_data).
    """
    if session_id and session_id in _sessions:
        _sessions[session_id]["_last_seen"] = time.monotonic()
        return session_id, _sessions[session_id]

    # Cleanup before creating a new session
    _cleanup_expired_sessions()

    if len(_sessions) >= MAX_SESSIONS:
        raise HTTPException(
            status_code=503,
            detail="Maximum number of MCP sessions reached. Try again later.",
        )

    new_id = str(uuid.uuid4())
    _sessions[new_id] = {
        "initialized": False,
        "client_info": None,
        "_last_seen": time.monotonic(),
    }
    return new_id, _sessions[new_id]


def validate_session(session_id: str | None) -> dict[str, Any] | None:
    """Validate session ID and return session data.

    Args:
        session_id: Session ID to validate.

    Returns:
        Session data if valid, None otherwise.
    """
    if not session_id:
        return None
    session = _sessions.get(session_id)
    if session is not None:
        session["_last_seen"] = time.monotonic()
    return session


# ============================================================
# MCP Protocol Handlers
# ============================================================

async def handle_initialize(params: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    """Handle MCP initialize request.

    Args:
        params: Initialize parameters from client.
        session: Session data.

    Returns:
        InitializeResult with server capabilities.
    """
    session["initialized"] = True
    session["client_info"] = params.get("clientInfo", {})

    return {
        "protocolVersion": "2025-03-26",
        "capabilities": {
            "resources": {
                "subscribe": False,
                "listChanged": False,
            },
            "tools": {},
        },
        "serverInfo": {
            "name": "agent-dashboard",
            "version": "1.0.0",
        },
    }


async def handle_resources_list() -> dict[str, Any]:
    """Handle resources/list request.

    Returns:
        List of available resources.
    """
    return {
        "resources": [
            {
                "uri": "ui://dashboard/agent-status",
                "name": "agent-status-dashboard",
                "description": "Real-time visualization of agent execution state",
                "mimeType": "text/html",
            }
        ]
    }


async def handle_resources_read(params: dict[str, Any]) -> dict[str, Any]:
    """Handle resources/read request.

    Args:
        params: Request parameters containing uri.

    Returns:
        Resource contents.
    """
    uri = params.get("uri", "")

    if uri == "ui://dashboard/agent-status":
        # Get the HTML content from the MCP server resource
        from src.mcp_server.server import agent_status_ui
        html_content = await agent_status_ui()

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/html",
                    "text": html_content,
                }
            ]
        }

    raise HTTPException(status_code=404, detail=f"Resource not found: {uri}")


async def handle_tools_list() -> dict[str, Any]:
    """Handle tools/list request.

    Returns:
        List of available tools.
    """
    return {
        "tools": [
            {
                "name": "get_agent_status",
                "description": "Get the current agent execution status for a specific channel.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The channel ID to get status for.",
                        },
                    },
                    "required": ["channel_id"],
                },
            },
            {
                "name": "run_rag_query",
                "description": "Run a RAG (Retrieval-Augmented Generation) query and visualize execution in the dashboard.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The channel (FileSearchStore) ID to search in.",
                        },
                        "query": {
                            "type": "string",
                            "description": "The user's question to answer.",
                        },
                    },
                    "required": ["channel_id", "query"],
                },
            },
            {
                "name": "reset_agent_state",
                "description": "Reset the agent execution state to idle for a specific channel.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The channel ID to reset. Resets all if not specified.",
                        },
                    },
                    "required": [],
                },
            },
        ]
    }


async def handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    """Handle tools/call request.

    Args:
        params: Request parameters containing tool name and arguments.

    Returns:
        Tool execution result.
    """
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name == "get_agent_status":
        from src.mcp_server.server import get_agent_status_tool
        channel_id = arguments.get("channel_id")
        result = await get_agent_status_tool(channel_id=channel_id)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False),
                }
            ],
            "isError": False,
        }

    elif tool_name == "run_rag_query":
        from src.mcp_server.server import run_rag_query_tool
        channel_id = arguments.get("channel_id", "")
        query = arguments.get("query", "")
        result = await run_rag_query_tool(channel_id=channel_id, query=query)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False),
                }
            ],
            "isError": False,
        }

    elif tool_name == "reset_agent_state":
        from src.mcp_server.server import reset_agent_state_tool
        channel_id = arguments.get("channel_id")
        result = await reset_agent_state_tool(channel_id=channel_id)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False),
                }
            ],
            "isError": False,
        }

    raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")


async def process_jsonrpc_message(message: dict[str, Any], session: dict[str, Any]) -> dict[str, Any] | None:
    """Process a single JSON-RPC message.

    Args:
        message: JSON-RPC request/notification.
        session: Session data.

    Returns:
        JSON-RPC response or None for notifications.
    """
    method = message.get("method", "")
    params = message.get("params", {})
    msg_id = message.get("id")

    # Handle notifications (no id = no response expected)
    if msg_id is None:
        if method == "notifications/initialized":
            # Client acknowledges initialization, no response needed
            return None
        return None

    try:
        # Route to appropriate handler
        if method == "initialize":
            result = await handle_initialize(params, session)
        elif method == "resources/list":
            result = await handle_resources_list()
        elif method == "resources/read":
            result = await handle_resources_read(params)
        elif method == "tools/list":
            result = await handle_tools_list()
        elif method == "tools/call":
            result = await handle_tools_call(params)
        elif method == "ping":
            result = {}
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }
    except HTTPException as e:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32000,
                "message": e.detail,
            },
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32603,
                "message": str(e),
            },
        }


# ============================================================
# HTTP Endpoints
# ============================================================

@router.post("/message")
async def mcp_message(request: Request):
    """Handle MCP Streamable HTTP POST requests.

    Implements the Streamable HTTP transport specification:
    - Accepts JSON-RPC messages (single or batch)
    - Returns JSON response or SSE stream
    - Manages session via Mcp-Session-Id header
    """
    # Get session ID from header
    session_id = request.headers.get("Mcp-Session-Id")

    # Parse request body
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Handle batch or single message
    is_batch = isinstance(body, list)
    messages = body if is_batch else [body]

    # Get or create session
    # For initialize request, always create new session if none provided
    is_initialize = any(m.get("method") == "initialize" for m in messages)

    if is_initialize:
        session_id, session = get_or_create_session(None)
    else:
        if not session_id:
            raise HTTPException(status_code=400, detail="Missing Mcp-Session-Id header")
        session = validate_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    # Process messages
    responses = []
    for message in messages:
        response = await process_jsonrpc_message(message, session)
        if response is not None:
            responses.append(response)

    # If no responses (all notifications), return 202 Accepted
    if not responses:
        return Response(status_code=202)

    # Return response(s)
    result = responses if is_batch else responses[0] if responses else None

    # Build response with session header
    response = JSONResponse(content=result)

    # Set session ID header for initialize response
    if is_initialize:
        response.headers["Mcp-Session-Id"] = session_id

    return response


@router.get("/message")
async def mcp_message_stream(request: Request):
    """Handle MCP Streamable HTTP GET requests (SSE stream).

    Opens an SSE stream for server-initiated messages.
    Currently returns 405 as we don't support server-initiated streams.
    """
    # For now, we don't support server-initiated streams
    # This endpoint would be used for long-running operations
    raise HTTPException(
        status_code=405,
        detail="Server-initiated streams not supported",
    )


@router.delete("/message")
async def mcp_message_delete(request: Request):
    """Handle session termination.

    Allows clients to explicitly terminate their session.
    """
    session_id = request.headers.get("Mcp-Session-Id")

    if not session_id:
        raise HTTPException(status_code=400, detail="Missing Mcp-Session-Id header")

    if session_id in _sessions:
        del _sessions[session_id]
        return Response(status_code=204)

    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/state")
async def get_mcp_state(channel_id: str | None = None):
    """Get current agent state as JSON (convenience endpoint).

    This is not part of MCP protocol but useful for debugging.

    Args:
        channel_id: Optional channel ID to get state for.
    """
    state_store = get_global_state_store()
    return JSONResponse(content=state_store.get_state(channel_id))
