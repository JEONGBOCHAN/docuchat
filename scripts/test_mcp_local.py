#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Local MCP Server Testing Script.

This script provides comprehensive testing for the MCP Apps server
without requiring Docker. It can be run directly to validate:
- MCP server initialization
- Tool registration
- State store functionality
- UI resource serving
- Dashboard middleware integration

Usage:
    python scripts/test_mcp_local.py

Options:
    --verbose    Show detailed test output
    --quick      Run only quick tests (skip E2E simulation)
"""

import argparse
import asyncio
import json
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class TestResult:
    """Result of a single test."""

    name: str
    passed: bool
    message: str
    duration_ms: float


class MCPLocalTester:
    """Local MCP server tester."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[TestResult] = []

    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        if self.verbose or level in ("ERROR", "RESULT"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

    def run_test(self, name: str, test_fn: Callable[[], bool]) -> bool:
        """Run a single test and record the result."""
        start = datetime.now()
        try:
            passed = test_fn()
            duration = (datetime.now() - start).total_seconds() * 1000
            result = TestResult(
                name=name,
                passed=passed,
                message="PASSED" if passed else "FAILED",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            result = TestResult(
                name=name,
                passed=False,
                message=f"ERROR: {str(e)}",
                duration_ms=duration,
            )
            if self.verbose:
                traceback.print_exc()

        self.results.append(result)
        status = "" if result.passed else ""
        self.log(f"{status} {name} ({result.duration_ms:.1f}ms)", "RESULT")

        if not result.passed and self.verbose:
            self.log(f"   {result.message}", "ERROR")

        return result.passed

    async def run_async_test(self, name: str, test_fn: Callable[[], Any]) -> bool:
        """Run an async test and record the result."""
        start = datetime.now()
        try:
            passed = await test_fn()
            duration = (datetime.now() - start).total_seconds() * 1000
            result = TestResult(
                name=name,
                passed=passed,
                message="PASSED" if passed else "FAILED",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            result = TestResult(
                name=name,
                passed=False,
                message=f"ERROR: {str(e)}",
                duration_ms=duration,
            )
            if self.verbose:
                traceback.print_exc()

        self.results.append(result)
        status = "" if result.passed else ""
        self.log(f"{status} {name} ({result.duration_ms:.1f}ms)", "RESULT")

        if not result.passed and self.verbose:
            self.log(f"   {result.message}", "ERROR")

        return result.passed

    def print_summary(self):
        """Print test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        print("\n" + "=" * 60)
        print("MCP LOCAL TEST SUMMARY")
        print("=" * 60)
        print(f"Total:  {total}")
        print(f"Passed: {passed} ")
        print(f"Failed: {failed} {'❌' if failed > 0 else ''}")
        print("=" * 60)

        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        return failed == 0


# ============================================================
# Test Functions
# ============================================================

def test_state_store_import():
    """Test that state store can be imported."""
    from src.mcp_server.state import AgentStateStore, get_global_state_store

    store = AgentStateStore()
    return store is not None


def test_state_store_initial_state():
    """Test initial state is idle."""
    from src.mcp_server.state import AgentStateStore

    store = AgentStateStore()
    state = store.get_state()

    return (
        state["status"] == "idle"
        and state["current_node"] is None
        and state["steps"] == []
    )


def test_state_store_update():
    """Test state updates work correctly."""
    from src.mcp_server.state import AgentStateStore

    store = AgentStateStore()

    # Update with agent_start
    store.update({
        "event": "agent_start",
        "timestamp": datetime.now().isoformat(),
        "data": {"query": "Test query"},
    })

    state = store.get_state()
    return state["status"] == "running" and state["current_query"] == "Test query"


def test_state_store_reset():
    """Test state reset works correctly."""
    from src.mcp_server.state import AgentStateStore

    store = AgentStateStore()

    # Modify state
    store.update({
        "event": "agent_start",
        "timestamp": datetime.now().isoformat(),
    })

    # Reset
    store.reset()

    state = store.get_state()
    return state["status"] == "idle" and state["steps"] == []


def test_global_state_store():
    """Test global state store singleton."""
    from src.mcp_server.state import get_global_state_store, reset_global_state_store

    reset_global_state_store()

    store1 = get_global_state_store()
    store2 = get_global_state_store()

    return store1 is store2


def test_pipeline_nodes():
    """Test pipeline nodes are included in state."""
    from src.mcp_server.state import AgentStateStore, PIPELINE_NODES

    store = AgentStateStore()
    state = store.get_state()

    return (
        "pipeline_nodes" in state
        and len(state["pipeline_nodes"]) == len(PIPELINE_NODES)
    )


def test_mcp_server_import():
    """Test MCP server can be imported."""
    from src.mcp_server.server import mcp_server

    return mcp_server is not None and mcp_server.name == "agent-dashboard"


def test_template_loading():
    """Test dashboard template can be loaded."""
    from src.mcp_server.server import load_template

    html = load_template("dashboard.html")

    return (
        html is not None
        and "Agent Status Dashboard" in html
        and "__INITIAL_STATE__" in html
    )


def test_state_injection():
    """Test state injection into template."""
    from src.mcp_server.server import inject_state_into_template

    html = "const state = __INITIAL_STATE__;"
    state = {"status": "running", "current_node": "Draft"}

    result = inject_state_into_template(html, state)

    return (
        "__INITIAL_STATE__" not in result
        and '"status": "running"' in result
    )


def test_dashboard_middleware_import():
    """Test dashboard middleware can be imported."""
    from src.agents.middlewares.dashboard import DashboardMiddleware

    return DashboardMiddleware is not None


def test_dashboard_middleware_creation():
    """Test dashboard middleware can be created."""
    from src.agents.middlewares.dashboard import DashboardMiddleware

    events = []

    def capture(event):
        events.append(event)

    middleware = DashboardMiddleware(state_updater=capture)

    return middleware is not None and middleware.name == "dashboard_middleware"


def test_middleware_integration():
    """Test middleware integrates with state store."""
    from src.mcp_server.state import AgentStateStore
    from src.agents.middlewares.dashboard import DashboardMiddleware

    store = AgentStateStore()
    middleware = DashboardMiddleware(state_updater=store.update)

    # Simulate agent start
    middleware.before_agent(
        state={"messages": [{"role": "user", "content": "Test query"}]},
        runtime=None,
    )

    state = store.get_state()
    return state["status"] == "running"


async def test_get_agent_status_tool():
    """Test get_agent_status tool."""
    from src.mcp_server.state import AgentStateStore
    from src.mcp_server.tools import get_agent_status

    store = AgentStateStore()
    store.update({
        "event": "agent_start",
        "timestamp": datetime.now().isoformat(),
    })

    result = await get_agent_status(state_store=store)

    return result["status"] == "running"


async def test_reset_agent_state_tool():
    """Test reset_agent_state tool."""
    from src.mcp_server.state import AgentStateStore
    from src.mcp_server.tools import reset_agent_state

    store = AgentStateStore()
    store.update({
        "event": "agent_start",
        "timestamp": datetime.now().isoformat(),
    })

    result = await reset_agent_state(state_store=store)

    return (
        result["message"] == "Agent state reset to idle"
        and result["state"]["status"] == "idle"
    )


async def test_ui_resource():
    """Test UI resource returns valid HTML."""
    from unittest.mock import patch
    from src.mcp_server.state import AgentStateStore
    from src.mcp_server.server import agent_status_ui

    store = AgentStateStore()

    with patch("src.mcp_server.server.get_global_state_store", return_value=store):
        html = await agent_status_ui()

    return html is not None and "Agent Status Dashboard" in html


def test_complete_workflow_simulation():
    """Test a complete RAG workflow simulation."""
    from src.mcp_server.state import AgentStateStore

    store = AgentStateStore()

    # Simulate complete workflow
    events = [
        {"event": "agent_start", "data": {"query": "Test query"}},
        {"event": "tool_start", "node": "Retrieve"},
        {"event": "tool_complete", "node": "Retrieve", "data": {"duration_ms": 500}},
        {"event": "model_start", "node": "Draft"},
        {"event": "model_complete", "node": "Draft", "data": {"duration_ms": 2000}},
        {"event": "agent_complete"},
    ]

    for event in events:
        store.update({
            **event,
            "timestamp": datetime.now().isoformat(),
        })

    state = store.get_state()

    return (
        state["status"] == "complete"
        and state["metrics"]["total_steps"] == 2
        and state["metrics"]["tool_calls"] == 1
        and state["metrics"]["model_calls"] == 1
        and all(s["status"] == "complete" for s in state["steps"])
    )


def test_error_workflow_simulation():
    """Test error handling in workflow."""
    from src.mcp_server.state import AgentStateStore

    store = AgentStateStore()

    store.update({
        "event": "agent_start",
        "timestamp": datetime.now().isoformat(),
    })

    store.update({
        "event": "agent_error",
        "timestamp": datetime.now().isoformat(),
        "error": "Test error",
    })

    state = store.get_state()

    return state["status"] == "error" and state["last_error"] == "Test error"


def test_subscriber_notification():
    """Test subscriber notification works."""
    from src.mcp_server.state import AgentStateStore

    store = AgentStateStore()
    events = []

    def capture(state):
        events.append(state)

    store.subscribe(capture)

    store.update({
        "event": "agent_start",
        "timestamp": datetime.now().isoformat(),
    })

    store.unsubscribe(capture)

    return len(events) == 1 and events[0]["status"] == "running"


def test_thread_safety():
    """Test thread-safe updates."""
    import threading
    from src.mcp_server.state import AgentStateStore

    store = AgentStateStore()
    store.update({
        "event": "agent_start",
        "timestamp": datetime.now().isoformat(),
    })

    errors = []

    def update_state():
        try:
            for i in range(50):
                store.update({
                    "event": "tool_start",
                    "timestamp": datetime.now().isoformat(),
                    "node": f"Tool_{i}",
                })
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=update_state) for _ in range(4)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    state = store.get_state()

    return len(errors) == 0 and state["metrics"]["total_steps"] == 200


# ============================================================
# Main
# ============================================================

async def main():
    """Run all MCP local tests."""
    parser = argparse.ArgumentParser(description="Local MCP Server Testing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick tests only")
    args = parser.parse_args()

    tester = MCPLocalTester(verbose=args.verbose)

    print("=" * 60)
    print("MCP LOCAL SERVER TESTS")
    print("=" * 60)
    print()

    # Sync tests
    print("State Store Tests:")
    tester.run_test("Import state store", test_state_store_import)
    tester.run_test("Initial state is idle", test_state_store_initial_state)
    tester.run_test("State update works", test_state_store_update)
    tester.run_test("State reset works", test_state_store_reset)
    tester.run_test("Global state store singleton", test_global_state_store)
    tester.run_test("Pipeline nodes present", test_pipeline_nodes)

    print("\nMCP Server Tests:")
    tester.run_test("Import MCP server", test_mcp_server_import)
    tester.run_test("Load dashboard template", test_template_loading)
    tester.run_test("State injection into template", test_state_injection)

    print("\nDashboard Middleware Tests:")
    tester.run_test("Import middleware", test_dashboard_middleware_import)
    tester.run_test("Create middleware", test_dashboard_middleware_creation)
    tester.run_test("Middleware integration", test_middleware_integration)

    print("\nAsync Tool Tests:")
    await tester.run_async_test("get_agent_status tool", test_get_agent_status_tool)
    await tester.run_async_test("reset_agent_state tool", test_reset_agent_state_tool)
    await tester.run_async_test("UI resource serving", test_ui_resource)

    print("\nSubscriber Tests:")
    tester.run_test("Subscriber notification", test_subscriber_notification)

    if not args.quick:
        print("\nWorkflow Simulation Tests:")
        tester.run_test("Complete RAG workflow", test_complete_workflow_simulation)
        tester.run_test("Error workflow handling", test_error_workflow_simulation)
        tester.run_test("Thread safety", test_thread_safety)

    return tester.print_summary()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
