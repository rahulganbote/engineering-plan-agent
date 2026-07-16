import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TimelineStepper } from '../TimelineStepper';
import { type PipelineStatus, PIPELINE_STATUS } from '../../lib/pipelineStatus';

describe('TimelineStepper (Hub-and-Spoke)', () => {
  const baseProps = {
    pipelineStatus: PIPELINE_STATUS.IDLE as PipelineStatus,
    completedAgents: new Set<string>(),
    artifacts: null,
    criticOutput: null,
    logs: [],
    isCollapsed: false,
    onToggleCollapse: vi.fn(),
  };

  it('renders without throwing', () => {
    render(<TimelineStepper {...baseProps} />);
  });

  it('shows the core agent and specialist node labels', () => {
    render(<TimelineStepper {...baseProps} />);
    
    // Core flow nodes
    expect(screen.getByText('Security')).toBeInTheDocument();
    expect(screen.getByText('Orchestrator')).toBeInTheDocument();
    expect(screen.getByText('Critic Agent')).toBeInTheDocument();
    expect(screen.getByText('EM Decision')).toBeInTheDocument();
    expect(screen.getByText('Export')).toBeInTheDocument();

    // Specialist satellite nodes
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByText('Schedule')).toBeInTheDocument();
    expect(screen.getByText('PoC')).toBeInTheDocument();
    expect(screen.getByText('Tech Stack')).toBeInTheDocument();
    expect(screen.getByText('Architect')).toBeInTheDocument();
  });

  it('reflects collapsed summary mode when isCollapsed is true', () => {
    render(<TimelineStepper {...baseProps} isCollapsed={true} pipelineStatus={PIPELINE_STATUS.AWAITING_HITL} />);
    expect(screen.getByText(/Awaiting Engineering Manager Decision/i)).toBeInTheDocument();
    expect(screen.queryByText('Security')).not.toBeInTheDocument(); // should hide the full map diagram
  });
});
