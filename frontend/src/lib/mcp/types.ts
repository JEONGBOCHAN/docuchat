/**
 * MCP (Model Context Protocol) Types
 *
 * Type definitions for MCP Streamable HTTP transport communication.
 * Based on MCP specification 2025-03-26.
 */

// =============================================================================
// JSON-RPC Types
// =============================================================================

export interface JsonRpcRequest {
  jsonrpc: '2.0';
  id: number | string;
  method: string;
  params?: Record<string, unknown>;
}

export interface JsonRpcNotification {
  jsonrpc: '2.0';
  method: string;
  params?: Record<string, unknown>;
}

export interface JsonRpcResponse {
  jsonrpc: '2.0';
  id: number | string;
  result?: unknown;
  error?: JsonRpcError;
}

export interface JsonRpcError {
  code: number;
  message: string;
  data?: unknown;
}

// =============================================================================
// MCP Protocol Types
// =============================================================================

export interface MCPCapabilities {
  resources?: {
    subscribe?: boolean;
    listChanged?: boolean;
  };
  tools?: Record<string, unknown>;
}

export interface MCPServerInfo {
  name: string;
  version: string;
}

export interface MCPClientInfo {
  name: string;
  version: string;
}

// Initialize
export interface InitializeParams {
  protocolVersion: string;
  capabilities: MCPCapabilities;
  clientInfo?: MCPClientInfo;
  [key: string]: unknown;
}

export interface InitializeResult {
  protocolVersion: string;
  capabilities: MCPCapabilities;
  serverInfo: MCPServerInfo;
}

// Resources
export interface MCPResource {
  uri: string;
  name: string;
  description?: string;
  mimeType?: string;
}

export interface ResourcesListResult {
  resources: MCPResource[];
}

export interface ResourceContent {
  uri: string;
  mimeType?: string;
  text?: string;
  blob?: string; // Base64 encoded
}

export interface ResourcesReadParams {
  uri: string;
  [key: string]: unknown;
}

export interface ResourcesReadResult {
  contents: ResourceContent[];
}

// Tools
export interface MCPTool {
  name: string;
  description?: string;
  inputSchema?: {
    type: string;
    properties?: Record<string, unknown>;
    required?: string[];
  };
}

export interface ToolsListResult {
  tools: MCPTool[];
}

export interface ToolContent {
  type: 'text' | 'image' | 'resource';
  text?: string;
  data?: string;
  mimeType?: string;
}

export interface ToolsCallParams {
  name: string;
  arguments?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ToolsCallResult {
  content: ToolContent[];
  isError?: boolean;
}

// =============================================================================
// Client State Types
// =============================================================================

export type MCPConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'error';

export interface MCPClientState {
  connectionState: MCPConnectionState;
  sessionId: string | null;
  serverInfo: MCPServerInfo | null;
  capabilities: MCPCapabilities | null;
  resources: MCPResource[];
  tools: MCPTool[];
  error: string | null;
}

// =============================================================================
// Agent State Types (from dashboard)
// =============================================================================

export interface PipelineNode {
  name: string;
  type: string;
  status: 'pending' | 'active' | 'complete' | 'error';
  startTime?: string;
  endTime?: string;
}

export interface ExecutionStep {
  name: string;
  type: string;
  status: 'pending' | 'active' | 'complete' | 'error';
  startTime?: string;
  endTime?: string;
  data?: {
    type?: string;
    tokens?: number;
    [key: string]: unknown;
  };
}

export interface ExecutionMetrics {
  totalDuration?: number;
  modelCalls: number;
  toolCalls: number;
  inputTokens: number;
  outputTokens: number;
  currentTokens?: number;
}

export interface AgentState {
  status: 'idle' | 'running' | 'complete' | 'error';
  currentNode: string | null;
  query: string | null;
  channelId: string | null;
  response: string | null;
  sources: Array<{
    document_id: string;
    document_name: string;
    chunk_index: number;
    content: string;
    score: number;
  }>;
  error: string | null;
  steps: ExecutionStep[];
  metrics: ExecutionMetrics;
  pipelineNodes: PipelineNode[];
  startTime: string | null;
  endTime: string | null;
  currentTokens?: number;
}
