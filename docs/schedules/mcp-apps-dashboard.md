# MCP Apps Dashboard Development Schedule

## Overview

**Original Request**: Implement MCP Apps dashboard with LangChain 1.0 middleware. Test in local container, then deploy to Azure.

**Scope**:
- LangChain 1.0 create_agent migration
- State publishing middleware
- MCP Apps server with dashboard UI
- Local container testing
- Azure deployment

**Out of Scope**: Agent V2 structure (Retrieve → Rerank → ... → Revise)

---

## Issue List

| ID | Title | Priority | Blocked By |
|----|-------|----------|------------|
| CHA-74 | LangChain 1.0 create_agent migration | High | - |
| CHA-75 | Add state publishing middleware using LangChain 1.0 | High | CHA-74 |
| CHA-76 | Implement MCP Apps server with dashboard UI | High | CHA-75 |
| CHA-77 | Local container integration testing for MCP Apps | Medium | CHA-76 |
| CHA-78 | Azure deployment for MCP Apps dashboard | Medium | CHA-77 |

---

## Dependency Graph

```
[Strict Sequential Dependency - No Parallelization Possible]

CHA-74 (LangChain 1.0 migration)
    │
    │  Creates new agent factory: src/agents/agent_factory.py
    │  Migrates: src/workflows/rag.py
    │
    ▼
CHA-75 (State publishing middleware)
    │
    │  Requires: LangChain 1.0 agent patterns from CHA-74
    │  Creates: src/agents/middlewares/dashboard.py
    │
    ▼
CHA-76 (MCP Apps server + dashboard UI)
    │
    │  Requires: Middleware for state events from CHA-75
    │  Creates: src/mcp_server/* (new module)
    │
    ▼
CHA-77 (Local container testing)
    │
    │  Requires: Complete MCP Apps from CHA-76
    │  Modifies: docker-compose.yml, Dockerfile
    │
    ▼
CHA-78 (Azure deployment)
    │
    │  Requires: Verified container build from CHA-77
    │  Modifies: .github/workflows/*.yml, Azure configs
    │
    ▼
   [DONE]
```

---

## File Conflict Analysis

| Issue | Expected Modified Files | Conflict Group |
|-------|------------------------|----------------|
| CHA-74 | src/workflows/rag.py, src/agents/__init__.py (new), src/agents/agent_factory.py (new) | A |
| CHA-75 | src/agents/middlewares/__init__.py (new), src/agents/middlewares/dashboard.py (new), src/agents/agent_factory.py | A |
| CHA-76 | src/mcp_server/* (new module), src/main.py (maybe) | B |
| CHA-77 | docker-compose.yml, Dockerfile, tests/* | C |
| CHA-78 | .github/workflows/*.yml, infra/* | D |

**Analysis**:
- **CHA-74 → CHA-75**: Conflict Group A - Both modify agent-related files
  - CHA-75 depends on agent patterns created by CHA-74
  - **MUST be sequential** (already set by Linear dependency)
- **CHA-76**: New module (src/mcp_server/), isolated from agents
  - BUT requires middleware events from CHA-75
  - **MUST be sequential** (depends on CHA-75)
- **CHA-77**: Container/test files
  - Requires complete MCP Apps from CHA-76
  - **MUST be sequential**
- **CHA-78**: CI/CD and Azure files
  - Requires verified container from CHA-77
  - **MUST be sequential**

**Conclusion**: All 5 issues have strict sequential dependencies. No parallel execution possible.

---

## Execution Plan

| Step | Issue | Execution | Description | E2E Test Required |
|------|-------|-----------|-------------|-------------------|
| 1 | CHA-74 | Solo | LangChain 1.0 create_agent migration | Mock tests only |
| 2 | CHA-75 | Solo | Add state publishing middleware | Mock tests only |
| 3 | CHA-76 | Solo | MCP Apps server + dashboard UI | Mock tests only |
| 4 | CHA-77 | Solo | Local container integration testing | **Yes - Container build & run** |
| 5 | CHA-78 | Solo | Azure deployment | **Yes - Live Azure verification** |

---

## Issue Details

### CHA-74: LangChain 1.0 create_agent Migration

**Description**: Migrate from current LangGraph patterns to LangChain 1.0 `create_agent()` API.

**Key Changes**:
- Create `src/agents/` module structure
- Implement agent factory using `langchain.agents.create_agent`
- Update `src/workflows/rag.py` to use new agent factory
- Preserve backward compatibility for existing `run_rag_agent()` function

**Files to Create/Modify**:
```
src/agents/__init__.py (new)
src/agents/agent_factory.py (new)
src/workflows/rag.py (modify)
pyproject.toml or requirements.txt (add langchain 1.0)
```

**Tests**:
- Unit tests for agent_factory.py
- Integration tests for rag.py with new agent

---

### CHA-75: Add State Publishing Middleware

**Description**: Implement middleware that captures agent execution state and publishes events for dashboard consumption.

**Key Changes**:
- Create `DashboardMiddleware` class following LangChain 1.0 middleware API
- Implement hooks: `before_agent`, `after_agent`, `before_model`, `after_model`, `wrap_tool_call`
- Create state store interface for event publishing

**Files to Create/Modify**:
```
src/agents/middlewares/__init__.py (new)
src/agents/middlewares/dashboard.py (new)
src/agents/agent_factory.py (modify - integrate middleware)
```

**Tests**:
- Unit tests for middleware hooks
- Integration tests for event publishing

---

### CHA-76: Implement MCP Apps Server with Dashboard UI

**Description**: Create MCP server with UI resources for real-time agent status dashboard.

**Key Changes**:
- Create `src/mcp_server/` module structure
- Implement MCP server with `ui://` resource support
- Create dashboard HTML template with real-time updates
- Define tools: `get_agent_status`, `run_rag_query`

**Files to Create**:
```
src/mcp_server/__init__.py (new)
src/mcp_server/server.py (new)
src/mcp_server/tools.py (new)
src/mcp_server/state.py (new)
src/mcp_server/templates/dashboard.html (new)
```

**Tests**:
- Unit tests for MCP server tools
- Integration tests for UI resource serving

---

### CHA-77: Local Container Integration Testing

**Description**: Verify MCP Apps works correctly in Docker container environment.

**Key Changes**:
- Update `docker-compose.yml` for MCP server service
- Update `Dockerfile` if needed
- Create integration test suite for containerized execution

**Files to Modify**:
```
docker-compose.yml (modify)
Dockerfile (modify if needed)
tests/integration/test_mcp_container.py (new)
```

**Tests**:
- **E2E Required**: Container build, run, and MCP protocol verification

---

### CHA-78: Azure Deployment for MCP Apps Dashboard

**Description**: Deploy MCP Apps dashboard to Azure with CI/CD integration.

**Key Changes**:
- Update GitHub Actions workflow for MCP server deployment
- Configure Azure Container Apps or App Service
- Verify live deployment

**Files to Modify**:
```
.github/workflows/azure-deploy.yml (modify)
infra/* (Azure configs, if needed)
```

**Tests**:
- **E2E Required**: Live Azure endpoint verification

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LangChain 1.0 API instability | High | Pin specific version, check docs |
| MCP SDK breaking changes | Medium | Use stable MCP version (0.9.x) |
| Container networking issues | Medium | Test locally before Azure push |
| Azure deployment quota | Low | Use existing resource group |

---

## Recommendations

1. **Sequential Execution Mandatory**: All 5 issues have strict dependencies. No shortcuts.

2. **External API Tests**:
   - CHA-74, CHA-75, CHA-76: Mock tests sufficient
   - CHA-77: Container E2E required
   - CHA-78: Azure E2E required

3. **Commit Strategy**: Each issue = 1 commit (immediate commit after each completion)

4. **Rollback Plan**: If Azure deployment fails, CHA-74~76 changes remain usable locally.

---

## Estimated Timeline

| Step | Issue | Complexity | Notes |
|------|-------|------------|-------|
| 1 | CHA-74 | Medium | LangChain migration has learning curve |
| 2 | CHA-75 | Medium | Middleware pattern implementation |
| 3 | CHA-76 | High | New module, HTML templates, MCP protocol |
| 4 | CHA-77 | Low | Container config updates |
| 5 | CHA-78 | Medium | CI/CD pipeline updates |

---

## Approval

**Status**: Awaiting Orchestrator 2nd Review

**Schedule Prepared By**: Dev Team Lead
**Date**: 2026-01-23
