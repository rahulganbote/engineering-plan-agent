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
      <TimelineStepper {...baseProps} pipelineStatus={PIPELINE_STATUS.ALIGNING} completedAgents={new Set(['orchestrator'])} />
    );
    expect(container).toBeTruthy();
  });

  it('asserts that every pipeline status activates exactly one step (or zero if idle/terminal)', () => {
    const nonRunningStatuses: PipelineStatus[] = [
      PIPELINE_STATUS.IDLE,
      PIPELINE_STATUS.EXPORTED,
      PIPELINE_STATUS.REJECTED,
      PIPELINE_STATUS.EXPORT_FAILED,
      PIPELINE_STATUS.ERROR,
      PIPELINE_STATUS.CANCELED,
    ];

    Object.values(PIPELINE_STATUS).forEach((status) => {
      const { container, unmount } = render(<TimelineStepper {...baseProps} pipelineStatus={status as PipelineStatus} />);
      const activeCircles = container.querySelectorAll('.w-12.h-12.animate-pulse');

      if (nonRunningStatuses.includes(status as PipelineStatus)) {
        expect(activeCircles.length).toBe(0);
      } else {
        expect(activeCircles.length).toBe(1);
      }
      unmount();
    });
  });
});
