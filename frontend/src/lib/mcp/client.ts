/**
 * MCP Client for Streamable HTTP Transport
 *
 * Implements MCP (Model Context Protocol) client using Streamable HTTP transport.
 * Connects to backend MCP server at /api/v1/mcp/message endpoint.
 *
 * Specification: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
 */

import { API_BASE_URL } from '../api/client';
import type {
  JsonRpcRequest,
  JsonRpcResponse,
  InitializeParams,
  InitializeResult,
  ResourcesListResult,
  ResourcesReadParams,
  ResourcesReadResult,
  ToolsListResult,
  ToolsCallParams,
  ToolsCallResult,
  MCPClientState,
  MCPConnectionState,
  MCPResource,
  MCPTool,
  AgentState,
} from './types';

// =============================================================================
// Constants
// =============================================================================

const MCP_ENDPOINT = `${API_BASE_URL}/api/v1/mcp/message`;
const PROTOCOL_VERSION = '2025-03-26';
const CLIENT_INFO = {
  name: 'docuchat-frontend',
  version: '1.0.0',
};

// =============================================================================
// MCP Client Class
// =============================================================================

export class MCPClient {
  private sessionId: string | null = null;
  private requestId = 0;
  private state: MCPClientState;
  private stateListeners: Set<(state: MCPClientState) => void> = new Set();

  constructor() {
    this.state = this.getInitialState();
  }

  // ---------------------------------------------------------------------------
  // State Management
  // ---------------------------------------------------------------------------

  private getInitialState(): MCPClientState {
    return {
      connectionState: 'disconnected',
      sessionId: null,
      serverInfo: null,
      capabilities: null,
      resources: [],
      tools: [],
      error: null,
    };
  }

  private setState(updates: Partial<MCPClientState>) {
    this.state = { ...this.state, ...updates };
    this.notifyListeners();
  }

  private setConnectionState(connectionState: MCPConnectionState, error?: string) {
    this.setState({
      connectionState,
      error: error ?? null,
    });
  }

  private notifyListeners() {
    this.stateListeners.forEach((listener) => listener(this.state));
  }

  /**
   * Subscribe to state changes.
   * @param listener Callback function called on state changes.
   * @returns Unsubscribe function.
   */
  subscribe(listener: (state: MCPClientState) => void): () => void {
    this.stateListeners.add(listener);
    // Immediately call with current state
    listener(this.state);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  /**
   * Get current client state.
   */
  getState(): MCPClientState {
    return this.state;
  }

  // ---------------------------------------------------------------------------
  // Low-level Communication
  // ---------------------------------------------------------------------------

  private getNextRequestId(): number {
    return ++this.requestId;
  }

  private async sendRequest<T, P extends object = Record<string, unknown>>(
    method: string,
    params: P = {} as P
  ): Promise<T> {
    const request: JsonRpcRequest = {
      jsonrpc: '2.0',
      id: this.getNextRequestId(),
      method,
      params: params as Record<string, unknown>,
    };

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      Accept: 'application/json, text/event-stream',
    };

    // Include session ID if available (except for initialize)
    if (this.sessionId && method !== 'initialize') {
      headers['Mcp-Session-Id'] = this.sessionId;
    }

    const response = await fetch(MCP_ENDPOINT, {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
    });

    // Check for session ID in response (initialize only)
    if (method === 'initialize') {
      const newSessionId = response.headers.get('Mcp-Session-Id');
      if (newSessionId) {
        this.sessionId = newSessionId;
        this.setState({ sessionId: newSessionId });
      }
    }

    if (!response.ok) {
      const errorText = await response.text();

      // Detect session expiration (404 = session not found)
      // Reset connection state to trigger auto-reconnect
      if (response.status === 404 && errorText.includes('Session not found')) {
        this.sessionId = null;
        this.setConnectionState('error', 'Session expired. Reconnecting...');
      }

      throw new Error(`MCP request failed: ${response.status} ${errorText}`);
    }

    const jsonResponse: JsonRpcResponse = await response.json();

    if (jsonResponse.error) {
      throw new Error(`MCP error: ${jsonResponse.error.message}`);
    }

    return jsonResponse.result as T;
  }

  // ---------------------------------------------------------------------------
  // Connection Management
  // ---------------------------------------------------------------------------

  /**
   * Connect to MCP server and initialize session.
   */
  async connect(): Promise<void> {
    if (this.state.connectionState === 'connected') {
      return;
    }

    this.setConnectionState('connecting');

    try {
      const initParams: InitializeParams = {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: CLIENT_INFO,
      };

      const result = await this.sendRequest<InitializeResult>('initialize', initParams);

      // Send initialized notification
      await this.sendNotification('notifications/initialized');

      // Fetch available resources and tools
      const [resourcesResult, toolsResult] = await Promise.all([
        this.sendRequest<ResourcesListResult>('resources/list'),
        this.sendRequest<ToolsListResult>('tools/list'),
      ]);

      this.setState({
        connectionState: 'connected',
        serverInfo: result.serverInfo,
        capabilities: result.capabilities,
        resources: resourcesResult.resources,
        tools: toolsResult.tools,
        error: null,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Connection failed';
      this.setConnectionState('error', errorMessage);
      throw error;
    }
  }

  /**
   * Disconnect from MCP server.
   */
  async disconnect(): Promise<void> {
    if (!this.sessionId) {
      this.setState(this.getInitialState());
      return;
    }

    try {
      await fetch(MCP_ENDPOINT, {
        method: 'DELETE',
        headers: {
          'Mcp-Session-Id': this.sessionId,
        },
      });
    } catch {
      // Ignore disconnect errors
    }

    this.sessionId = null;
    this.requestId = 0;
    this.setState(this.getInitialState());
  }

  /**
   * Send a notification (no response expected).
   */
  private async sendNotification(method: string, params: Record<string, unknown> = {}): Promise<void> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (this.sessionId) {
      headers['Mcp-Session-Id'] = this.sessionId;
    }

    await fetch(MCP_ENDPOINT, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        jsonrpc: '2.0',
        method,
        params,
      }),
    });
  }

  // ---------------------------------------------------------------------------
  // Resource Operations
  // ---------------------------------------------------------------------------

  /**
   * List available resources.
   */
  async listResources(): Promise<MCPResource[]> {
    this.ensureConnected();
    const result = await this.sendRequest<ResourcesListResult>('resources/list');
    this.setState({ resources: result.resources });
    return result.resources;
  }

  /**
   * Read a resource by URI.
   * @param uri Resource URI (e.g., "ui://dashboard/agent-status")
   */
  async readResource(uri: string): Promise<ResourcesReadResult> {
    this.ensureConnected();
    const params: ResourcesReadParams = { uri };
    return this.sendRequest<ResourcesReadResult>('resources/read', params);
  }

  // ---------------------------------------------------------------------------
  // Tool Operations
  // ---------------------------------------------------------------------------

  /**
   * List available tools.
   */
  async listTools(): Promise<MCPTool[]> {
    this.ensureConnected();
    const result = await this.sendRequest<ToolsListResult>('tools/list');
    this.setState({ tools: result.tools });
    return result.tools;
  }

  /**
   * Call a tool by name.
   * @param name Tool name
   * @param args Tool arguments
   */
  async callTool(name: string, args: Record<string, unknown> = {}): Promise<ToolsCallResult> {
    this.ensureConnected();
    const params: ToolsCallParams = { name, arguments: args };
    return this.sendRequest<ToolsCallResult>('tools/call', params);
  }

  // ---------------------------------------------------------------------------
  // Dashboard-specific Operations
  // ---------------------------------------------------------------------------

  /**
   * Read the agent status dashboard UI.
   * @returns HTML content for the dashboard
   */
  async readDashboard(): Promise<string> {
    const result = await this.readResource('ui://dashboard/agent-status');
    const content = result.contents[0];
    return content?.text ?? '';
  }

  /**
   * Get current agent execution status for a specific channel.
   * @param channelId Channel ID to get status for
   */
  async getAgentStatus(channelId: string): Promise<AgentState> {
    const result = await this.callTool('get_agent_status', { channel_id: channelId });
    const textContent = result.content.find((c) => c.type === 'text');
    if (textContent?.text) {
      return JSON.parse(textContent.text) as AgentState;
    }
    throw new Error('Invalid agent status response');
  }

  /**
   * Run a RAG query.
   * @param channelId Channel ID to search in
   * @param query User query
   */
  async runRagQuery(channelId: string, query: string): Promise<AgentState> {
    const result = await this.callTool('run_rag_query', { channel_id: channelId, query });
    const textContent = result.content.find((c) => c.type === 'text');
    if (textContent?.text) {
      return JSON.parse(textContent.text) as AgentState;
    }
    throw new Error('Invalid RAG query response');
  }

  /**
   * Reset agent state to idle for a specific channel.
   * @param channelId Channel ID to reset (optional, resets all if not specified)
   */
  async resetAgentState(channelId?: string): Promise<void> {
    await this.callTool('reset_agent_state', channelId ? { channel_id: channelId } : {});
  }

  // ---------------------------------------------------------------------------
  // Utilities
  // ---------------------------------------------------------------------------

  private ensureConnected(): void {
    if (this.state.connectionState !== 'connected') {
      throw new Error('MCP client not connected. Call connect() first.');
    }
  }

  /**
   * Check if client is connected.
   */
  isConnected(): boolean {
    return this.state.connectionState === 'connected';
  }
}

// =============================================================================
// Singleton Instance
// =============================================================================

let mcpClientInstance: MCPClient | null = null;

/**
 * Get the singleton MCP client instance.
 */
export function getMCPClient(): MCPClient {
  if (!mcpClientInstance) {
    mcpClientInstance = new MCPClient();
  }
  return mcpClientInstance;
}

/**
 * Create a new MCP client instance (for testing).
 */
export function createMCPClient(): MCPClient {
  return new MCPClient();
}

export default getMCPClient;
