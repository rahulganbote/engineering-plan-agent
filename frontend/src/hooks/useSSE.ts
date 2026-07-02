import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { apiFetch } from '../lib/apiClient';
import { cleanLlmErrorMessage } from '../lib/utils';
import { type PipelineStatus, PIPELINE_STATUS } from '../lib/pipelineStatus';

export interface LogEvent {
  type: string;
  payload?: Record<string, unknown>;
  timestamp?: string;
  status?: string;
  agent?: string;
  final_status?: string;
  pii_types?: unknown;
  message?: string;
  decision?: string;
  reviewer?: string;
  mode?: string;
  sheet_url?: string;
  error?: string;
  issue_key?: string;
  url?: string;
  detail?: string;
  key?: string;
  circuit?: string;
  breaker?: string;
  from_family?: string;
  to_family?: string;
  reason?: string;
  attempt?: number;
  timeout_sec?: number;
  input?: number;
  output?: number;
  revision?: number;
  targets?: string[];
  seq?: number;
  ts?: number;
}

export interface CriticDimension {
  score: number;
  threshold: number;
  passed: boolean;
}

export interface CriticOutput {
  revisionNumber: number;
  overallScore: number;
  badge: 'green' | 'amber' | 'red';
  dimensions: Record<string, CriticDimension>;
}

export interface ApprovalResult {
  decision: 'approved' | 'rejected';
  sheet_url?: string;
  jira_url?: string;
  rejection_count: number;
  export_status?: string;
  export_mode?: string;
  export_detail?: string;
  jira_status?: string;
  jira_issue_key?: string;
  jira_detail?: string;
}

// Backend returns these as Pydantic objects (structured), not strings.
// Sprint 3 stopgap: store as `unknown`; let the UI render via JSON.stringify or
// per-field accessors. Sprint 4 builds typed Plan/Schedule/Arch/PoC/Stack interfaces.
export interface ArtifactsState {
  plan_output?: unknown;
  schedule_output?: unknown;
  arch_output?: unknown;
  poc_output?: unknown;
  stack_output?: unknown;
  brd_sections?: unknown;
  critic_output?: unknown;
}

interface ArtifactsResponse {
  brd_sections?: unknown[];
  plan_output?: unknown;
  schedule_output?: unknown;
  arch_output?: unknown;
  poc_output?: unknown;
  stack_output?: unknown;
  processing_time_sec?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
  total_cost_usd?: number;
  fallback_occurred?: boolean;
  fallback_from?: string;
  fallback_to?: string;
  errors?: string[];
  pipeline_status?: string;
  critic_output?: {
    revision_number: number;
    overall_score: number;
    badge?: string;
    dimensions?: Record<string, CriticDimension>;
    groundedness?: CriticDimension;
    completeness?: CriticDimension;
    consistency?: CriticDimension;
    actionability?: CriticDimension;
  };
  export?: {
    sheet_url?: string | null;
    mode?: string;
    status?: string;
    detail?: string;
    fallback_reason?: string | null;
    jira?: {
      url?: string | null;
      mode?: string;
      issue_key?: string | null;
      detail?: string | null;
    };
  };
}

export const useSSE = (runId: string | null, apiBaseUrl: string) => {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>(PIPELINE_STATUS.IDLE);
  const [artifacts, setArtifacts] = useState<ArtifactsState | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [tokenUsage, setTokenUsage] = useState<{ input: number; output: number } | null>(null);
  const [costUsd, setCostUsd] = useState<number | null>(null);
  const [criticOutput, setCriticOutput] = useState<CriticOutput | null>(null);
  const [approvalResult, setApprovalResult] = useState<ApprovalResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fallbackActive, setFallbackActive] = useState<{ from: string; to: string } | null>(null);
  const [prevRunId, setPrevRunId] = useState<string | null>(null);

  const seenSeqs = useRef<Set<number>>(new Set());

  if (runId !== prevRunId) {
    setPrevRunId(runId);
    if (runId) {
      setPipelineStatus(PIPELINE_STATUS.INITIALIZING);
    }
  }

  const clearRun = useCallback((newStatus: PipelineStatus = PIPELINE_STATUS.IDLE) => {
    setLogs([]);
    setPipelineStatus(newStatus);
    setArtifacts(null);
    setElapsedSeconds(0);
    setTokenUsage(null);
    setCostUsd(null);
    setCriticOutput(null);
    setApprovalResult(null);
    setErrorMessage(null);
    setFallbackActive(null);
    seenSeqs.current.clear();
  }, []);

  const completedAgents = useMemo(() => {
    const s = new Set<string>();

    for (const log of logs) {
      if (log.type === 'agent_start' && log.agent) {
        s.delete(log.agent);
      } else if ((log.type === 'agent_complete' || log.type === 'agent_failed') && log.agent) {
        s.add(log.agent);
      }
    }

    if (artifacts?.brd_sections && (artifacts.brd_sections as unknown[]).length > 0) {
      s.add('orchestrator');
    }
    if (artifacts?.plan_output) {
      s.add('engineering_plan_generator');
    }
    if (artifacts?.schedule_output) {
      s.add('schedule_estimator');
    }
    if (artifacts?.arch_output) {
      s.add('solution_architect');
    }
    if (artifacts?.poc_output) {
      s.add('poc_planner');
    }
    if (artifacts?.stack_output) {
      s.add('tech_stack_recommender');
    }
    if (artifacts?.critic_output) {
      s.add('critic');
    }

    return s;
  }, [artifacts, logs]);

  useEffect(() => {
    if (!runId) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    clearRun('initializing');

    const es = new EventSource(`${apiBaseUrl}/status/${runId}`, { withCredentials: true });
    const startTs = Date.now();
    const tick = setInterval(() => {
      setElapsedSeconds(Math.round((Date.now() - startTs) / 1000));
    }, 1000);

    let processedIndex = 0;

    const processEvent = (data: LogEvent) => {
      if (typeof data.seq === 'number') {
        if (seenSeqs.current.has(data.seq)) return;
        seenSeqs.current.add(data.seq);
      }
      setLogs((prev) => [...prev, data]);

      switch (data.type) {
        case 'status':
        case 'pipeline_status': {
          const status = data.status || (data.payload as Record<string, string>)?.status;
          setPipelineStatus((status || PIPELINE_STATUS.IDLE) as PipelineStatus);
          break;
        }
        case 'provider_fallback': {
          setFallbackActive({
            from: data.from_family || '',
            to: data.to_family || '',
          });
          break;
        }
        case 'artifacts_update': {
          const artifactsPayload = data.payload || data;
          setArtifacts(artifactsPayload as unknown as ArtifactsState);
          break;
        }
        case 'token_update': {
          const payload = (data.payload || data) as Record<string, number> | undefined;
          if (payload) {
            setTokenUsage({ input: payload.input || 0, output: payload.output || 0 });
          }
          break;
        }
        case 'critic_complete': {
          const criticPayload = (data.payload || data) as Record<string, unknown>;
          const parseDimension = (val: unknown) => val as CriticDimension;
          setCriticOutput({
            revisionNumber: (criticPayload.revision_number ?? criticPayload.revisionNumber) as number,
            overallScore: (criticPayload.overall_score ?? criticPayload.overallScore) as number,
            badge: ((criticPayload.badge as string)?.toLowerCase() || criticPayload.badge) as 'green' | 'amber' | 'red',
            dimensions: (criticPayload.dimensions || {
              groundedness: parseDimension(criticPayload.groundedness),
              completeness: parseDimension(criticPayload.completeness),
              consistency: parseDimension(criticPayload.consistency),
              actionability: parseDimension(criticPayload.actionability),
            }) as Record<string, CriticDimension>,
          });
          break;
        }
        case 'hitl_decision': {
          const hitlPayload = data.payload || data;
          setApprovalResult(hitlPayload as unknown as ApprovalResult);
          break;
        }
        case 'exports_finalized': {
          // Terminal event from the /approve background task - carries the
          // fully-resolved ApprovalResponse payload (sheet_url, jira_url,
          // export_status, etc.) so the UI can hydrate after the async exports
          // complete. Without this handler, the button-click flow would never
          // see the integration URLs because the initial POST /approve response
          // is now async-pending.
          const payload = (data.payload as Record<string, unknown>) || (data as unknown as Record<string, unknown>);
          setApprovalResult({
            decision: (payload.decision as 'approved' | 'rejected') || 'approved',
            sheet_url: payload.sheet_url as string | undefined,
            jira_url: payload.jira_url as string | undefined,
            rejection_count: (payload.rejection_count as number) ?? 0,
            export_status: payload.export_status as string | undefined,
            export_mode: payload.export_mode as string | undefined,
            export_detail: payload.export_detail as string | undefined,
            jira_status: payload.jira_status as string | undefined,
            jira_issue_key: payload.jira_issue_key as string | undefined,
            jira_detail: payload.jira_detail as string | undefined,
          });
          const finalStatus = payload.pipeline_status as string | undefined;
          if (finalStatus) setPipelineStatus(finalStatus as PipelineStatus);
          // This is the TRUE end of the run lifecycle (pipeline + exports done).
          // Now safe to close SSE; useEffect cleanup also closes on unmount.
          clearInterval(tick);
          clearInterval(pollInterval);
          es.close();
          break;
        }
        case 'pipeline_complete': {
          const finalStatus = data.status || data.final_status || (data.payload as Record<string, string>)?.final_status || (data.payload as Record<string, string>)?.status;
          setPipelineStatus((finalStatus || PIPELINE_STATUS.AWAITING_HITL) as PipelineStatus);
          const flat = data as unknown as Record<string, unknown>;
          const inner = (data.payload as Record<string, unknown>) || {};
          const pt = (flat.processing_time_sec ?? inner.processing_time_sec) as number | undefined;
          if (pt != null && pt > 0) setElapsedSeconds(Math.round(pt));
          const tin = (flat.total_input_tokens ?? inner.total_input_tokens) as number | undefined;
          const tout = (flat.total_output_tokens ?? inner.total_output_tokens) as number | undefined;
          if (tin != null || tout != null) setTokenUsage({ input: tin || 0, output: tout || 0 });
          const cost = (flat.total_cost_usd ?? inner.total_cost_usd) as number | undefined;
          if (cost != null) setCostUsd(cost);
          // ── IMPORTANT: do NOT close SSE here ─────────────────────────────────
          // pipeline_complete fires when the orchestrator + critic + HITL routing
          // is done, BUT the run lifecycle continues:
          //   1. User reviews artifacts at HITL gate
          //   2. User clicks Approve (button) OR talks to voice agent
          //   3. Backend emits hitl_decision + (later) exports_finalized
          //
          // If we closed SSE here, those post-decision events would arrive at a
          // dead connection - the UI would never see sheet_url / jira_url and
          // the HITL gate would never transition to "approved" state.
          //
          // SSE stays open until exports_finalized fires (true end of lifecycle)
          // or the React component unmounts (useEffect cleanup closes it).
          // The tick interval is the only thing safe to stop now.
          clearInterval(tick);
          break;
        }
        case 'security_blocked': {
          setPipelineStatus(PIPELINE_STATUS.ERROR);
          setErrorMessage(cleanLlmErrorMessage(data.message || 'Security validation blocked.'));
          clearInterval(tick);
          clearInterval(pollInterval);
          es.close();
          break;
        }
        case 'error': {
          setPipelineStatus(PIPELINE_STATUS.ERROR);
          setErrorMessage(cleanLlmErrorMessage(data.message || 'An unexpected error occurred.'));
          clearInterval(tick);
          clearInterval(pollInterval);
          es.close();
          break;
        }
      }
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as LogEvent;
        processEvent(data);
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.onerror = (err) => {
      console.warn('SSE connection failed; relying on polling fallback.', err);
    };

    // Robust Polling Fallback (Polls every 2 seconds for updates)
    const pollInterval = setInterval(async () => {
      try {
        const res = await apiFetch<{ events: LogEvent[], next_index: number }>(
          `${apiBaseUrl}/events/${runId}?since=${processedIndex}`
        );
        if (res && res.events && res.events.length > 0) {
          res.events.forEach(data => {
            processEvent(data);
          });
          processedIndex = res.next_index;
        }
      } catch (e) {
        console.error('Event polling fallback failed:', e);
      }
    }, 2000);

    return () => {
      clearInterval(tick);
      clearInterval(pollInterval);
      es.close();
    };
  }, [runId, apiBaseUrl, clearRun]);

  // Fetch final artifacts when runId is set and pipeline status transitions to final/gate states
  const fetchArtifacts = useCallback(async () => {
    if (!runId) return;
    try {
      const data = await apiFetch<ArtifactsResponse>(`${apiBaseUrl}/artifacts/${runId}`);
      
      if (data.brd_sections) {
        setArtifacts({
          plan_output: data.plan_output || undefined,
          schedule_output: data.schedule_output || undefined,
          arch_output: data.arch_output || undefined,
          poc_output: data.poc_output || undefined,
          stack_output: data.stack_output || undefined,
          brd_sections: data.brd_sections || undefined,
        });
      }
      // Pick up time + tokens from /artifacts response (works on refresh)
      if (data.processing_time_sec != null && data.processing_time_sec > 0) {
        setElapsedSeconds(Math.round(data.processing_time_sec));
      }
      if (data.total_input_tokens != null || data.total_output_tokens != null) {
        setTokenUsage({
          input: data.total_input_tokens || 0,
          output: data.total_output_tokens || 0,
        });
      }
      if (data.total_cost_usd != null) {
        setCostUsd(data.total_cost_usd);
      }
      if (data.fallback_occurred) {
        setFallbackActive({
          from: data.fallback_from || '',
          to: data.fallback_to || '',
        });
      }
      if (data.pipeline_status === 'error') {
        setPipelineStatus(PIPELINE_STATUS.ERROR);
        setErrorMessage(cleanLlmErrorMessage(data.errors?.[0] || 'An unexpected error occurred.'));
      }

      if (data.critic_output) {
        setCriticOutput({
          revisionNumber: data.critic_output.revision_number,
          overallScore: data.critic_output.overall_score,
          badge: data.critic_output.badge?.toLowerCase() as 'green' | 'amber' | 'red',
          dimensions: data.critic_output.dimensions || {
            groundedness: data.critic_output.groundedness!,
            completeness: data.critic_output.completeness!,
            consistency: data.critic_output.consistency!,
            actionability: data.critic_output.actionability!,
          },
        });
      }

      if (data.export) {
        setApprovalResult({
          decision: data.export.status === 'rejected' ? 'rejected' : 'approved',
          sheet_url: data.export.sheet_url || undefined,
          jira_url: data.export.jira?.url || undefined,
          rejection_count: 0,
          export_status: data.export.status || undefined,
          export_mode: data.export.mode || undefined,
          export_detail: data.export.detail || undefined,
          jira_status: data.export.jira?.mode || undefined,
          jira_issue_key: data.export.jira?.issue_key || undefined,
          jira_detail: data.export.jira?.detail || undefined,
        });
      }
    } catch (e) {
      console.error('Failed to fetch artifacts:', e);
    }
  }, [runId, apiBaseUrl]);

  useEffect(() => {
    if (!runId) return;

    if (([PIPELINE_STATUS.AWAITING_HITL, PIPELINE_STATUS.EXPORTED, PIPELINE_STATUS.EXPORT_FAILED, PIPELINE_STATUS.REJECTED, PIPELINE_STATUS.ERROR] as PipelineStatus[]).includes(pipelineStatus)) {
      Promise.resolve().then(() => {
        fetchArtifacts();
      });
    }
  }, [runId, pipelineStatus, fetchArtifacts]);

  return {
    logs,
    pipelineStatus,
    completedAgents,
    artifacts,
    elapsedSeconds,
    tokenUsage,
    costUsd,
    criticOutput,
    approvalResult,
    clearRun,
    fetchArtifacts,
    setPipelineStatus,
    setApprovalResult,
    errorMessage,
    fallbackActive,
  };
};
