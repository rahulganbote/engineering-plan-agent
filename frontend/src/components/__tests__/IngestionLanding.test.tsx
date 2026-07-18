import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { IngestionLanding } from '../IngestionLanding';

describe('IngestionLanding', () => {
  const defaultProps = {
    selectedFile: null,
    onFileSelect: vi.fn(),
    onRemoveFile: vi.fn(),
    onTrigger: vi.fn(),
    isLoading: false,
    isAuthenticated: false,
    onLogin: vi.fn(),
  };

  it('renders without throwing', () => {
    render(<IngestionLanding {...defaultProps} />);
    expect(screen.getByText('System Architecture')).toBeInTheDocument();
  });

  it('does not show welcome banner when logged out', () => {
    render(<IngestionLanding {...defaultProps} isAuthenticated={false} />);
    expect(screen.queryByText(/Next Step:/i)).not.toBeInTheDocument();
  });

  it('shows welcome banner when logged in and no file is selected', () => {
    render(<IngestionLanding {...defaultProps} isAuthenticated={true} selectedFile={null} />);
    expect(screen.getByText(/Next Step:/i)).toBeInTheDocument();
    expect(screen.getByText(/Drag & drop a BRD file on the left panel to begin/i)).toBeInTheDocument();
  });

  it('does not show welcome banner when logged in but file is already selected', () => {
    const mockFile = new File(['brd content'], 'FoodHub_BRD.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    render(<IngestionLanding {...defaultProps} isAuthenticated={true} selectedFile={mockFile} />);
    expect(screen.queryByText(/Next Step:/i)).not.toBeInTheDocument();
  });
});
