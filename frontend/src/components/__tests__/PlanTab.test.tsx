import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PlanTab } from '../PlanTab';

describe('PlanTab', () => {
  it('renders an empty-state when planData is null', () => {
    render(<PlanTab planData={null} />);
  });

  it('renders phases when given structured plan data', () => {
    const planData = {
      phases: [{ name: 'Discovery', duration_weeks: 2, objectives: ['Define scope'] }],
      risks: [],
      milestones: [],
      team_composition: ['EM', 'Tech Lead'],
      confidence_score: 0.85,
    };
    render(<PlanTab planData={planData} />);
    expect(screen.getByText(/Discovery/i)).toBeInTheDocument();
  });
});
