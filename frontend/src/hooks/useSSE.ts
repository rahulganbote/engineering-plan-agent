import { useState, useEffect, useCallback } from 'react';

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
  attempt?: number;
  timeout_sec?: number;
  input?: number;
  output?: number;
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

export const useSSE = (runId: string | null, apiBaseUrl: string) => {
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<string>('idle');
  const [completedAgents, setCompletedAgents] = useState<Set<string>>(new Set());
  const [artifacts, setArtifacts] = useState<ArtifactsState | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [tokenUsage, setTokenUsage] = useState<{ input: number; output: number } | null>(null);
  const [criticOutput, setCriticOutput] = useState<CriticOutput | null>(null);
  const [approvalResult, setApprovalResult] = useState<ApprovalResult | null>(null);

  const clearRun = useCallback(() => {
    setLogs([]);
    setPipelineStatus('idle');
    setCompletedAgents(new Set());
    setArtifacts(null);
    setElapsedSeconds(0);
    setTokenUsage(null);
    setCriticOutput(null);
    setApprovalResult(null);
  }, []);

  useEffect(() => {
    if (!runId) return;

    const es = new EventSource(`${apiBaseUrl}/status/${runId}`, { withCredentials: true });
    const statusTimeout = setTimeout(() => {
      setPipelineStatus('initializing');
    }, 0);
    const startTs = Date.now();
    const tick = setInterval(() => {
      setElapsedSeconds(Math.round((Date.now() - startTs) / 1000));
    }, 1000);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as LogEvent;
        setLogs((prev) => [...prev, data]);

        switch (data.type) {
          case 'status':
          case 'pipeline_status': {
            const status = data.status || (data.payload as Record<string, string>)?.status;
            setPipelineStatus(status || 'unknown');
            break;
          }
          case 'agent_start': {
            const agent = data.agent || (data.payload as Record<string, string>)?.agent;
            if (agent) {
              setCompletedAgents((prev) => {
                const next = new Set(prev);
                next.delete(agent);
                return next;
              });
            }
            break;
          }
          case 'agent_complete': {
            const agent = data.agent || (data.payload as Record<string, string>)?.agent;
            if (agent) {
              setCompletedAgents((prev) => {
                const next = new Set(prev);
                next.add(agent);
                return next;
              });
            }
            break;
          }
          case 'agent_failed': {
            // Backend emits this when an agent raises. Mark the chip as
            // "completed" (stops spinner). Sprint 5 polish: distinct "failed"
            // visual state on the TimelineStepper chip.
            const agent = data.agent || (data.payload as Record<string, string>)?.agent;
            if (agent) {
              setCompletedAgents((prev) => {
                const next = new Set(prev);
                next.add(agent);
                return next;
              });
            }
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
            const criticPayload = data.payload || data;
            setCriticOutput(criticPayload as unknown as CriticOutput);
            break;
          }
          case 'hitl_decision': {
            const hitlPayload = data.payload || data;
            setApprovalResult(hitlPayload as unknown as ApprovalResult);
            break;
          }
          case 'pipeline_complete': {
            const finalStatus = data.status || data.final_status || (data.payload as Record<string, string>)?.final_status || (data.payload as Record<string, string>)?.status;
            setPipelineStatus(finalStatus || 'completed');
            // Populate time + tokens from the event payload (covers refresh case —
            // SSE replay delivers pipeline_complete instantly so the per-second tick
            // has no chance to fire). Backend includes processing_time_sec +
            // total_input_tokens + total_output_tokens on this event.
            const flat = data as unknown as Record<string, unknown>;
            const inner = (data.payload as Record<string, unknown>) || {};
            const pt = (flat.processing_time_sec ?? inner.processing_time_sec) as number | undefined;
            if (pt != null && pt > 0) setElapsedSeconds(Math.round(pt));
            const tin = (flat.total_input_tokens ?? inner.total_input_tokens) as number | undefined;
            const tout = (flat.total_output_tokens ?? inner.total_output_tokens) as number | undefined;
            if (tin != null || tout != null) setTokenUsage({ input: tin || 0, output: tout || 0 });
            clearInterval(tick);
            es.close();
            break;
          }
          case 'error': {
            setPipelineStatus('error');
            clearInterval(tick);
            es.close();
            break;
          }
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.onerror = (err) => {
      console.error('SSE connection failed:', err);
      setPipelineStatus('error');
      clearInterval(tick);
      es.close();
    };

    return () => {
      clearTimeout(statusTimeout);
      clearInterval(tick);
      es.close();
    };
  }, [runId, apiBaseUrl]);

  // Fetch final artifacts when runId is set and pipeline status transitions to final/gate states
  const fetchArtifacts = useCallback(async () => {
    if (!runId) return;
    try {
      const response = await fetch(`${apiBaseUrl}/artifacts/${runId}`, { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        
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

        if (data.critic_output) {
          setCriticOutput({
            revisionNumber: data.critic_output.revision_number,
            overallScore: data.critic_output.overall_score,
            badge: data.critic_output.badge?.toLowerCase() as 'green' | 'amber' | 'red',
            dimensions: data.critic_output.dimensions || {},
          });
        }

        // Force-fill completed agents if artifacts exist
        setCompletedAgents((prev) => {
          const next = new Set(prev);
          if (data.brd_sections && data.brd_sections.length > 0) {
            next.add('orchestrator');
          }
          if (data.plan_output) {
            next.add('engineering_plan_generator');
          }
          if (data.schedule_output) {
            next.add('schedule_estimator');
          }
          if (data.arch_output) {
            next.add('solution_architect');
          }
          if (data.poc_output) {
            next.add('poc_planner');
          }
          if (data.stack_output) {
            next.add('tech_stack_recommender');
          }
          if (data.critic_output) {
            next.add('critic');
          }
          return next;
        });
      }
    } catch (e) {
      console.error('Failed to fetch artifacts:', e);
    }
  }, [runId, apiBaseUrl]);

  useEffect(() => {
    if (!runId) return;

    if (['awaiting_hitl', 'exported', 'export_failed', 'rejected', 'error'].includes(pipelineStatus)) {
      fetchArtifacts();
    }
  }, [runId, pipelineStatus, fetchArtifacts]);

  return {
    logs,
    pipelineStatus,
    completedAgents,
    artifacts,
    elapsedSeconds,
    tokenUsage,
    criticOutput,
    approvalResult,
    clearRun,
    fetchArtifacts,
    setPipelineStatus,
    setApprovalResult,
  };
};
