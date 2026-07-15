import { render, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AgentWorkspace } from '../AgentWorkspace';

// Dynamic mock variables we can update within tests
let mockPipelineStatus = 'running';
let mockFallbackActive: { from: string; to: string } | null = null;
let mockRunId: string | null = 'test-run-123';

// Mock WorkspaceContext
vi.mock('../../context/WorkspaceContext', () => ({
  useWorkspace: () => ({
    runId: mockRunId,
    setRunId: vi.fn(),
    apiBaseUrl: 'http://localhost:8000',
    setApiBaseUrl: vi.fn(),
    logs: [],
    pipelineStatus: mockPipelineStatus,
    completedAgents: new Set(),
    artifacts: null,
    elapsedSeconds: 10,
    tokenUsage: null,
    costUsd: null,
    criticOutput: null,
    approvalResult: null,
    clearRun: vi.fn(),
    fetchArtifacts: vi.fn().mockResolvedValue(undefined),
    setPipelineStatus: vi.fn(),
    setApprovalResult: vi.fn(),
    errorMessage: null,
    longRunningWarning: null,
    fallbackActive: mockFallbackActive,
    elevenlabsAgentId: '',
  }),
}));

// Mock AuthContext
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'manager@example.com', name: 'Test Manager' },
    isAuthenticated: true,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

// Mock useTheme hook
vi.mock('../../hooks/useTheme', () => ({
  useTheme: () => ({
    theme: 'dark',
    setTheme: vi.fn(),
  }),
}));

// Mock sonner
const mockToastWarning = vi.fn();
vi.mock('sonner', () => ({
  toast: {
    warning: (...args: any[]) => mockToastWarning(...args),
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  },
}));

describe('AgentWorkspace fallback toast warning scenario', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPipelineStatus = 'running';
    mockFallbackActive = null;
    mockRunId = 'test-run-123';

    // Mock global fetch for relative API endpoint loading inside component
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      if (url.includes('/api/providers')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ openai: { available: true } }),
        } as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      } as Response);
    });
  });

  it('triggers warning toast once during execution fallback, and is suppressed after HITL decision', () => {
    // 1. Initial render - no fallback active, toast should not be called
    let view: any;
    act(() => {
      view = render(<AgentWorkspace />);
    });
    expect(mockToastWarning).not.toHaveBeenCalled();

    // 2. Simulate fallback occurrence (transitioning fallbackActive state)
    mockFallbackActive = { from: 'anthropic', to: 'openai' };
    act(() => {
      view.rerender(<AgentWorkspace />);
    });
    expect(mockToastWarning).toHaveBeenCalledTimes(1);
    expect(mockToastWarning).toHaveBeenCalledWith(
      'Anthropic quota exceeded - using Openai for this run.',
      expect.any(Object)
    );

    // Reset calls to count subsequent triggers
    mockToastWarning.mockClear();

    // 3. Trigger updates with same run/fallback state - should NOT call toast again (deduplication)
    act(() => {
      view.rerender(<AgentWorkspace />);
    });
    expect(mockToastWarning).not.toHaveBeenCalled();

    // 4. Simulate transition to "rejected" state (HITL decision made)
    mockPipelineStatus = 'rejected';
    act(() => {
      view.rerender(<AgentWorkspace />);
    });
    expect(mockToastWarning).not.toHaveBeenCalled();
  });
});
