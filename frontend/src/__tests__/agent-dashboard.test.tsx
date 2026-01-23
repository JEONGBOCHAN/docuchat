/**
 * Tests for AgentDashboard Component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AgentDashboard, AgentStatusBadge } from '@/components/dashboard';
import type { MCPContextValue } from '@/contexts/MCPContext';

// Mock the MCP context
const mockConnect = vi.fn();
const mockDisconnect = vi.fn();
const mockReadDashboard = vi.fn();
const mockGetAgentStatus = vi.fn();

const createMockContext = (overrides: Partial<MCPContextValue> = {}): MCPContextValue => ({
  state: {
    connectionState: 'connected',
    sessionId: 'test-session',
    serverInfo: { name: 'test', version: '1.0.0' },
    capabilities: null,
    resources: [],
    tools: [],
    error: null,
  },
  isConnected: true,
  isConnecting: false,
  error: null,
  connect: mockConnect,
  disconnect: mockDisconnect,
  resources: [],
  readResource: vi.fn(),
  readDashboard: mockReadDashboard,
  tools: [],
  callTool: vi.fn(),
  getAgentStatus: mockGetAgentStatus,
  runRagQuery: vi.fn(),
  resetAgentState: vi.fn(),
  ...overrides,
});

// Mock useMCP hook
vi.mock('@/contexts/MCPContext', () => ({
  useMCP: () => createMockContext(),
}));

describe('AgentDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    mockReadDashboard.mockResolvedValue('<!DOCTYPE html><html><body>Dashboard</body></html>');
    mockGetAgentStatus.mockResolvedValue({
      status: 'idle',
      currentNode: null,
      query: null,
      channelId: null,
      response: null,
      sources: [],
      error: null,
      steps: [],
      metrics: { modelCalls: 0, toolCalls: 0, inputTokens: 0, outputTokens: 0 },
      pipelineNodes: [],
      startTime: null,
      endTime: null,
    });
    mockConnect.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ---------------------------------------------------------------------------
  // Basic Rendering Tests
  // ---------------------------------------------------------------------------

  describe('Basic Rendering', () => {
    it('should render iframe with dashboard HTML', async () => {
      render(<AgentDashboard />);

      await waitFor(() => {
        const iframe = document.querySelector('iframe');
        expect(iframe).toBeInTheDocument();
        expect(iframe).toHaveAttribute('title', 'Agent Dashboard');
      });
    });

    it('should load dashboard on mount', async () => {
      render(<AgentDashboard />);

      await waitFor(() => {
        expect(mockReadDashboard).toHaveBeenCalled();
        expect(mockGetAgentStatus).toHaveBeenCalled();
      });
    });

    it('should render with custom className', async () => {
      const { container } = render(<AgentDashboard className="custom-class" />);

      await waitFor(() => {
        const element = container.firstChild as HTMLElement;
        expect(element.className).toContain('custom-class');
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Render Mode Tests
  // ---------------------------------------------------------------------------

  describe('Render Modes', () => {
    it('should render iframe in iframe mode', async () => {
      render(<AgentDashboard renderMode="iframe" />);

      await waitFor(() => {
        const iframe = document.querySelector('iframe');
        expect(iframe).toBeInTheDocument();
        expect(iframe).toHaveAttribute('sandbox', 'allow-scripts allow-same-origin');
      });
    });

    it('should render inline HTML in inline mode', async () => {
      render(<AgentDashboard renderMode="inline" />);

      await waitFor(() => {
        const iframe = document.querySelector('iframe');
        expect(iframe).not.toBeInTheDocument();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // State Change Callback Tests
  // ---------------------------------------------------------------------------

  describe('State Change Callback', () => {
    it('should call onStateChange when state changes', async () => {
      const onStateChange = vi.fn();

      render(<AgentDashboard onStateChange={onStateChange} />);

      await waitFor(() => {
        expect(onStateChange).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'idle' })
        );
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Polling Tests
  // ---------------------------------------------------------------------------

  describe('Polling', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should poll for status updates', async () => {
      render(<AgentDashboard pollingInterval={1000} />);

      // Wait for initial load
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      expect(mockGetAgentStatus).toHaveBeenCalledTimes(1);

      // Advance time to trigger polling
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });

      expect(mockGetAgentStatus).toHaveBeenCalledTimes(2);
    });

    it('should reload dashboard when agent is running', async () => {
      mockGetAgentStatus.mockResolvedValue({ status: 'running' });

      render(<AgentDashboard pollingInterval={1000} />);

      // Wait for initial load
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // First call for initial load
      expect(mockReadDashboard).toHaveBeenCalledTimes(1);

      // Advance time to trigger polling
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });

      // Should reload dashboard since agent is running
      expect(mockReadDashboard).toHaveBeenCalledTimes(2);
    });

    it('should stop polling on unmount', async () => {
      const { unmount } = render(<AgentDashboard pollingInterval={1000} />);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      const initialCalls = mockGetAgentStatus.mock.calls.length;

      unmount();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });

      // Should not have made more calls after unmount
      expect(mockGetAgentStatus).toHaveBeenCalledTimes(initialCalls);
    });
  });
});

describe('AgentStatusBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConnect.mockResolvedValue(undefined);
    mockGetAgentStatus.mockResolvedValue({ status: 'idle' });
  });

  it('should render status badge', async () => {
    render(<AgentStatusBadge />);

    await waitFor(() => {
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });
  });

  it('should show running status', async () => {
    mockGetAgentStatus.mockResolvedValue({ status: 'running' });

    render(<AgentStatusBadge />);

    await waitFor(() => {
      expect(screen.getByText('Running')).toBeInTheDocument();
    });
  });

  it('should show complete status', async () => {
    mockGetAgentStatus.mockResolvedValue({ status: 'complete' });

    render(<AgentStatusBadge />);

    await waitFor(() => {
      expect(screen.getByText('Complete')).toBeInTheDocument();
    });
  });

  it('should show error status', async () => {
    mockGetAgentStatus.mockResolvedValue({ status: 'error' });

    render(<AgentStatusBadge />);

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument();
    });
  });
});
