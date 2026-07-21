import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { LogConsole } from '../LogConsole';

describe('LogConsole', () => {
  it('renders without throwing when logs are empty', () => {
    render(<LogConsole logs={[]} />);
  });

  it('shows the header / title row', () => {
    render(<LogConsole logs={[]} />);
    // Title text varies; just assert the Console heading appears
    const headings = screen.getAllByText(/console|log/i);
    expect(headings.length).toBeGreaterThan(0);
  });

  it('renders a log line with agent_start formatting', () => {
    const logs = [{ type: 'agent_start', agent: 'plan_generator', timestamp: 'now' }];
    render(<LogConsole logs={logs} />);
    expect(screen.getByText(/plan_generator/i)).toBeInTheDocument();
  });

  it('renders pipeline_complete log with final status', () => {
    const logs = [{ type: 'pipeline_complete', status: 'awaiting_hitl', timestamp: 'now' }];
    render(<LogConsole logs={logs} />);
    expect(screen.getByText(/Run completed/i)).toBeInTheDocument();
  });

  it('collapses and expands log container when header is clicked', () => {
    const logs = [{ type: 'agent_start', agent: 'plan_generator', timestamp: 'now' }];
    render(<LogConsole logs={logs} />);
    
    expect(screen.getByText(/plan_generator/i)).toBeInTheDocument();

    const header = screen.getByText(/Live Pipeline Engine Console/i);
    act(() => {
      fireEvent.click(header);
    });
    
    expect(screen.queryByText(/plan_generator/i)).not.toBeInTheDocument();

    act(() => {
      fireEvent.click(header);
    });
    expect(screen.getByText(/plan_generator/i)).toBeInTheDocument();
  });

  it('auto-collapses when pipelineStatus transitions to awaiting_hitl', () => {
    const logs = [{ type: 'agent_start', agent: 'plan_generator', timestamp: 'now' }];
    const { rerender } = render(<LogConsole logs={logs} pipelineStatus="running" />);
    
    expect(screen.getByText(/plan_generator/i)).toBeInTheDocument();

    rerender(<LogConsole logs={logs} pipelineStatus="awaiting_hitl" />);
    expect(screen.queryByText(/plan_generator/i)).not.toBeInTheDocument();
  });
});
