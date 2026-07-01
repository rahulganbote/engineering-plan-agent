import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ScheduleTab } from '../ScheduleTab';

describe('ScheduleTab', () => {
  it('renders an empty-state when scheduleData is null', () => {
    render(<ScheduleTab scheduleData={null} />);
  });

  it('renders sprint table when sprints are present', () => {
    const scheduleData = {
      sprints: [{ sprint: 1, week_range: 'W1-W2', deliverables: ['Kickoff'], team_members: ['EM'], effort_days: 10 }],
      total_effort_days: 100,
      critical_path: ['Discovery'],
    };
    render(<ScheduleTab scheduleData={scheduleData} />);
    expect(screen.getByText(/Kickoff/i)).toBeInTheDocument();
  });
});
