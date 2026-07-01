import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TechStackTab } from '../TechStackTab';

// Mock WorkspaceContext
vi.mock('../../context/WorkspaceContext', () => ({
  useWorkspace: () => ({
    logs: [],
  }),
}));

describe('TechStackTab', () => {
  it('renders empty-state when techStackData is null', () => {
    render(<TechStackTab techStackData={null} />);
  });

  it('renders recommended option', () => {
    const stack = {
      options: [{
        name: 'FastAPI + PostgreSQL',
        components: { backend: 'FastAPI', database: 'PostgreSQL' },
        scalability_rating: 4,
        team_familiarity_rating: 5,
        integration_risk: 'low',
        estimated_monthly_cost_usd: 2000,
        pros: ['High perf'],
        cons: ['Newer'],
        citation: 'ref1',
      }],
      recommended_option: 'FastAPI + PostgreSQL',
      recommendation_rationale: 'Team familiarity + fit',
    };
    render(<TechStackTab techStackData={stack} />);
    expect(screen.getAllByText(/FastAPI \+ PostgreSQL/i).length).toBeGreaterThan(0);
  });
});
