/**
 * Tests for useSSE hook — the SSE event parser that drives the entire UI.
 *
 * Strategy: mock EventSource, fire each event type one at a time, assert the
 * hook's state updated correctly. Covers the cases that hurt us most:
 *   - pipeline_complete must populate elapsedSeconds + tokens from payload
 *     (page-refresh recovery — the ticker can't fire fast enough)
 *   - agent_complete and agent_failed both mark the chip as "done"
 *   - artifacts fetch falls back to /artifacts/{runId} on status change
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useSSE } from '../useSSE';

// ── EventSource mock ────────────────────────────────────────────────────────
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  readyState = 1;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  close() { this.readyState = 2; }
  fire(payload: object) { this.onmessage?.({ data: JSON.stringify(payload) }); }
}

beforeEach(() => {
  MockEventSource.instances = [];
  // @ts-expect-error overriding global
  globalThis.EventSource = MockEventSource;
  // Mock fetch for /artifacts fallback
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
  );
});

describe('useSSE', () => {
  it('returns idle state when runId is null', () => {
    const { result } = renderHook(() => useSSE(null, 'http://localhost:8000'));
    expect(result.current.pipelineStatus).toBe('idle');
    expect(result.current.logs).toEqual([]);
    expect(result.current.elapsedSeconds).toBe(0);
    expect(result.current.tokenUsage).toBeNull();
  });

  it('opens EventSource when runId is provided', () => {
    renderHook(() => useSSE('test-run', 'http://localhost:8000'));
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toContain('/status/test-run');
  });

  it('populates elapsedSeconds, tokens, and costUsd from pipeline_complete event (refresh recovery)', () => {
    const { result } = renderHook(() => useSSE('test-run', 'http://localhost:8000'));
    act(() => {
      MockEventSource.instances[0].fire({
        type: 'pipeline_complete',
        status: 'awaiting_hitl',
        processing_time_sec: 27.5,
        total_input_tokens: 12345,
        total_output_tokens: 4567,
        total_cost_usd: 0.0825,
      });
    });
    expect(result.current.elapsedSeconds).toBe(28);
    expect(result.current.tokenUsage).toEqual({ input: 12345, output: 4567 });
    expect(result.current.costUsd).toBe(0.0825);
    expect(result.current.pipelineStatus).toBe('awaiting_hitl');
  });

  it('adds agent to completedAgents on agent_complete', () => {
    const { result } = renderHook(() => useSSE('test-run', 'http://localhost:8000'));
    act(() => {
      MockEventSource.instances[0].fire({ type: 'agent_complete', agent: 'plan_generator' });
    });
    expect(result.current.completedAgents.has('plan_generator')).toBe(true);
  });

  it('also marks chip done on agent_failed (stops spinner)', () => {
    const { result } = renderHook(() => useSSE('test-run', 'http://localhost:8000'));
    act(() => {
      MockEventSource.instances[0].fire({ type: 'agent_failed', agent: 'critic' });
    });
    expect(result.current.completedAgents.has('critic')).toBe(true);
  });

  it('appends events to logs', () => {
    const { result } = renderHook(() => useSSE('test-run', 'http://localhost:8000'));
    act(() => {
      MockEventSource.instances[0].fire({ type: 'agent_start', agent: 'plan_generator' });
      MockEventSource.instances[0].fire({ type: 'cache_hit', backend: 'l1' });
    });
    expect(result.current.logs.length).toBeGreaterThanOrEqual(2);
  });

  it('clearRun resets all state', async () => {
    const { result } = renderHook(() => useSSE('test-run', 'http://localhost:8000'));
    act(() => {
      MockEventSource.instances[0].fire({
        type: 'pipeline_complete',
        status: 'awaiting_hitl',
        processing_time_sec: 27.5,
        total_input_tokens: 12345,
        total_output_tokens: 4567,
        total_cost_usd: 0.0825,
      });
    });
    expect(result.current.costUsd).toBe(0.0825);
    act(() => { result.current.clearRun(); });
    await waitFor(() => expect(result.current.completedAgents.size).toBe(0));
    expect(result.current.pipelineStatus).toBe('idle');
    expect(result.current.tokenUsage).toBeNull();
    expect(result.current.costUsd).toBeNull();
  });

  it('populates costUsd and other fields from fallback artifacts API', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          brd_sections: [{ title: 'Overview' }],
          plan_output: { agent_name: 'engineering_plan_generator' },
          processing_time_sec: 15.2,
          total_input_tokens: 2000,
          total_output_tokens: 1000,
          total_cost_usd: 0.015,
        }),
      } as Response)
    );

    const { result } = renderHook(() => useSSE('test-run', 'http://localhost:8000'));
    act(() => {
      MockEventSource.instances[0].fire({
        type: 'pipeline_complete',
        status: 'awaiting_hitl',
        processing_time_sec: 15.2,
      });
    });

    await waitFor(() => expect(result.current.costUsd).toBe(0.015));
    expect(result.current.tokenUsage).toEqual({ input: 2000, output: 1000 });
    expect(result.current.elapsedSeconds).toBe(15);
  });
});
