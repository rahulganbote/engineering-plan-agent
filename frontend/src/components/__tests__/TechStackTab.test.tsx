import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TechStackTab } from '../TechStackTab';

describe('TechStackTab', () => {
  it('renders empty-state when techStackData is null', () => {
    render(<TechStackTab techStackData={null} />);
  });

  it('renders recommended option', () => {
    const stack = {
      options: [{
        name: 'FastAPI + PostgreSQL',
        scalability: 4,
        familiarity: 5,
        integration_risk: 'low',
        monthly_cost_usd: 2000,
        pros: ['High perf'],
        cons: ['Newer'],
      }],
      recommended_option: 'FastAPI + PostgreSQL',
      recommendation_rationale: 'Team familiarity + fit',
    };
    render(<TechStackTab techStackData={stack} />);
    expect(screen.getByText(/FastAPI \+ PostgreSQL/i)).toBeInTheDocument();
  });
});
