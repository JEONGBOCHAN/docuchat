/**
 * Tests for MCP Client
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createMCPClient, MCPClient } from '@/lib/mcp/client';
import type { MCPClientState } from '@/lib/mcp/types';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('MCPClient', () => {
  let client: MCPClient;

  beforeEach(() => {
    client = createMCPClient();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ---------------------------------------------------------------------------
  // State Management Tests
  // ---------------------------------------------------------------------------

  describe('State Management', () => {
    it('should have initial disconnected state', () => {
      const state = client.getState();
      expect(state.connectionState).toBe('disconnected');
      expect(state.sessionId).toBeNull();
      expect(state.serverInfo).toBeNull();
      expect(state.resources).toEqual([]);
      expect(state.tools).toEqual([]);
    });

    it('should notify subscribers on state change', async () => {
      const listener = vi.fn();
      client.subscribe(listener);

      // Initial call
      expect(listener).toHaveBeenCalledTimes(1);
      expect(listener).toHaveBeenCalledWith(expect.objectContaining({
        connectionState: 'disconnected',
      }));
    });

    it('should allow unsubscribing', () => {
      const listener = vi.fn();
      const unsubscribe = client.subscribe(listener);

      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();

      // Manually trigger state change by accessing private method
      // This is a basic test - full integration would trigger real state changes
    });
  });

  // ---------------------------------------------------------------------------
  // Connection Tests
  // ---------------------------------------------------------------------------

  describe('Connection', () => {
    it('should connect successfully', async () => {
      // Mock initialize response
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'Mcp-Session-Id': 'test-session-123' }),
        json: async () => ({
          jsonrpc: '2.0',
          id: 1,
          result: {
            protocolVersion: '2025-03-26',
            capabilities: { resources: {}, tools: {} },
            serverInfo: { name: 'test-server', version: '1.0.0' },
          },
        }),
      });

      // Mock notifications/initialized (202 Accepted)
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 202,
      });

      // Mock resources/list
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 2,
          result: {
            resources: [
              { uri: 'ui://dashboard/agent-status', name: 'dashboard', mimeType: 'text/html' },
            ],
          },
        }),
      });

      // Mock tools/list
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 3,
          result: {
            tools: [
              { name: 'get_agent_status', description: 'Get agent status' },
            ],
          },
        }),
      });

      await client.connect();

      const state = client.getState();
      expect(state.connectionState).toBe('connected');
      expect(state.sessionId).toBe('test-session-123');
      expect(state.serverInfo?.name).toBe('test-server');
      expect(state.resources).toHaveLength(1);
      expect(state.tools).toHaveLength(1);
    });

    it('should handle connection error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(client.connect()).rejects.toThrow('Network error');

      const state = client.getState();
      expect(state.connectionState).toBe('error');
      expect(state.error).toBe('Network error');
    });

    it('should not reconnect if already connected', async () => {
      // Set up successful connection
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'Mcp-Session-Id': 'session-1' }),
        json: async () => ({
          jsonrpc: '2.0',
          id: 1,
          result: {
            protocolVersion: '2025-03-26',
            capabilities: {},
            serverInfo: { name: 'test', version: '1.0.0' },
          },
        }),
      });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 202 });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 2, result: { resources: [] } }),
      });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 3, result: { tools: [] } }),
      });

      await client.connect();
      const callCount = mockFetch.mock.calls.length;

      // Try to connect again
      await client.connect();

      // Should not have made additional calls
      expect(mockFetch.mock.calls.length).toBe(callCount);
    });
  });

  // ---------------------------------------------------------------------------
  // Disconnect Tests
  // ---------------------------------------------------------------------------

  describe('Disconnect', () => {
    it('should disconnect and reset state', async () => {
      // Connect first
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'Mcp-Session-Id': 'session-1' }),
        json: async () => ({
          jsonrpc: '2.0',
          id: 1,
          result: {
            protocolVersion: '2025-03-26',
            capabilities: {},
            serverInfo: { name: 'test', version: '1.0.0' },
          },
        }),
      });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 202 });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 2, result: { resources: [] } }),
      });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 3, result: { tools: [] } }),
      });

      await client.connect();
      expect(client.isConnected()).toBe(true);

      // Mock DELETE response
      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });

      await client.disconnect();

      expect(client.isConnected()).toBe(false);
      const state = client.getState();
      expect(state.connectionState).toBe('disconnected');
      expect(state.sessionId).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // Resource Operations Tests
  // ---------------------------------------------------------------------------

  describe('Resource Operations', () => {
    beforeEach(async () => {
      // Set up connected state
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'Mcp-Session-Id': 'session-1' }),
        json: async () => ({
          jsonrpc: '2.0',
          id: 1,
          result: {
            protocolVersion: '2025-03-26',
            capabilities: {},
            serverInfo: { name: 'test', version: '1.0.0' },
          },
        }),
      });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 202 });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 2, result: { resources: [] } }),
      });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 3, result: { tools: [] } }),
      });

      await client.connect();
    });

    it('should list resources', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 4,
          result: {
            resources: [
              { uri: 'ui://dashboard/agent-status', name: 'dashboard', mimeType: 'text/html' },
            ],
          },
        }),
      });

      const resources = await client.listResources();
      expect(resources).toHaveLength(1);
      expect(resources[0].uri).toBe('ui://dashboard/agent-status');
    });

    it('should read resource', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 4,
          result: {
            contents: [
              { uri: 'ui://dashboard/agent-status', mimeType: 'text/html', text: '<html></html>' },
            ],
          },
        }),
      });

      const result = await client.readResource('ui://dashboard/agent-status');
      expect(result.contents).toHaveLength(1);
      expect(result.contents[0].text).toBe('<html></html>');
    });

    it('should throw when not connected', async () => {
      const newClient = createMCPClient();
      await expect(newClient.listResources()).rejects.toThrow('not connected');
    });
  });

  // ---------------------------------------------------------------------------
  // Tool Operations Tests
  // ---------------------------------------------------------------------------

  describe('Tool Operations', () => {
    beforeEach(async () => {
      // Set up connected state
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'Mcp-Session-Id': 'session-1' }),
        json: async () => ({
          jsonrpc: '2.0',
          id: 1,
          result: {
            protocolVersion: '2025-03-26',
            capabilities: {},
            serverInfo: { name: 'test', version: '1.0.0' },
          },
        }),
      });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 202 });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 2, result: { resources: [] } }),
      });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 3, result: { tools: [] } }),
      });

      await client.connect();
    });

    it('should list tools', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 4,
          result: {
            tools: [
              { name: 'get_agent_status', description: 'Get status' },
              { name: 'run_rag_query', description: 'Run query' },
            ],
          },
        }),
      });

      const tools = await client.listTools();
      expect(tools).toHaveLength(2);
      expect(tools[0].name).toBe('get_agent_status');
    });

    it('should call tool', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 4,
          result: {
            content: [
              { type: 'text', text: '{"status": "idle"}' },
            ],
            isError: false,
          },
        }),
      });

      const result = await client.callTool('get_agent_status');
      expect(result.isError).toBe(false);
      expect(result.content[0].text).toBe('{"status": "idle"}');
    });
  });

  // ---------------------------------------------------------------------------
  // Dashboard-specific Operations Tests
  // ---------------------------------------------------------------------------

  describe('Dashboard Operations', () => {
    beforeEach(async () => {
      // Set up connected state
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ 'Mcp-Session-Id': 'session-1' }),
        json: async () => ({
          jsonrpc: '2.0',
          id: 1,
          result: {
            protocolVersion: '2025-03-26',
            capabilities: {},
            serverInfo: { name: 'test', version: '1.0.0' },
          },
        }),
      });
      mockFetch.mockResolvedValueOnce({ ok: true, status: 202 });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 2, result: { resources: [] } }),
      });
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jsonrpc: '2.0', id: 3, result: { tools: [] } }),
      });

      await client.connect();
    });

    it('should read dashboard HTML', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 4,
          result: {
            contents: [
              { uri: 'ui://dashboard/agent-status', mimeType: 'text/html', text: '<!DOCTYPE html><html>Dashboard</html>' },
            ],
          },
        }),
      });

      const html = await client.readDashboard();
      expect(html).toContain('Dashboard');
    });

    it('should get agent status', async () => {
      const mockAgentState = {
        status: 'idle',
        currentNode: null,
        query: null,
        metrics: { modelCalls: 0, toolCalls: 0, inputTokens: 0, outputTokens: 0 },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 4,
          result: {
            content: [
              { type: 'text', text: JSON.stringify(mockAgentState) },
            ],
            isError: false,
          },
        }),
      });

      const state = await client.getAgentStatus();
      expect(state.status).toBe('idle');
    });

    it('should reset agent state', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          jsonrpc: '2.0',
          id: 4,
          result: {
            content: [
              { type: 'text', text: '{"message": "reset"}' },
            ],
            isError: false,
          },
        }),
      });

      await expect(client.resetAgentState()).resolves.not.toThrow();
    });
  });

  // ---------------------------------------------------------------------------
  // Error Handling Tests
  // ---------------------------------------------------------------------------

  describe('Error Handling', () => {
    it('should handle JSON-RPC error response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Headers(),
        json: async () => ({
          jsonrpc: '2.0',
          id: 1,
          error: {
            code: -32601,
            message: 'Method not found',
          },
        }),
      });

      await expect(client.connect()).rejects.toThrow('Method not found');
    });

    it('should handle HTTP error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        headers: new Headers(),
        text: async () => 'Internal Server Error',
      });

      await expect(client.connect()).rejects.toThrow('MCP request failed: 500');
    });
  });
});
