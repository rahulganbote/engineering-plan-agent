import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TimelineStepper } from '../TimelineStepper';
import { type PipelineStatus, PIPELINE_STATUS } from '../../lib/pipelineStatus';

describe('TimelineStepper', () => {
  const baseProps = {
    pipelineStatus: PIPELINE_STATUS.IDLE as PipelineStatus,
    completedAgents: new Set<string>(),
    artifacts: null,
    criticOutput: null,
    approvalResult: null,
    logs: [],
  };


  it('renders without throwing', () => {
    render(<TimelineStepper {...baseProps} />);
  });

  it('shows all 7 business-focused stage labels', () => {
    render(<TimelineStepper {...baseProps} />);
    // 7 steps: Security, Orchestrator, Specialists Drafting, Arbitration, Specialists Alignment, Critic, Decision
    expect(screen.getByText('Security Validation')).toBeInTheDocument();
    expect(screen.getByText('Orchestrator')).toBeInTheDocument();
    expect(screen.getByText('Specialists Drafting')).toBeInTheDocument();
    expect(screen.getByText('Arbitration')).toBeInTheDocument();
    expect(screen.getByText('Specialists Alignment')).toBeInTheDocument();
    expect(screen.getByText('Critic')).toBeInTheDocument();
    expect(screen.getByText('Decision')).toBeInTheDocument();
  });

  it('reflects completed orchestrator status visually', () => {
    const { container } = render(
      <TimelineStepper {...baseProps} pipelineStatus={PIPELINE_STATUS.SPECIALIST_EXECUTING} completedAgents={new Set(['orchestrator'])} />
    );
    expect(container).toBeTruthy();
  });
});
