import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { HITLApprovalGate } from '../HITLApprovalGate';

// Mock WorkspaceContext
vi.mock('../../context/WorkspaceContext', () => ({
  useWorkspace: () => ({
    apiBaseUrl: 'http://localhost:8000',
  }),
}));

// Mock AuthContext
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { email: 'manager@example.com', name: 'Test Manager' },
    isAuthenticated: true,
  }),
}));

// Mock sonner — toast triggers shouldn't blow up tests
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  },
}));

beforeEach(() => {
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ decision: 'approved' }) } as Response)
  );
});

describe('HITLApprovalGate', () => {
  it('renders without throwing', () => {
    render(<HITLApprovalGate runId="test-run" />);
  });

  it('shows Approve and Reject buttons', () => {
    render(<HITLApprovalGate runId="test-run" />);
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument();
  });

  it('rejects empty rejection (triggers toast.error)', async () => {
    const { toast } = await import('sonner');
    render(<HITLApprovalGate runId="test-run" />);
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    // expect error toast for missing notes
    expect(toast.error).toHaveBeenCalled();
  });
});
