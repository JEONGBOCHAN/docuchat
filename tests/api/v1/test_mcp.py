# -*- coding: utf-8 -*-
"""
Tests for MCP Streamable HTTP Transport Endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from src.main import app


ADMIN_KEY = "test-admin-key"


@pytest.fixture(autouse=True)
def _set_admin_key(monkeypatch):
    """Set admin API key for all tests."""
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    from src.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def _ah(extra: dict | None = None) -> dict:
    """Build headers dict with admin key merged in."""
    base = {"X-Admin-Key": ADMIN_KEY}
    if extra:
        base.update(extra)
    return base


class TestMCPStreamableHTTP:
    """Test MCP Streamable HTTP transport endpoint."""

    def test_initialize_creates_session(self, client):
        """Test that initialize request creates a new session."""
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0",
                    },
                },
            },
        )

        assert response.status_code == 200
        assert "Mcp-Session-Id" in response.headers

        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2025-03-26"
        assert "capabilities" in data["result"]
        assert "serverInfo" in data["result"]
        assert data["result"]["serverInfo"]["name"] == "agent-dashboard"

    def test_request_without_session_fails(self, client):
        """Test that requests without session ID fail (except initialize)."""
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/list",
                "params": {},
            },
        )

        assert response.status_code == 400
        assert "Missing Mcp-Session-Id" in response.json()["detail"]

    def test_request_with_invalid_session_fails(self, client):
        """Test that requests with invalid session ID fail."""
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": "invalid-session-id"}),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/list",
                "params": {},
            },
        )

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    def test_resources_list(self, client):
        """Test resources/list returns available resources."""
        # First, initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Then, list resources
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
                "params": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        assert "result" in data
        assert "resources" in data["result"]

        resources = data["result"]["resources"]
        assert len(resources) >= 1

        # Check for dashboard resource
        dashboard_resource = next(
            (r for r in resources if r["uri"] == "ui://dashboard/agent-status"),
            None,
        )
        assert dashboard_resource is not None
        assert dashboard_resource["mimeType"] == "text/html"

    def test_resources_read(self, client):
        """Test resources/read returns resource content."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Read resource
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {"uri": "ui://dashboard/agent-status"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "contents" in data["result"]

        contents = data["result"]["contents"]
        assert len(contents) == 1
        assert contents[0]["uri"] == "ui://dashboard/agent-status"
        assert contents[0]["mimeType"] == "text/html"
        assert "<!DOCTYPE html>" in contents[0]["text"] or "<html" in contents[0]["text"].lower()

    def test_resources_read_not_found(self, client):
        """Test resources/read returns error for unknown resource."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Try to read unknown resource
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {"uri": "ui://unknown/resource"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Resource not found" in data["error"]["message"]

    def test_tools_list(self, client):
        """Test tools/list returns available tools."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # List tools
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "tools" in data["result"]

        tools = data["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        assert "get_agent_status" in tool_names
        assert "run_rag_query" in tool_names
        assert "reset_agent_state" in tool_names

    def test_tools_call_get_agent_status(self, client):
        """Test tools/call for get_agent_status."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Call tool
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_agent_status",
                    "arguments": {},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "content" in data["result"]
        assert data["result"]["isError"] is False

    def test_tools_call_reset_agent_state(self, client):
        """Test tools/call for reset_agent_state."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Call tool
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "reset_agent_state",
                    "arguments": {},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["isError"] is False

    def test_tools_call_not_found(self, client):
        """Test tools/call returns error for unknown tool."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Try to call unknown tool
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "unknown_tool",
                    "arguments": {},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Tool not found" in data["error"]["message"]

    def test_batch_requests(self, client):
        """Test batch JSON-RPC requests."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Batch request
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json=[
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "resources/list",
                    "params": {},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/list",
                    "params": {},
                },
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Check both responses are present
        ids = [r["id"] for r in data]
        assert 2 in ids
        assert 3 in ids

    def test_notification_returns_202(self, client):
        """Test that notifications return 202 Accepted."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Send notification (no id)
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )

        assert response.status_code == 202

    def test_ping(self, client):
        """Test ping method."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Ping
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "ping",
                "params": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        assert "result" in data

    def test_method_not_found(self, client):
        """Test unknown method returns error."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Unknown method
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "unknown/method",
                "params": {},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601
        assert "Method not found" in data["error"]["message"]

    def test_session_delete(self, client):
        """Test session termination."""
        # Initialize
        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session_id = init_response.headers["Mcp-Session-Id"]

        # Delete session
        response = client.delete(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
        )

        assert response.status_code == 204

        # Try to use session after deletion
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "ping",
                "params": {},
            },
        )

        assert response.status_code == 404

    def test_get_message_not_supported(self, client):
        """Test GET /message returns 405."""
        response = client.get("/api/v1/mcp/message", headers=_ah())
        assert response.status_code == 405

    def test_state_endpoint(self, client):
        """Test convenience state endpoint."""
        response = client.get("/api/v1/mcp/state", headers=_ah())
        assert response.status_code == 200

        data = response.json()
        assert "status" in data

    def test_invalid_json(self, client):
        """Test invalid JSON returns 400."""
        response = client.post(
            "/api/v1/mcp/message",
            content="invalid json{",
            headers=_ah({"Content-Type": "application/json"}),
        )
        assert response.status_code == 400

    def test_mcp_message_without_admin_key_rejected(self, client):
        """Test that MCP message endpoint rejects requests without admin key."""
        response = client.post(
            "/api/v1/mcp/message",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        assert response.status_code in (401, 422)

    def test_mcp_state_without_admin_key_rejected(self, client):
        """Test that MCP state endpoint rejects requests without admin key."""
        response = client.get("/api/v1/mcp/state")
        assert response.status_code in (401, 422)

    def test_mcp_get_message_without_admin_key_rejected(self, client):
        """Test that GET /mcp/message rejects requests without admin key."""
        response = client.get("/api/v1/mcp/message")
        assert response.status_code in (401, 422)

    def test_mcp_delete_message_without_admin_key_rejected(self, client):
        """Test that DELETE /mcp/message rejects requests without admin key."""
        response = client.delete(
            "/api/v1/mcp/message",
            headers={"Mcp-Session-Id": "some-session"},
        )
        assert response.status_code in (401, 422)


class TestMCPSessionManagement:
    """Test session management in detail."""

    def test_multiple_sessions(self, client):
        """Test multiple independent sessions."""
        # Create first session
        init1 = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session1 = init1.headers["Mcp-Session-Id"]

        # Create second session
        init2 = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            },
        )
        session2 = init2.headers["Mcp-Session-Id"]

        # Sessions should be different
        assert session1 != session2

        # Both sessions should work independently
        for session_id in [session1, session2]:
            response = client.post(
                "/api/v1/mcp/message",
                headers=_ah({"Mcp-Session-Id": session_id}),
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "ping",
                    "params": {},
                },
            )
            assert response.status_code == 200

    def test_session_persists_client_info(self, client):
        """Test that session stores client info."""
        # Initialize with client info
        client_info = {
            "name": "test-client",
            "version": "1.2.3",
        }

        init_response = client.post(
            "/api/v1/mcp/message",
            headers=_ah(),
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": client_info,
                },
            },
        )

        assert init_response.status_code == 200
        session_id = init_response.headers["Mcp-Session-Id"]

        # Session should be valid for subsequent requests
        response = client.post(
            "/api/v1/mcp/message",
            headers=_ah({"Mcp-Session-Id": session_id}),
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
                "params": {},
            },
        )
        assert response.status_code == 200
