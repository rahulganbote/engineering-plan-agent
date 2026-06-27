import React from 'react';
import { AlertCircle, Target, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

interface SuccessCriterion {
  metric: string;
  target_value: string;
  measurement_method: string;
}

interface PoCOutput {
  poc_hypothesis?: string;
  scope_in?: string[];
  scope_out?: string[];
  duration_weeks?: number;
  success_criteria?: SuccessCriterion[];
  team_size?: number;
  risk_if_poc_fails?: string;
}

interface PoCTabProps {
  pocData: unknown;
}

export const PoCTab: React.FC<PoCTabProps> = ({ pocData }) => {
  let poc: PoCOutput | null = null;
  if (pocData) {
    if (typeof pocData === 'string') {
      try {
        poc = JSON.parse(pocData) as PoCOutput;
      } catch {
        poc = null;
      }
    } else {
      poc = pocData as PoCOutput;
    }
  }

  if (!poc || (!poc.poc_hypothesis && !poc.success_criteria)) {
    return (
      <div className="p-6 bg-card border border-border rounded-xl text-center space-y-3">
        <AlertCircle className="mx-auto text-muted-foreground" size={32} />
        <h4 className="text-sm font-bold text-foreground">PoC Scope Plan Unavailable</h4>
        <p className="text-xs text-muted-foreground max-w-md mx-auto">
          The Proof of Concept structure could not be parsed. Below is the raw data:
        </p>
        <pre className="p-4 bg-background rounded text-left font-mono text-[10px] text-muted-foreground overflow-x-auto whitespace-pre-wrap max-h-60">
          {typeof pocData === 'string' ? pocData : JSON.stringify(pocData, null, 2)}
        </pre>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in text-foreground">
      {/* Hypothesis Statement Header Card */}
      {poc.poc_hypothesis && (
        <div className="bg-card border border-border rounded-xl p-5 space-y-2 shadow-sm">
          <h4 className="text-xs font-bold text-primary uppercase tracking-wider flex items-center gap-2">
            <Target size={14} /> PoC Validation Hypothesis (Riskiest Assumption)
          </h4>
          <p className="text-sm text-foreground leading-relaxed font-semibold italic">
            "{poc.poc_hypothesis}"
          </p>
        </div>
      )}

      {/* Metrics Block */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-background border border-border p-6 rounded-xl shadow-inner">
        <div>
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-1">PoC Duration</span>
          <span className="text-xl font-black text-primary">{poc.duration_weeks || '—'} weeks</span>
        </div>
        <div>
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-1">Target Team Size</span>
          <span className="text-xl font-black text-primary">{poc.team_size || '—'} resources</span>
        </div>
      </div>

      {/* Scope Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Scope In */}
        <div className="bg-card border border-border rounded-xl p-5 space-y-3 shadow-sm">
          <h4 className="text-xs font-bold text-success uppercase tracking-wider flex items-center gap-1.5 border-b border-border pb-2">
            <CheckCircle2 size={14} className="text-success" /> Validation Scope In
          </h4>
          <ul className="space-y-2 text-xs text-muted-foreground">
            {poc.scope_in && poc.scope_in.length > 0 ? (
              poc.scope_in.map((item, idx) => (
                <li key={idx} className="flex gap-2 items-start leading-relaxed">
                  <span className="text-success shrink-0 select-none mt-0.5">✓</span>
                  <span>{item}</span>
                </li>
              ))
            ) : (
              <span className="text-muted-foreground italic block">No items defined</span>
            )}
          </ul>
        </div>

        {/* Scope Out */}
        <div className="bg-card border border-border rounded-xl p-5 space-y-3 shadow-sm">
          <h4 className="text-xs font-bold text-danger uppercase tracking-wider flex items-center gap-1.5 border-b border-border pb-2">
            <XCircle size={14} className="text-danger" /> Out of Scope (Deferred)
          </h4>
          <ul className="space-y-2 text-xs text-muted-foreground">
            {poc.scope_out && poc.scope_out.length > 0 ? (
              poc.scope_out.map((item, idx) => (
                <li key={idx} className="flex gap-2 items-start leading-relaxed text-muted-foreground">
                  <span className="text-danger shrink-0 select-none mt-0.5">✗</span>
                  <span>{item}</span>
                </li>
              ))
            ) : (
              <span className="text-muted-foreground italic block">No items defined</span>
            )}
          </ul>
        </div>
      </div>

      {/* Success Criteria */}
      {poc.success_criteria && poc.success_criteria.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider border-b border-border/60 pb-2">Success Criteria Matrix</h3>
          <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-background border-b border-border text-muted-foreground font-semibold">
                  <th className="p-3">Success Metric Indicator</th>
                  <th className="p-3 w-36 text-center">Target Threshold</th>
                  <th className="p-3">Measurement Methodology</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card/40">
                {poc.success_criteria.map((c, idx) => (
                  <tr key={idx} className="hover:bg-card/20 text-muted-foreground">
                    <td className="p-3 font-semibold text-foreground">{c.metric}</td>
                    <td className="p-3 text-center">
                      <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-primary/10 text-primary border border-primary/30">
                        {c.target_value}
                      </span>
                    </td>
                    <td className="p-3 text-muted-foreground leading-relaxed">{c.measurement_method}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Risk if PoC fails */}
      {poc.risk_if_poc_fails && (
        <div className="bg-danger/10 border border-danger/20 rounded-xl p-5 space-y-2">
          <h4 className="text-xs font-bold text-danger uppercase tracking-wider flex items-center gap-2">
            <AlertTriangle size={14} className="text-danger" /> Business Consequence If PoC Fails
          </h4>
          <p className="text-xs text-danger/80 leading-relaxed italic">
            "{poc.risk_if_poc_fails}"
          </p>
        </div>
      )}
    </div>
  );
};
