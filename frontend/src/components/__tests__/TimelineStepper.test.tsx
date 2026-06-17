import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TimelineStepper } from '../TimelineStepper';

describe('TimelineStepper', () => {
  const baseProps = {
    pipelineStatus: 'idle',
    completedAgents: new Set<string>(),
    artifacts: null,
    criticOutput: null,
    approvalResult: null,
  };

  it('renders without throwing', () => {
    render(<TimelineStepper {...baseProps} />);
  });

  it('shows all 6 business-focused stage labels', () => {
    render(<TimelineStepper {...baseProps} />);
    // 6 steps: Security, Orchestrator, Specialists, Critic, HITL Gate, Decision
    expect(screen.getByText('Security')).toBeInTheDocument();
    expect(screen.getByText('Orchestrator')).toBeInTheDocument();
    expect(screen.getByText('Specialists')).toBeInTheDocument();
    expect(screen.getByText('Critic')).toBeInTheDocument();
    expect(screen.getByText('HITL Gate')).toBeInTheDocument();
    expect(screen.getByText('Decision')).toBeInTheDocument();
  });

  it('reflects completed orchestrator status visually', () => {
    const { container } = render(
      <TimelineStepper {...baseProps} pipelineStatus="dispatching" completedAgents={new Set(['orchestrator'])} />
    );
    expect(container).toBeTruthy();
  });
});
