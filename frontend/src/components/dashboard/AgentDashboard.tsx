'use client';

/**
 * AgentDashboard Component
 *
 * Renders the MCP UI resource for agent status visualization.
 * Connects to MCP server and displays real-time agent execution state.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { useMCP } from '@/contexts/MCPContext';
import type { AgentState } from '@/lib/mcp';

// =============================================================================
// Types
// =============================================================================

export interface AgentDashboardProps {
  /**
   * Polling interval in ms for status updates. Default: 2000
   */
  pollingInterval?: number;
  /**
   * Whether to render HTML in iframe (safer) or inline. Default: 'iframe'
   */
  renderMode?: 'iframe' | 'inline';
  /**
   * CSS class name for the container
   */
  className?: string;
  /**
   * Callback when agent state changes
   */
  onStateChange?: (state: AgentState) => void;
}

// =============================================================================
// Component
// =============================================================================

export function AgentDashboard({
  pollingInterval = 2000,
  renderMode = 'iframe',
  className = '',
  onStateChange,
}: AgentDashboardProps) {
  const {
    isConnected,
    isConnecting,
    error: mcpError,
    connect,
    readDashboard,
    getAgentStatus,
  } = useMCP();

  const [dashboardHtml, setDashboardHtml] = useState<string>('');
  const [agentState, setAgentState] = useState<AgentState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // ---------------------------------------------------------------------------
  // Connect to MCP
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!isConnected && !isConnecting && !mcpError) {
      connect().catch((err) => {
        console.error('Failed to connect to MCP:', err);
        setError('Failed to connect to MCP server');
      });
    }
  }, [isConnected, isConnecting, mcpError, connect]);

  // ---------------------------------------------------------------------------
  // Load Dashboard HTML
  // ---------------------------------------------------------------------------

  const loadDashboard = useCallback(async () => {
    if (!isConnected) return;

    try {
      setIsLoading(true);
      setError(null);

      const html = await readDashboard();
      setDashboardHtml(html);

      // Also get initial agent state
      const state = await getAgentStatus();
      setAgentState(state);
      onStateChange?.(state);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setIsLoading(false);
    }
  }, [isConnected, readDashboard, getAgentStatus, onStateChange]);

  useEffect(() => {
    if (isConnected) {
      loadDashboard();
    }
  }, [isConnected, loadDashboard]);

  // ---------------------------------------------------------------------------
  // Poll for Agent Status Updates
  // ---------------------------------------------------------------------------

  const pollStatus = useCallback(async () => {
    if (!isConnected) return;

    try {
      const state = await getAgentStatus();
      setAgentState(state);
      onStateChange?.(state);

      // If agent is running, reload dashboard to get updated HTML
      if (state.status === 'running') {
        const html = await readDashboard();
        setDashboardHtml(html);
      }
    } catch (err) {
      console.error('Failed to poll agent status:', err);
    }
  }, [isConnected, getAgentStatus, readDashboard, onStateChange]);

  useEffect(() => {
    if (isConnected && pollingInterval > 0) {
      pollingRef.current = setInterval(pollStatus, pollingInterval);
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [isConnected, pollingInterval, pollStatus]);

  // ---------------------------------------------------------------------------
  // Send State Updates to iframe
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (renderMode === 'iframe' && iframeRef.current && agentState) {
      try {
        iframeRef.current.contentWindow?.postMessage(
          { type: 'STATE_UPDATE', state: agentState },
          '*'
        );
      } catch {
        // Ignore postMessage errors
      }
    }
  }, [renderMode, agentState]);

  // ---------------------------------------------------------------------------
  // Render: Connection State
  // ---------------------------------------------------------------------------

  if (isConnecting) {
    return (
      <div className={`flex items-center justify-center h-full bg-gray-50 dark:bg-gray-900 ${className}`}>
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="text-sm text-gray-500 dark:text-gray-400">Connecting to MCP server...</p>
        </div>
      </div>
    );
  }

  if (mcpError || error) {
    return (
      <div className={`flex items-center justify-center h-full bg-gray-50 dark:bg-gray-900 ${className}`}>
        <div className="flex flex-col items-center gap-3 max-w-sm text-center">
          <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
            <svg className="w-6 h-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-300">{mcpError || error}</p>
          <button
            onClick={() => {
              setError(null);
              connect().catch(console.error);
            }}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className={`flex items-center justify-center h-full bg-gray-50 dark:bg-gray-900 ${className}`}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
            </svg>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Not connected to MCP server</p>
          <button
            onClick={() => connect().catch(console.error)}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Connect
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Loading
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center h-full bg-gray-50 dark:bg-gray-900 ${className}`}>
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render: Dashboard Content
  // ---------------------------------------------------------------------------

  if (renderMode === 'iframe') {
    return (
      <div className={`h-full bg-white dark:bg-gray-900 ${className}`}>
        <iframe
          ref={iframeRef}
          srcDoc={dashboardHtml}
          className="w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin"
          title="Agent Dashboard"
        />
      </div>
    );
  }

  // Inline render mode (less secure, but works with dark mode)
  return (
    <div
      className={`h-full overflow-auto bg-white dark:bg-gray-900 ${className}`}
      dangerouslySetInnerHTML={{ __html: dashboardHtml }}
    />
  );
}

// =============================================================================
// Compact Status Badge (for use outside dashboard)
// =============================================================================

export interface AgentStatusBadgeProps {
  className?: string;
}

export function AgentStatusBadge({ className = '' }: AgentStatusBadgeProps) {
  const { isConnected, isConnecting, error, connect, getAgentStatus } = useMCP();
  const [status, setStatus] = useState<AgentState['status'] | null>(null);

  useEffect(() => {
    if (!isConnected && !isConnecting && !error) {
      connect().catch(console.error);
    }
  }, [isConnected, isConnecting, error, connect]);

  useEffect(() => {
    if (!isConnected) return;

    const fetchStatus = async () => {
      try {
        const state = await getAgentStatus();
        setStatus(state.status);
      } catch {
        // Ignore errors
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [isConnected, getAgentStatus]);

  const getStatusColor = () => {
    switch (status) {
      case 'idle':
        return 'bg-gray-400';
      case 'running':
        return 'bg-green-500 animate-pulse';
      case 'complete':
        return 'bg-blue-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-300';
    }
  };

  const getStatusText = () => {
    if (isConnecting) return 'Connecting...';
    if (error) return 'Error';
    if (!isConnected) return 'Disconnected';
    switch (status) {
      case 'idle':
        return 'Idle';
      case 'running':
        return 'Running';
      case 'complete':
        return 'Complete';
      case 'error':
        return 'Error';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
      <span className="text-xs text-gray-600 dark:text-gray-400">{getStatusText()}</span>
    </div>
  );
}

export default AgentDashboard;
