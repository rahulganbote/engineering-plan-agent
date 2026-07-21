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
    expect(screen.getByText('How It Works')).toBeInTheDocument();
  });


});
