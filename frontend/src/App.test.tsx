import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import App from './App';

/**
 * Sprint 1 & 2 tests.
 * Validates the workspaces layout, sandbox toggle, and control elements.
 */
describe('App (Sprint 1 workspace and sandbox)', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            authenticated: true,
            email: 'sairam1908@gmail.com',
            name: 'Sairam Ganbote',
          }),
      })
    ) as unknown as typeof fetch;
  });

  it('renders without throwing', async () => {
    render(<App />);
    expect(await screen.findByRole('heading', { name: /BRD → Engineering Plan/i })).toBeInTheDocument();
  });

  it('renders the workspace title', async () => {
    render(<App />);
    expect(await screen.findByRole('heading', { name: /BRD → Engineering Plan/i })).toBeInTheDocument();
  });

  it('renders the workspace control elements', async () => {
    render(<App />);
    expect(await screen.findByRole('button', { name: /Browse files/i })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /Generate Engineering Plan/i })).toBeInTheDocument();
  });
});
