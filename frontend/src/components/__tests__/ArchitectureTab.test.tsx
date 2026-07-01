import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ArchitectureTab } from '../ArchitectureTab';

// MermaidRenderer imports mermaid which is heavy - mock it
vi.mock('../MermaidRenderer', () => ({
  MermaidRenderer: ({ diagramMermaid }: { diagramMermaid?: string | null }) =>
    <div data-testid="mermaid-mock">{diagramMermaid || 'no diagram'}</div>,
}));

describe('ArchitectureTab', () => {
  it('renders an empty-state when architectureData is null', () => {
    render(<ArchitectureTab architectureData={null} />);
  });

  it('renders pattern + components when structured data is provided', () => {
    const arch = {
      pattern: 'Microservices',
      pattern_justification: 'Scale + isolation',
      components: [{ name: 'API Gateway', responsibility: 'Routing', technology: 'AWS API Gateway', interfaces: ['REST'] }],
      nfr_mappings: [],
      data_flow: [],
      deployment_model: 'AWS',
      diagram_mermaid: 'graph LR\nA --> B',
    };
    render(<ArchitectureTab architectureData={arch} />);
    expect(screen.getByText(/Microservices/i)).toBeInTheDocument();
    expect(screen.getByText('API Gateway')).toBeInTheDocument();
  });
});
