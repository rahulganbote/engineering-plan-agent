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
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl text-center space-y-3">
        <AlertCircle className="mx-auto text-slate-500" size={32} />
        <h4 className="text-sm font-bold text-slate-300">Plan Content Unavailable</h4>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          The engineering plan structure could not be parsed. Below is the raw data:
        </p>
        <pre className="p-4 bg-slate-950 rounded text-left font-mono text-[10px] text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-60">
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
      return 'bg-red-950/40 text-red-400 border border-red-900/30';
    }
    if (l === 'medium' || l === 'amber') {
      return 'bg-amber-950/40 text-amber-400 border border-amber-900/30';
    }
    return 'bg-green-950/40 text-green-400 border border-green-900/30';
  };

  return (
    <div className="space-y-8 animate-fade-in text-slate-100">
      {/* Overview Block */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-slate-950 border border-slate-850 p-6 rounded-xl shadow-inner">
        <div className="md:col-span-1 flex flex-col justify-between gap-4">
          <div>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Total Duration</span>
            <span className="text-2xl font-black text-indigo-400">{plan.total_duration_weeks || '—'} weeks</span>
          </div>
          {plan.confidence_score !== undefined && (
            <div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Plan Confidence</span>
              <span className="text-2xl font-black text-indigo-400">{(plan.confidence_score * 100).toFixed(0)}%</span>
            </div>
          )}
        </div>
        <div className="md:col-span-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-2.5">Team Composition</span>
          <div className="flex flex-wrap gap-1.5">
            {plan.team_composition && Object.entries(plan.team_composition).length > 0 ? (
              Object.entries(plan.team_composition).map(([role, count]) => (
                <div key={role} className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-full text-[11px] shadow-sm">
                  <div className="h-4 w-4 rounded-full bg-indigo-900/60 border border-indigo-700 flex items-center justify-center text-[8px] font-extrabold text-indigo-300">
                    {getRoleInitials(role)}
                  </div>
                  <span className="text-slate-300 truncate max-w-[155px]" title={role}>{role}</span>
                  <span className="bg-indigo-950 text-indigo-400 font-extrabold px-1 rounded text-[9px]">
                    ×{count}
                  </span>
                </div>
              ))
            ) : (
              <span className="text-xs text-slate-500">No team data generated</span>
            )}
          </div>
        </div>
      </div>

      {/* Phases Checklist */}
      <div className="space-y-6">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/60 pb-2">Project Phases & Milestones</h3>
        {plan.phases && plan.phases.length > 0 ? (
          plan.phases.map((phase, i) => (
            <div key={phase.name || i} className="bg-slate-900 border border-slate-850 rounded-xl p-5 space-y-4 shadow-sm hover:border-slate-800 transition">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h4 className="text-sm font-bold text-slate-200">
                  📅 Phase {i + 1}: {phase.name}
                </h4>
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-900/30">
                  {phase.duration_weeks} weeks
                </span>
              </div>

              {/* Objectives */}
              {phase.objectives && phase.objectives.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Objectives</span>
                  <ul className="list-disc pl-4 space-y-1 text-xs text-slate-400">
                    {phase.objectives.map((obj, oIdx) => (
                      <li key={oIdx}>{obj}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Milestones Table */}
              {phase.milestones && phase.milestones.length > 0 && (
                <div className="space-y-2 pt-2">
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Milestones</span>
                  <div className="overflow-x-auto rounded-lg border border-slate-850">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-slate-950 border-b border-slate-850 text-slate-400 font-semibold">
                          <th className="p-2.5 w-16 text-center">Week</th>
                          <th className="p-2.5">Milestone Checkpoint</th>
                          <th className="p-2.5">Key Deliverable</th>
                          <th className="p-2.5 w-32">Owner Role</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-850 bg-slate-900/60">
                        {phase.milestones.map((m, mIdx) => (
                          <tr key={mIdx} className="hover:bg-slate-850/20 text-slate-300">
                            <td className="p-2.5 text-center font-mono font-bold text-indigo-400">W{m.week}</td>
                            <td className="p-2.5 font-semibold text-slate-200">{m.name}</td>
                            <td className="p-2.5 text-slate-400">{m.deliverable}</td>
                            <td className="p-2.5 text-slate-400 truncate">{m.owner_role}</td>
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
          <div className="text-xs text-slate-500">No phases generated</div>
        )}
      </div>

      {/* Risks Analysis */}
      {plan.risks && plan.risks.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/60 pb-2">⚠️ Risks Assessment</h3>
          <div className="overflow-x-auto rounded-xl border border-slate-850 bg-slate-900 shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-950 border-b border-slate-850 text-slate-400 font-semibold">
                  <th className="p-3">Risk Description</th>
                  <th className="p-3 w-28 text-center">Likelihood</th>
                  <th className="p-3 w-28 text-center">Impact</th>
                  <th className="p-3">Mitigation Strategy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850 bg-slate-900/40">
                {plan.risks.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-850/20 text-slate-350">
                    <td className="p-3 font-medium text-slate-200">
                      {r.description}
                      {r.citation && (
                        <a 
                          href={`#cite-${r.citation}`} 
                          className="text-[9px] text-indigo-400 hover:text-indigo-300 font-black align-super ml-0.5" 
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
                    <td className="p-3 text-slate-400 leading-relaxed">{r.mitigation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Self-Critique Reflection Notes */}
      {plan.reflection_notes && (
        <div className="bg-amber-950/10 border border-amber-900/20 rounded-xl p-5 space-y-2">
          <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
            <Award size={14} /> Agent Self-Reflection Note
          </h4>
          <p className="text-xs text-amber-300/80 leading-relaxed italic whitespace-pre-wrap">
            {plan.reflection_notes}
          </p>
        </div>
      )}

      {/* Sources & Citations Glossar */}
      {citationsList.length > 0 && (
        <div className="border border-slate-850 rounded-xl p-5 bg-slate-950 shadow-inner">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-850 pb-2 mb-3">
            Sources & RAG Citations
          </h4>
          <ol className="list-decimal pl-5 space-y-2 text-xs text-slate-400">
            {citationsList.map((citation) => (
              <li key={citation} id={`cite-${citation}`} className="scroll-mt-24">
                <span className="font-mono text-slate-300 font-bold block">{citation}</span>
                <span className="text-[10px] text-slate-500 block mt-0.5">Retrieved from engineering knowledge store</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};
