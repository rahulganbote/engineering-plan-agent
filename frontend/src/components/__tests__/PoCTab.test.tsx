import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PoCTab } from '../PoCTab';

describe('PoCTab', () => {
  it('renders empty-state when pocData is null', () => {
    render(<PoCTab pocData={null} />);
  });

  it('renders hypothesis + success criteria when given PoC data', () => {
    const poc = {
      poc_hypothesis: 'Latency under 2s for 95% of payment transactions',
      scope_in: ['Payment processing'],
      scope_out: ['MFA'],
      success_criteria: [{ metric: 'Latency', target: '<2s', measurement: 'p95' }],
      duration_weeks: 4,
      team_size: 5,
      risk_if_fails: 'User satisfaction drops',
      confidence_score: 0.7,
    };
    render(<PoCTab pocData={poc} />);
    expect(screen.getByText(/Latency under 2s/i)).toBeInTheDocument();
  });
});
