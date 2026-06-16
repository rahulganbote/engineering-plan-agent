import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from './App'

/**
 * Sprint 0 smoke test.
 * Goal: prove that the scaffolding (Vite + React + TS + Tailwind + shadcn Button)
 * is wired correctly. If this passes, the whole toolchain is healthy.
 * Real component tests get added as components are built in Sprint 1+.
 */
describe('App (Sprint 0 smoke)', () => {
  it('renders without throwing', () => {
    render(<App />)
  })

  it('shows the scaffold title', () => {
    render(<App />)
    expect(screen.getByText(/EM Copilot — React UI/i)).toBeInTheDocument()
  })

  it('renders the three example Buttons', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: 'Primary' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Secondary' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ghost' })).toBeInTheDocument()
  })
})
