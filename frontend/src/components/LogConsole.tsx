import React, { useEffect, useRef, useState } from 'react';
import { Terminal, Copy, Check } from 'lucide-react';
import { type LogEvent } from '../hooks/useSSE';
import { cleanLlmErrorMessage } from '../lib/utils';

interface LogConsoleProps {
  logs: LogEvent[];
}

export const LogConsole: React.FC<LogConsoleProps> = ({ logs }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  // Map event types to formatted strings
  const formatEventText = (log: LogEvent): string => {
    switch (log.type) {
      case 'agent_start':
        return `[Agent: ${log.agent}] Starting execution...`;
      case 'agent_complete':
        return `[Agent: ${log.agent}] Completed execution successfully.`;
      case 'status':
      case 'pipeline_status':
        return `[Pipeline] Status changed: ${log.status || log.payload?.status || 'unknown'}`;
      case 'pipeline_complete':
        return `[Pipeline] Run completed. Final status: ${log.status || log.final_status || 'completed'}`;
      case 'pii_warning':
        return `[PII Check] Blocked/redacted potential sensitive data. Types: ${Array.isArray(log.pii_types) ? log.pii_types.join(', ') : JSON.stringify(log.pii_types)}`;
      case 'hitl_decision':
        return `[HITL] Human Decision: Reviewer "${log.reviewer || 'EM'}" marked run as "${log.decision || 'unknown'}".`;
      case 'hitl_escalated':
        return `[HITL] Escalation Triggered: ${log.message || 'Two rejections - flagging for audit review'}`;
      case 'export_complete':
        return `[Export] Success: Saved to ${log.mode || 'local fallback'}. ${log.sheet_url ? `URL: ${log.sheet_url}` : ''}`;
      case 'export_failed':
        return `[Export] Critical failure: ${log.error || 'unknown'}`;
      case 'jira_pushed':
        return `[Jira Integration] Epic successfully pushed: [${log.issue_key}] -> ${log.url}`;
      case 'jira_skipped':
        return `[Jira Integration] Push skipped: ${log.detail || 'not configured or matching key found'}`;
      case 'idempotent_skip':
        return `[Jira Integration] Reusing existing issue key: ${log.issue_key}`;
      case 'pinecone_ingest':
        return `[Pinecone RAG] Text chunk successfully ingested. Status: ${log.status || 'ok'}`;
      case 'pinecone_ingest_failed':
        return `[Pinecone RAG] Ingestion error: ${log.error}`;
      case 'cache_hit':
        return `[Resilience Cache] Cache hit for key: ${log.key || 'unknown'}`;
      case 'cache_miss':
        return `[Resilience Cache] Cache miss for key: ${log.key || 'unknown'}. Re-processing...`;
      case 'breaker_open':
        return `[Circuit Breaker] Tripped! Circuit "${log.breaker || log.circuit || 'unknown'}" is now OPEN.`;
      case 'breaker_short_circuit':
        return `[Circuit Breaker] Short-circuit fast fail: Execution rejected by open circuit "${log.breaker || log.circuit || 'unknown'}".`;
      case 'retry':
        return `[Resilience Retry] Attempt #${log.attempt || 1} after error: ${log.error || 'timeout'}`;
      case 'bulkhead_timeout':
        return `[Resilience Bulkhead] Timeout! Specialist "${log.agent || 'unknown'}" timed out after ${log.timeout_sec || 90}s (bulkhead isolation triggered).`;
      case 'error':
        return `[System Error] Critical exception: ${log.message || 'unknown error'}`;
      case 'provider_fallback': {
        const fromFam = log.from_family || (log.payload as Record<string, string>)?.from_family || 'unknown';
        const toFam = log.to_family || (log.payload as Record<string, string>)?.to_family || 'unknown';
        const reason = log.reason || (log.payload as Record<string, string>)?.reason || '';
        const cleanReason = cleanLlmErrorMessage(reason);
        return `[LLM Engine] Fallback Triggered: ${fromFam.toUpperCase()} API limits reached or key expired. Switched to ${toFam.toUpperCase()} successfully.${cleanReason ? ` Reason: ${cleanReason}` : ''}`;
      }
      case 'token_update': {
        const payload = (log.payload || log) as LogEvent;
        return `[Token Engine] Usage update: ${payload.input?.toLocaleString() || 0} in / ${payload.output?.toLocaleString() || 0} out`;
      }
      case 'artifacts_update':
        return `[Artifacts Engine] Shared state bundles updated.`;
      default: {
        const { type, payload, ...extra } = log;
        delete (extra as Record<string, unknown>).timestamp;
        const extraStr = Object.keys(extra).length ? ` | ${JSON.stringify(extra)}` : '';
        return `[Event: ${type}]${payload ? ` Payload: ${JSON.stringify(payload)}` : ''}${extraStr}`;
      }
    }
  };

  // Map event types to CSS color classes
  const getEventColorClass = (type: string): string => {
    switch (type) {
      // Cyan (Info)
      case 'agent_start':
      case 'agent_complete':
      case 'pipeline_status':
      case 'status':
      case 'token_update':
      case 'artifacts_update':
        return 'text-cyan-400';

      // Amber (Warning)
      case 'retry':
      case 'pii_warning':
      case 'breaker_short_circuit':
      case 'hitl_escalated':
      case 'jira_skipped':
      case 'provider_fallback':
        return 'text-warning font-bold';

      // Red (Critical/Error)
      case 'error':
      case 'bulkhead_timeout':
      case 'breaker_open':
      case 'export_failed':
      case 'pinecone_ingest_failed':
        return 'text-danger font-bold';

      // Green (Success)
      case 'pipeline_complete':
      case 'export_complete':
      case 'cache_hit':
      case 'jira_pushed':
      case 'idempotent_skip':
      case 'pinecone_ingest':
        return 'text-success';

      default:
        return 'text-foreground';
    }
  };

  const getFullTextLog = () => {
    return logs
      .map((log, i) => `[${(i + 1).toString().padStart(2, '0')}] ${formatEventText(log)}`)
      .join('\n');
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getFullTextLog());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden bg-background flex flex-col shadow-lg">
      {/* Console Header */}
      <div className="px-5 py-3 bg-card border-b border-border flex justify-between items-center select-none">
        <div className="flex items-center gap-2 text-foreground">
          <Terminal size={16} className="text-cyan-400" />
          <span className="font-bold text-xs uppercase tracking-wider">Live Pipeline Engine Console</span>
          <span className="px-1.5 py-0.5 bg-secondary rounded text-[10px] text-muted-foreground font-mono">
            {logs.length} events
          </span>
        </div>
        <button
          onClick={handleCopy}
          disabled={logs.length === 0}
          className="flex items-center gap-1.5 px-2.5 py-1 bg-secondary hover:bg-secondary text-foreground disabled:opacity-55 disabled:cursor-not-allowed rounded text-[11px] font-semibold border border-border transition"
          title="Copy formatted logs to clipboard"
        >
          {copied ? (
            <>
              <Check size={12} className="text-success animate-scale-in" />
              <span className="text-success">Copied!</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>Copy Logs</span>
            </>
          )}
        </button>
      </div>

      {/* Terminal logs list */}
      <div
        ref={containerRef}
        className="p-5 bg-background text-foreground font-mono text-xs max-h-72 min-h-[12rem] overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent"
      >
        {logs.length === 0 ? (
          <div className="text-muted-foreground italic flex items-center gap-2 select-none h-full justify-center py-12">
            <span className="animate-pulse">_</span> Awaiting execution triggers to hook into the SSE event stream...
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="leading-relaxed hover:bg-card/40 px-1 rounded transition-colors flex items-start gap-3">
              {/* Event counter */}
              <span className="text-muted-foreground select-none font-bold shrink-0">
                [{(i + 1).toString().padStart(2, '0')}]
              </span>
              
              {/* Formatted Message */}
              <span className={`break-all ${getEventColorClass(log.type)}`}>
                {formatEventText(log)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
