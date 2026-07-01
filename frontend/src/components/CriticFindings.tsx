import { useState } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle2, AlertCircle } from 'lucide-react';

/**
 * Critic findings - surfaces the cross-agent consistency checks and
 * hallucination flags produced by the Critic agent.
 *
 * Mirrors the Streamlit "Critic findings · N consistency · M hallucination"
 * expander. Hidden when both lists are empty (clean runs).
 *
 * Data source: `artifacts.critic_output` from the /artifacts GET response.
 * Backend populates these via:
 *   - critic._check_cross_agent_consistency()   → ConsistencyIssue list
 *   - critic._detect_hallucinations()           → HallucinationFlag list
 */

interface ConsistencyIssue {
  agents_involved?: string[];
  conflict_description?: string;
  severity?: string;   // "low" | "medium" | "high" | "critical"
}

interface HallucinationFlag {
  agent?: string;
  claim?: string;
  status?: string;                // "supported" | "partially_supported" | "unsupported"
  supporting_chunk_id?: string | null;
}

interface CriticFindingsData {
  consistency_issues?: ConsistencyIssue[];
  hallucination_flags?: HallucinationFlag[];
}

interface CriticFindingsProps {
  /** Pass artifacts.critic_output from WorkspaceContext (typed as unknown). */
  criticDetail: unknown;
}

const SEVERITY_COLORS: Record<string, string> = {
  low:      'text-muted-foreground',
  medium:   'text-warning',
  high:     'text-orange-400',
  critical: 'text-danger',
};

const STATUS_COLORS: Record<string, string> = {
  supported:           'text-success',
  partially_supported: 'text-warning',
  unsupported:         'text-danger',
};

export const CriticFindings: React.FC<CriticFindingsProps> = ({ criticDetail }) => {
  const [expanded, setExpanded] = useState(false);

  const data = (criticDetail ?? {}) as CriticFindingsData;
  const issues = data.consistency_issues ?? [];
  const allFlags = data.hallucination_flags ?? [];

  // Surface only flags the Critic could NOT verify - "supported" claims are
  // verifications, not findings. This makes the count label match the user's
  // intuition: "5 hallucinations" should mean 5 real problems, not 5 checks
  // that all passed.
  const flaggedClaims = allFlags.filter(
    f => (f.status ?? '').toLowerCase() !== 'supported'
  );

  if (issues.length === 0 && flaggedClaims.length === 0) return null;

  return (
    <div className="border-t border-border pt-6 mt-6">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 rounded-lg border border-border bg-card/40 hover:bg-card/60 transition-colors"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-warning" />
          <span className="text-sm font-semibold text-foreground">
            Critic findings · {issues.length} consistency · {flaggedClaims.length} grounding
          </span>
        </div>
        {expanded
          ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
          : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="mt-3 px-4 py-3 rounded-lg border border-border bg-background/40 space-y-4">
          {issues.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-foreground uppercase tracking-wider mb-2">
                Consistency issues ({issues.length})
              </h4>
              <ul className="space-y-2">
                {issues.map((issue, i) => {
                  const sev = (issue.severity ?? 'medium').toLowerCase();
                  const sevColor = SEVERITY_COLORS[sev] ?? 'text-foreground';
                  return (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <AlertCircle className={`w-4 h-4 mt-0.5 ${sevColor}`} />
                      <div className="flex-1">
                        <span className={`text-xs font-semibold uppercase ${sevColor}`}>
                          {sev}
                        </span>
                        <span className="text-foreground ml-2">
                          {issue.conflict_description}
                        </span>
                        {issue.agents_involved?.length ? (
                          <span className="text-muted-foreground text-xs ml-2">
                            ({issue.agents_involved.join(', ')})
                          </span>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {flaggedClaims.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-foreground uppercase tracking-wider mb-2">
                Hallucination &amp; scope creep ({flaggedClaims.length})
              </h4>
              <ul className="space-y-2">
                {flaggedClaims.map((f, i) => {
                  const status = (f.status ?? 'unsupported').toLowerCase();
                  const statusColor = STATUS_COLORS[status] ?? 'text-foreground';
                  return (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <CheckCircle2 className={`w-4 h-4 mt-0.5 ${statusColor}`} />
                      <div className="flex-1">
                        <code className="text-xs text-muted-foreground bg-card px-1.5 py-0.5 rounded">
                          {f.agent}
                        </code>
                        <span className={`text-xs italic ml-2 ${statusColor}`}>
                          {status.replace('_', ' ')}
                        </span>
                        <span className="text-foreground ml-2">
                          {f.claim}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
