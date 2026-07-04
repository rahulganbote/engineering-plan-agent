import React from 'react';
import { AlertCircle, Award } from 'lucide-react';

interface Milestone {
  name: string;
  week: number;
  deliverable: string;
  owner_role: string;
}

interface Risk {
  description: string;
  likelihood: string;
  impact: string;
  mitigation: string;
  citation: string;
}

interface Phase {
  name: string;
  duration_weeks: number;
  objectives: string[];
  milestones: Milestone[];
}

interface PlanOutput {
  phases?: Phase[];
  risks?: Risk[];
  team_composition?: Record<string, number>;
  total_duration_weeks?: number;
  reflection_notes?: string;
  confidence_score?: number;
  llm_confidence_score?: number | null;
  confidence_drivers?: string[];
}

interface PlanTabProps {
  planData: unknown;
}

export const PlanTab: React.FC<PlanTabProps> = ({ planData }) => {
  // Parse defensively (handles both pre-parsed JSON objects or raw string formats)
  let plan: PlanOutput | null = null;
  if (planData) {
    if (typeof planData === 'string') {
      try {
        plan = JSON.parse(planData) as PlanOutput;
      } catch {
        plan = null;
      }
    } else {
      plan = planData as PlanOutput;
    }
  }

  if (!plan || (!plan.phases && !plan.risks && !plan.team_composition)) {
    return (
      <div className="p-6 bg-card border border-border rounded-xl text-center space-y-3">
        <AlertCircle className="mx-auto text-muted-foreground" size={32} />
        <h4 className="text-sm font-bold text-foreground">Plan Content Unavailable</h4>
        <p className="text-xs text-muted-foreground max-w-md mx-auto">
          The engineering plan structure could not be parsed. Below is the raw data:
        </p>
        <pre className="p-4 bg-background rounded text-left font-mono text-[10px] text-muted-foreground overflow-x-auto whitespace-pre-wrap max-h-60">
          {typeof planData === 'string' ? planData : JSON.stringify(planData, null, 2)}
        </pre>
      </div>
    );
  }

  // Gather unique citations for footnote indexing
  const citationsList = Array.from(
    new Set(
      (plan.risks || [])
        .map((r) => r.citation)
        .filter((c): c is string => typeof c === 'string' && c.trim().length > 0)
    )
  );

  const getCitationIndex = (citation: string) => {
    return citationsList.indexOf(citation) + 1;
  };

  const getRoleInitials = (role: string) => {
    return role
      .split(' ')
      .map((w) => w[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const getRiskBadgeColor = (level: string) => {
    const l = level.toLowerCase();
    if (l === 'high' || l === 'critical' || l === 'red') {
      return 'bg-danger/40 text-danger border border-danger/30';
    }
    if (l === 'medium' || l === 'amber') {
      return 'bg-warning/40 text-warning border border-warning/30';
    }
    return 'bg-green-950/40 text-success border border-green-900/30';
  };

  return (
    <div className="space-y-8 animate-fade-in text-foreground">
      {/* Overview Block */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-background border border-border p-6 rounded-xl shadow-inner">
        <div className="md:col-span-1 flex flex-col justify-between gap-4">
          <div>
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-1">Total Duration</span>
            <span className="text-2xl font-black text-primary">{plan.total_duration_weeks || '-'} weeks</span>
          </div>
          {plan.confidence_score !== undefined && (
            <div>
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-1">Plan Confidence</span>
              <span className="text-2xl font-black text-primary">{(plan.confidence_score * 100).toFixed(0)}%</span>
              {plan.confidence_drivers && plan.confidence_drivers.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-[10px] text-muted-foreground leading-snug">
                  {plan.confidence_drivers.map((driver, idx) => (
                    <li key={idx}>{driver}</li>
                  ))}
                </ul>
              )}
              {/* Judge-disagreement flag: LLM saw something the structural signals missed
                  (or vice versa). Surfaced only when the gap exceeds 0.20, so a healthy
                  ±0.05 drift stays quiet and doesn't cry wolf. */}
              {plan.llm_confidence_score != null &&
                Math.abs(plan.llm_confidence_score - plan.confidence_score) > 0.15 && (
                <div className="mt-2 flex items-start gap-1.5 rounded border border-warning/40 bg-warning/10 px-2 py-1.5 text-[10px] text-warning leading-snug">
                  <span aria-hidden="true">⚠</span>
                  <span>
                    LLM judge scored <strong>{(plan.llm_confidence_score * 100).toFixed(0)}%</strong> here — {Math.abs(plan.llm_confidence_score - plan.confidence_score) >= 0.5 ? 'large' : 'notable'} gap from the structural {Math.round(plan.confidence_score * 100)}%. Worth a closer look before approval.
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="md:col-span-2">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-2.5">Team Composition</span>
          <div className="flex flex-wrap gap-1.5">
            {plan.team_composition && Object.entries(plan.team_composition).length > 0 ? (
              Object.entries(plan.team_composition).map(([role, count]) => (
                <div key={role} className="flex items-center gap-1.5 bg-card border border-border px-2.5 py-1 rounded-full text-[11px] shadow-sm">
                  <div className="h-4 w-4 rounded-full bg-primary/60 border border-primary flex items-center justify-center text-[8px] font-extrabold text-primary">
                    {getRoleInitials(role)}
                  </div>
                  <span className="text-foreground truncate max-w-[155px]" title={role}>{role}</span>
                  <span className="bg-primary/10 text-primary font-extrabold px-1 rounded text-[9px]">
                    ×{count}
                  </span>
                </div>
              ))
            ) : (
              <span className="text-xs text-muted-foreground">No team data generated</span>
            )}
          </div>
        </div>
      </div>

      {/* Phases Checklist */}
      <div className="space-y-6">
        <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider border-b border-border/60 pb-2">Project Phases & Milestones</h3>
        {plan.phases && plan.phases.length > 0 ? (
          plan.phases.map((phase, i) => (
            <div key={phase.name || i} className="bg-card border border-border rounded-xl p-5 space-y-4 shadow-sm hover:border-border transition">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <h4 className="text-sm font-bold text-foreground">
                  📅 Phase {i + 1}: {phase.name}
                </h4>
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/30">
                  {phase.duration_weeks} weeks
                </span>
              </div>

              {/* Objectives */}
              {phase.objectives && phase.objectives.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Objectives</span>
                  <ul className="list-disc pl-4 space-y-1 text-xs text-muted-foreground">
                    {phase.objectives.map((obj, oIdx) => (
                      <li key={oIdx}>{obj}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Milestones Table */}
              {phase.milestones && phase.milestones.length > 0 && (
                <div className="space-y-2 pt-2">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Milestones</span>
                  <div className="overflow-x-auto rounded-lg border border-border">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-background border-b border-border text-muted-foreground font-semibold">
                          <th className="p-2.5 w-16 text-center">Week</th>
                          <th className="p-2.5">Milestone Checkpoint</th>
                          <th className="p-2.5">Key Deliverable</th>
                          <th className="p-2.5 w-32">Owner Role</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border bg-card/60">
                        {phase.milestones.map((m, mIdx) => (
                          <tr key={mIdx} className="hover:bg-card/20 text-foreground">
                            <td className="p-2.5 text-center font-mono font-bold text-primary">W{m.week}</td>
                            <td className="p-2.5 font-semibold text-foreground">{m.name}</td>
                            <td className="p-2.5 text-muted-foreground">{m.deliverable}</td>
                            <td className="p-2.5 text-muted-foreground truncate">{m.owner_role}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="text-xs text-muted-foreground">No phases generated</div>
        )}
      </div>

      {/* Risks Analysis */}
      {plan.risks && plan.risks.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider border-b border-border/60 pb-2">⚠️ Risks Assessment</h3>
          <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-background border-b border-border text-muted-foreground font-semibold">
                  <th className="p-3">Risk Description</th>
                  <th className="p-3 w-28 text-center">Likelihood</th>
                  <th className="p-3 w-28 text-center">Impact</th>
                  <th className="p-3">Mitigation Strategy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card/40">
                {plan.risks.map((r, idx) => (
                  <tr key={idx} className="hover:bg-card/20 text-muted-foreground">
                    <td className="p-3 font-medium text-foreground">
                      {r.description}
                      {r.citation && (
                        <a 
                          href={`#cite-${r.citation}`} 
                          className="text-[9px] text-primary hover:text-primary font-black align-super ml-0.5" 
                          title={`Jump to citation: ${r.citation}`}
                        >
                          [{getCitationIndex(r.citation)}]
                        </a>
                      )}
                    </td>
                    <td className="p-3 text-center">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${getRiskBadgeColor(r.likelihood)}`}>
                        {r.likelihood}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${getRiskBadgeColor(r.impact)}`}>
                        {r.impact}
                      </span>
                    </td>
                    <td className="p-3 text-muted-foreground leading-relaxed">{r.mitigation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Self-Critique Reflection Notes */}
      {plan.reflection_notes && (
        <div className="bg-warning/10 border border-warning/20 rounded-xl p-5 space-y-2">
          <h4 className="text-xs font-bold text-warning uppercase tracking-wider flex items-center gap-2">
            <Award size={14} /> Agent Self-Reflection Note
          </h4>
          <p className="text-xs text-warning/80 leading-relaxed italic whitespace-pre-wrap">
            {plan.reflection_notes}
          </p>
        </div>
      )}

      {/* Sources & Citations Glossar */}
      {citationsList.length > 0 && (
        <div className="border border-border rounded-xl p-5 bg-background shadow-inner">
          <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-2 mb-3">
            Sources & RAG Citations
          </h4>
          <ol className="list-decimal pl-5 space-y-2 text-xs text-muted-foreground">
            {citationsList.map((citation) => (
              <li key={citation} id={`cite-${citation}`} className="scroll-mt-24">
                <span className="font-mono text-foreground font-bold block">{citation}</span>
                <span className="text-[10px] text-muted-foreground block mt-0.5">Retrieved from engineering knowledge store</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};
