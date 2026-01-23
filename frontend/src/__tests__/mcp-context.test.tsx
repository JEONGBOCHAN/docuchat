/**
 * Tests for MCP Context and Provider
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { MCPProvider, useMCP, useMCPOptional } from '@/contexts/MCPContext';
import type { MCPClientState } from '@/lib/mcp';

// Mock the MCP client module
const mockConnect = vi.fn();
const mockDisconnect = vi.fn();
const mockReadResource = vi.fn();
const mockReadDashboard = vi.fn();
const mockCallTool = vi.fn();
const mockGetAgentStatus = vi.fn();
const mockRunRagQuery = vi.fn();
const mockResetAgentState = vi.fn();
const mockSubscribe = vi.fn();

const mockInitialState: MCPClientState = {
  connectionState: 'disconnected',
  sessionId: null,
  serverInfo: null,
  capabilities: null,
  resources: [],
  tools: [],
  error: null,
};

let subscriberCallback: ((state: MCPClientState) => void) | null = null;

vi.mock('@/lib/mcp', () => ({
  getMCPClient: () => ({
    connect: mockConnect,
    disconnect: mockDisconnect,
    readResource: mockReadResource,
    readDashboard: mockReadDashboard,
    callTool: mockCallTool,
    getAgentStatus: mockGetAgentStatus,
    runRagQuery: mockRunRagQuery,
    resetAgentState: mockResetAgentState,
    getState: () => mockInitialState,
    subscribe: (callback: (state: MCPClientState) => void) => {
      subscriberCallback = callback;
      callback(mockInitialState);
      return () => {
        subscriberCallback = null;
      };
    },
  }),
}));

describe('MCPContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    subscriberCallback = null;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ---------------------------------------------------------------------------
  // Provider Tests
  // ---------------------------------------------------------------------------

  describe('MCPProvider', () => {
    it('should render children', () => {
      render(
        <MCPProvider>
          <div data-testid="child">Child</div>
        </MCPProvider>
      );

      expect(screen.getByTestId('child')).toBeInTheDocument();
    });

    it('should provide initial state', () => {
      function TestComponent() {
        const { state, isConnected, isConnecting } = useMCP();
        return (
          <div>
            <span data-testid="state">{state.connectionState}</span>
            <span data-testid="connected">{isConnected.toString()}</span>
            <span data-testid="connecting">{isConnecting.toString()}</span>
          </div>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      expect(screen.getByTestId('state')).toHaveTextContent('disconnected');
      expect(screen.getByTestId('connected')).toHaveTextContent('false');
      expect(screen.getByTestId('connecting')).toHaveTextContent('false');
    });

    it('should auto-connect when autoConnect is true', async () => {
      mockConnect.mockResolvedValueOnce(undefined);

      function TestComponent() {
        const { isConnecting } = useMCP();
        return <div data-testid="connecting">{isConnecting.toString()}</div>;
      }

      render(
        <MCPProvider autoConnect={true}>
          <TestComponent />
        </MCPProvider>
      );

      await waitFor(() => {
        expect(mockConnect).toHaveBeenCalled();
      });
    });

    it('should not auto-connect when autoConnect is false', () => {
      function TestComponent() {
        return <div>Test</div>;
      }

      render(
        <MCPProvider autoConnect={false}>
          <TestComponent />
        </MCPProvider>
      );

      expect(mockConnect).not.toHaveBeenCalled();
    });
  });

  // ---------------------------------------------------------------------------
  // useMCP Hook Tests
  // ---------------------------------------------------------------------------

  describe('useMCP', () => {
    it('should throw when used outside provider', () => {
      function TestComponent() {
        useMCP();
        return null;
      }

      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => render(<TestComponent />)).toThrow(
        'useMCP must be used within an MCPProvider'
      );

      consoleSpy.mockRestore();
    });

    it('should provide connect method', async () => {
      mockConnect.mockResolvedValueOnce(undefined);

      function TestComponent() {
        const { connect } = useMCP();
        return (
          <button onClick={() => connect()} data-testid="connect">
            Connect
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('connect').click();
      });

      expect(mockConnect).toHaveBeenCalled();
    });

    it('should provide disconnect method', async () => {
      mockDisconnect.mockResolvedValueOnce(undefined);

      function TestComponent() {
        const { disconnect } = useMCP();
        return (
          <button onClick={() => disconnect()} data-testid="disconnect">
            Disconnect
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('disconnect').click();
      });

      expect(mockDisconnect).toHaveBeenCalled();
    });

    it('should provide readResource method', async () => {
      mockReadResource.mockResolvedValueOnce({
        contents: [{ uri: 'test://uri', text: 'content' }],
      });

      function TestComponent() {
        const { readResource } = useMCP();
        return (
          <button
            onClick={() => readResource('test://uri')}
            data-testid="read-resource"
          >
            Read
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('read-resource').click();
      });

      expect(mockReadResource).toHaveBeenCalledWith('test://uri');
    });

    it('should provide readDashboard method', async () => {
      mockReadDashboard.mockResolvedValueOnce('<html>Dashboard</html>');

      function TestComponent() {
        const { readDashboard } = useMCP();
        return (
          <button
            onClick={() => readDashboard()}
            data-testid="read-dashboard"
          >
            Read Dashboard
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('read-dashboard').click();
      });

      expect(mockReadDashboard).toHaveBeenCalled();
    });

    it('should provide callTool method', async () => {
      mockCallTool.mockResolvedValueOnce({
        content: [{ type: 'text', text: 'result' }],
        isError: false,
      });

      function TestComponent() {
        const { callTool } = useMCP();
        return (
          <button
            onClick={() => callTool('test_tool', { arg: 'value' })}
            data-testid="call-tool"
          >
            Call Tool
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('call-tool').click();
      });

      expect(mockCallTool).toHaveBeenCalledWith('test_tool', { arg: 'value' });
    });

    it('should provide getAgentStatus method', async () => {
      mockGetAgentStatus.mockResolvedValueOnce({ status: 'idle' });

      function TestComponent() {
        const { getAgentStatus } = useMCP();
        return (
          <button
            onClick={() => getAgentStatus()}
            data-testid="get-status"
          >
            Get Status
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('get-status').click();
      });

      expect(mockGetAgentStatus).toHaveBeenCalled();
    });

    it('should provide runRagQuery method', async () => {
      mockRunRagQuery.mockResolvedValueOnce({ status: 'complete' });

      function TestComponent() {
        const { runRagQuery } = useMCP();
        return (
          <button
            onClick={() => runRagQuery('channel-1', 'test query')}
            data-testid="run-query"
          >
            Run Query
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('run-query').click();
      });

      expect(mockRunRagQuery).toHaveBeenCalledWith('channel-1', 'test query');
    });

    it('should provide resetAgentState method', async () => {
      mockResetAgentState.mockResolvedValueOnce(undefined);

      function TestComponent() {
        const { resetAgentState } = useMCP();
        return (
          <button
            onClick={() => resetAgentState()}
            data-testid="reset"
          >
            Reset
          </button>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      await act(async () => {
        screen.getByTestId('reset').click();
      });

      expect(mockResetAgentState).toHaveBeenCalled();
    });
  });

  // ---------------------------------------------------------------------------
  // useMCPOptional Hook Tests
  // ---------------------------------------------------------------------------

  describe('useMCPOptional', () => {
    it('should return null when used outside provider', () => {
      function TestComponent() {
        const context = useMCPOptional();
        return (
          <div data-testid="result">{context ? 'has context' : 'no context'}</div>
        );
      }

      render(<TestComponent />);

      expect(screen.getByTestId('result')).toHaveTextContent('no context');
    });

    it('should return context when used inside provider', () => {
      function TestComponent() {
        const context = useMCPOptional();
        return (
          <div data-testid="result">{context ? 'has context' : 'no context'}</div>
        );
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      expect(screen.getByTestId('result')).toHaveTextContent('has context');
    });
  });

  // ---------------------------------------------------------------------------
  // State Update Tests
  // ---------------------------------------------------------------------------

  describe('State Updates', () => {
    it('should update state when client state changes', async () => {
      function TestComponent() {
        const { state } = useMCP();
        return <div data-testid="state">{state.connectionState}</div>;
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      expect(screen.getByTestId('state')).toHaveTextContent('disconnected');

      // Simulate state change from client
      await act(async () => {
        if (subscriberCallback) {
          subscriberCallback({
            ...mockInitialState,
            connectionState: 'connected',
          });
        }
      });

      expect(screen.getByTestId('state')).toHaveTextContent('connected');
    });

    it('should provide resources from state', () => {
      function TestComponent() {
        const { resources } = useMCP();
        return <div data-testid="count">{resources.length}</div>;
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      expect(screen.getByTestId('count')).toHaveTextContent('0');
    });

    it('should provide tools from state', () => {
      function TestComponent() {
        const { tools } = useMCP();
        return <div data-testid="count">{tools.length}</div>;
      }

      render(
        <MCPProvider>
          <TestComponent />
        </MCPProvider>
      );

      expect(screen.getByTestId('count')).toHaveTextContent('0');
    });
  });
});
