'use client';

/**
 * MCP Context Provider
 *
 * Provides MCP (Model Context Protocol) client state and methods to React components.
 * Handles connection lifecycle, auto-reconnection, and state management.
 */

import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useState,
  useRef,
  type ReactNode,
} from 'react';
import {
  getMCPClient,
  type MCPClient,
  type MCPClientState,
  type MCPResource,
  type MCPTool,
  type AgentState,
  type ResourcesReadResult,
  type ToolsCallResult,
} from '@/lib/mcp';

// =============================================================================
// Types
// =============================================================================

export interface MCPContextValue {
  // State
  state: MCPClientState;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;

  // Connection
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;

  // Resources
  resources: MCPResource[];
  readResource: (uri: string) => Promise<ResourcesReadResult>;
  readDashboard: () => Promise<string>;

  // Tools
  tools: MCPTool[];
  callTool: (name: string, args?: Record<string, unknown>) => Promise<ToolsCallResult>;

  // Dashboard-specific (channel-scoped)
  getAgentStatus: (channelId: string) => Promise<AgentState>;
  runRagQuery: (channelId: string, query: string) => Promise<AgentState>;
  resetAgentState: (channelId?: string) => Promise<void>;
}

// =============================================================================
// Context
// =============================================================================

const MCPContext = createContext<MCPContextValue | null>(null);

// =============================================================================
// Provider Props
// =============================================================================

export interface MCPProviderProps {
  children: ReactNode;
  /**
   * Auto-connect on mount. Default: false
   */
  autoConnect?: boolean;
  /**
   * Auto-reconnect on disconnect. Default: true
   */
  autoReconnect?: boolean;
  /**
   * Reconnect delay in ms. Default: 3000
   */
  reconnectDelay?: number;
  /**
   * Max reconnect attempts. Default: 5
   */
  maxReconnectAttempts?: number;
}

// =============================================================================
// Provider Component
// =============================================================================

export function MCPProvider({
  children,
  autoConnect = false,
  autoReconnect = true,
  reconnectDelay = 3000,
  maxReconnectAttempts = 5,
}: MCPProviderProps) {
  const clientRef = useRef<MCPClient | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [state, setState] = useState<MCPClientState>(() => {
    const client = getMCPClient();
    clientRef.current = client;
    return client.getState();
  });

  // Subscribe to client state changes
  useEffect(() => {
    const client = clientRef.current;
    if (!client) return;

    const unsubscribe = client.subscribe((newState) => {
      setState(newState);
    });

    return unsubscribe;
  }, []);

  // Clear reconnect timeout on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Connection Methods
  // ---------------------------------------------------------------------------

  const connect = useCallback(async () => {
    const client = clientRef.current;
    if (!client) return;

    try {
      await client.connect();
      reconnectAttemptsRef.current = 0;
    } catch (error) {
      console.error('MCP connection failed:', error);
      throw error;
    }
  }, []);

  const disconnect = useCallback(async () => {
    const client = clientRef.current;
    if (!client) return;

    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    await client.disconnect();
    reconnectAttemptsRef.current = 0;
  }, []);

  // Auto-reconnect logic
  const attemptReconnect = useCallback(() => {
    if (!autoReconnect) return;
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      console.warn('Max MCP reconnect attempts reached');
      return;
    }

    reconnectAttemptsRef.current += 1;
    console.log(`MCP reconnect attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts}`);

    reconnectTimeoutRef.current = setTimeout(async () => {
      try {
        await connect();
      } catch {
        attemptReconnect();
      }
    }, reconnectDelay);
  }, [autoReconnect, maxReconnectAttempts, reconnectDelay, connect]);

  // Watch for disconnections and attempt reconnect
  useEffect(() => {
    if (state.connectionState === 'error' && autoReconnect) {
      attemptReconnect();
    }
  }, [state.connectionState, autoReconnect, attemptReconnect]);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect().catch(console.error);
    }
  }, [autoConnect, connect]);

  // ---------------------------------------------------------------------------
  // Resource Methods
  // ---------------------------------------------------------------------------

  const readResource = useCallback(async (uri: string): Promise<ResourcesReadResult> => {
    const client = clientRef.current;
    if (!client) throw new Error('MCP client not initialized');
    return client.readResource(uri);
  }, []);

  const readDashboard = useCallback(async (): Promise<string> => {
    const client = clientRef.current;
    if (!client) throw new Error('MCP client not initialized');
    return client.readDashboard();
  }, []);

  // ---------------------------------------------------------------------------
  // Tool Methods
  // ---------------------------------------------------------------------------

  const callTool = useCallback(
    async (name: string, args?: Record<string, unknown>): Promise<ToolsCallResult> => {
      const client = clientRef.current;
      if (!client) throw new Error('MCP client not initialized');
      return client.callTool(name, args);
    },
    []
  );

  const getAgentStatus = useCallback(async (channelId: string): Promise<AgentState> => {
    const client = clientRef.current;
    if (!client) throw new Error('MCP client not initialized');
    return client.getAgentStatus(channelId);
  }, []);

  const runRagQuery = useCallback(
    async (channelId: string, query: string): Promise<AgentState> => {
      const client = clientRef.current;
      if (!client) throw new Error('MCP client not initialized');
      return client.runRagQuery(channelId, query);
    },
    []
  );

  const resetAgentState = useCallback(async (channelId?: string): Promise<void> => {
    const client = clientRef.current;
    if (!client) throw new Error('MCP client not initialized');
    return client.resetAgentState(channelId);
  }, []);

  // ---------------------------------------------------------------------------
  // Context Value
  // ---------------------------------------------------------------------------

  const value: MCPContextValue = {
    // State
    state,
    isConnected: state.connectionState === 'connected',
    isConnecting: state.connectionState === 'connecting',
    error: state.error,

    // Connection
    connect,
    disconnect,

    // Resources
    resources: state.resources,
    readResource,
    readDashboard,

    // Tools
    tools: state.tools,
    callTool,

    // Dashboard-specific
    getAgentStatus,
    runRagQuery,
    resetAgentState,
  };

  return <MCPContext.Provider value={value}>{children}</MCPContext.Provider>;
}

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook to access MCP client functionality.
 *
 * Must be used within an MCPProvider.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { connect, isConnected, getAgentStatus } = useMCP();
 *
 *   useEffect(() => {
 *     if (!isConnected) {
 *       connect();
 *     }
 *   }, [isConnected, connect]);
 *
 *   return <div>{isConnected ? 'Connected' : 'Disconnected'}</div>;
 * }
 * ```
 */
export function useMCP(): MCPContextValue {
  const context = useContext(MCPContext);
  if (!context) {
    throw new Error('useMCP must be used within an MCPProvider');
  }
  return context;
}

// =============================================================================
// Optional Hook (for components that may be outside provider)
// =============================================================================

/**
 * Hook to access MCP client functionality, returns null if outside provider.
 *
 * Useful for components that may or may not be wrapped in MCPProvider.
 */
export function useMCPOptional(): MCPContextValue | null {
  return useContext(MCPContext);
}

export default MCPProvider;
