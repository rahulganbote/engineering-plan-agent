import React from 'react';
import { AlertCircle, Zap, GitCommit } from 'lucide-react';

interface SprintRow {
  sprint: number;
  week_range: string;
  deliverables: string[];
  team_members: string[];
  effort_days: number;
}

interface ScheduleOutput {
  sprints?: SprintRow[];
  total_effort_days?: number;
  critical_path?: string[];
  buffer_weeks?: number;
  comparable_projects?: string[];
  confidence_score?: number;
}

interface ScheduleTabProps {
  scheduleData: unknown;
}

export const ScheduleTab: React.FC<ScheduleTabProps> = ({ scheduleData }) => {
  let sched: ScheduleOutput | null = null;
  if (scheduleData) {
    if (typeof scheduleData === 'string') {
      try {
        sched = JSON.parse(scheduleData) as ScheduleOutput;
      } catch {
        sched = null;
      }
    } else {
      sched = scheduleData as ScheduleOutput;
    }
  }

  if (!sched || (!sched.sprints && !sched.critical_path)) {
    return (
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl text-center space-y-3">
        <AlertCircle className="mx-auto text-slate-500" size={32} />
        <h4 className="text-sm font-bold text-slate-300">Schedule Content Unavailable</h4>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          The sprint schedule structure could not be parsed. Below is the raw data:
        </p>
        <pre className="p-4 bg-slate-950 rounded text-left font-mono text-[10px] text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-60">
          {typeof scheduleData === 'string' ? scheduleData : JSON.stringify(scheduleData, null, 2)}
        </pre>
      </div>
    );
  }

  const getRoleInitials = (role: string) => {
    return role
      .split(' ')
      .map((w) => w[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <div className="space-y-8 animate-fade-in text-slate-100">
      {/* Overview Block */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-950 border border-slate-850 p-6 rounded-xl shadow-inner">
        <div>
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Total Effort</span>
          <span className="text-2xl font-black text-indigo-400">
            {sched.total_effort_days !== undefined ? `${sched.total_effort_days.toFixed(1)} days` : '—'}
          </span>
        </div>
        <div>
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Buffer Allocation</span>
          <span className="text-2xl font-black text-indigo-400">{sched.buffer_weeks || 0} weeks</span>
        </div>
        {sched.confidence_score !== undefined && (
          <div>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">Estimation Confidence</span>
            <span className="text-2xl font-black text-indigo-400">{(sched.confidence_score * 100).toFixed(0)}%</span>
          </div>
        )}
      </div>

      {/* Sprints Table */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/60 pb-2">Sprint Backlog Allocation</h3>
        {sched.sprints && sched.sprints.length > 0 ? (
          <div className="overflow-x-auto rounded-xl border border-slate-850 bg-slate-900 shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-950 border-b border-slate-850 text-slate-400 font-semibold">
                  <th className="p-3 w-20 text-center">Sprint</th>
                  <th className="p-3 w-28 text-center">Weeks</th>
                  <th className="p-3">Deliverables & Targets</th>
                  <th className="p-3 w-44">Allocated Resources</th>
                  <th className="p-3 w-24 text-center">Effort</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850 bg-slate-900/40">
                {sched.sprints.map((s, idx) => (
                  <tr key={idx} className="hover:bg-slate-850/20 text-slate-350 align-top">
                    <td className="p-3 text-center font-bold text-indigo-400 font-mono">S{s.sprint}</td>
                    <td className="p-3 text-center text-slate-300 font-medium font-mono">{s.week_range}</td>
                    <td className="p-3 space-y-1">
                      <ul className="list-disc pl-4 space-y-1 text-slate-300">
                        {s.deliverables && s.deliverables.map((d, dIdx) => (
                          <li key={dIdx} className="leading-relaxed">{d}</li>
                        ))}
                      </ul>
                    </td>
                    <td className="p-3">
                      <div className="flex flex-wrap gap-1">
                        {s.team_members && s.team_members.length > 0 ? (
                          s.team_members.map((member, mIdx) => (
                            <div 
                              key={mIdx} 
                              className="flex items-center gap-1 bg-slate-950 border border-slate-800 px-1.5 py-0.5 rounded text-[10px] text-slate-300"
                              title={member}
                            >
                              <div className="h-3.5 w-3.5 rounded bg-indigo-900/60 flex items-center justify-center text-[7px] font-black text-indigo-300">
                                {getRoleInitials(member)}
                              </div>
                              <span className="truncate max-w-[80px]">{member}</span>
                            </div>
                          ))
                        ) : (
                          <span className="text-slate-600 italic text-[10px]">Unassigned</span>
                        )}
                      </div>
                    </td>
                    <td className="p-3 text-center text-slate-300 font-bold font-mono">{s.effort_days}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-slate-500">No sprints defined</div>
        )}
      </div>

      {/* Critical Path badge flow */}
      {sched.critical_path && sched.critical_path.length > 0 && (
        <div className="space-y-4 border border-slate-850 rounded-xl p-5 bg-slate-900/40">
          <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-2">
            <Zap size={14} className="text-indigo-400" /> System Critical Path Sequence
          </h4>
          <div className="flex flex-wrap items-center gap-2 pt-2">
            {sched.critical_path.map((step, idx) => (
              <React.Fragment key={idx}>
                {idx > 0 && <span className="text-slate-600 font-bold text-xs">→</span>}
                <div className="flex items-center gap-1.5 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-200 shadow-sm">
                  <span className="h-2 w-2 rounded-full bg-indigo-500" />
                  <span>{step}</span>
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Comparable projects */}
      {sched.comparable_projects && sched.comparable_projects.length > 0 && (
        <div className="border border-slate-850 rounded-xl p-5 bg-slate-950 shadow-inner">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-850 pb-2 mb-3">
            Comparable Historical Projects (RAG Calibration)
          </h4>
          <div className="flex flex-wrap gap-2">
            {sched.comparable_projects.map((proj, idx) => (
              <div key={idx} className="flex items-center gap-1 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-md text-xs text-slate-300 font-mono shadow-sm">
                <GitCommit size={12} className="text-slate-500" />
                <span>{proj}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
