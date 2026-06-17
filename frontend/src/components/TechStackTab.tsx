import React from 'react';
import { AlertCircle, Star, Sparkles, DollarSign } from 'lucide-react';

interface StackOption {
  name: string;
  components: Record<string, string>;
  scalability_rating: number;
  team_familiarity_rating: number;
  integration_risk: string;
  estimated_monthly_cost_usd: number;
  pros: string[];
  cons: string[];
  citation: string;
}

interface TechStackOutput {
  options?: StackOption[];
  recommended_option?: string;
  recommendation_rationale?: string;
}

interface TechStackTabProps {
  techStackData: unknown;
}

export const TechStackTab: React.FC<TechStackTabProps> = ({ techStackData }) => {
  let stack: TechStackOutput | null = null;
  if (techStackData) {
    if (typeof techStackData === 'string') {
      try {
        stack = JSON.parse(techStackData) as TechStackOutput;
      } catch {
        stack = null;
      }
    } else {
      stack = techStackData as TechStackOutput;
    }
  }

  if (!stack || (!stack.options && !stack.recommended_option)) {
    return (
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl text-center space-y-3">
        <AlertCircle className="mx-auto text-slate-500" size={32} />
        <h4 className="text-sm font-bold text-slate-300">Tech Stack Matrix Unavailable</h4>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          The technology stack recommendations structure could not be parsed. Below is the raw data:
        </p>
        <pre className="p-4 bg-slate-950 rounded text-left font-mono text-[10px] text-slate-400 overflow-x-auto whitespace-pre-wrap max-h-60">
          {typeof techStackData === 'string' ? techStackData : JSON.stringify(techStackData, null, 2)}
        </pre>
      </div>
    );
  }

  const rec = stack.recommended_option || '';
  const options = stack.options || [];

  // Gather unique citations for footnotes
  const citationsList = Array.from(
    new Set(
      options
        .map((o) => o.citation)
        .filter((c): c is string => typeof c === 'string' && c.trim().length > 0)
    )
  );

  const getCitationIndex = (citation: string) => {
    return citationsList.indexOf(citation) + 1;
  };

  const getRatingStars = (rating: number) => {
    return (
      <div className="flex gap-0.5 text-indigo-400">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star 
            key={s} 
            size={10} 
            className={s <= rating ? 'fill-indigo-400 stroke-indigo-400' : 'text-slate-800'} 
          />
        ))}
      </div>
    );
  };

  const getRiskColor = (level: string) => {
    const l = level.toLowerCase();
    if (l === 'high' || l === 'critical' || l === 'red') {
      return 'text-red-400 bg-red-950/40 border-red-900/30';
    }
    if (l === 'medium' || l === 'amber') {
      return 'text-amber-400 bg-amber-950/40 border-amber-900/30';
    }
    return 'text-green-400 bg-green-950/40 border-green-900/30';
  };

  return (
    <div className="space-y-8 animate-fade-in text-slate-100">
      {/* Recommended option and rationale */}
      {rec && (
        <div className="bg-gradient-to-r from-indigo-950/20 to-slate-900 border border-indigo-900/40 rounded-xl p-5 space-y-3 shadow-md relative overflow-hidden">
          <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 bg-indigo-500/10 h-24 w-24 rounded-full blur-xl" />
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-indigo-400" />
            <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-wider">Recommended Architecture Stack</h4>
          </div>
          <span className="text-xl font-black text-slate-100 bg-slate-950 px-3 py-1 rounded-lg border border-slate-850 inline-block">
            {rec}
          </span>
          {stack.recommendation_rationale && (
            <p className="text-xs text-slate-350 leading-relaxed border-t border-slate-850/60 pt-3">
              <strong>Rationale:</strong> {stack.recommendation_rationale}
            </p>
          )}
        </div>
      )}

      {/* Side-by-side Options Comparison */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800/60 pb-2">Technology Stack Matrix</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {options.map((opt, idx) => {
            const isRec = opt.name === rec;
            return (
              <div 
                key={idx} 
                className={`rounded-xl p-5 flex flex-col justify-between space-y-4 border transition ${
                  isRec 
                    ? 'bg-slate-900/90 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.1)]' 
                    : 'bg-slate-900 border-slate-850 hover:border-slate-800'
                }`}
              >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-slate-850 pb-3">
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-slate-200">
                      {opt.name}
                      {opt.citation && (
                        <a 
                          href={`#cite-${opt.citation}`} 
                          className="text-[9px] text-indigo-400 hover:text-indigo-300 font-black align-super ml-0.5"
                          title={`Citation: ${opt.citation}`}
                        >
                          [{getCitationIndex(opt.citation)}]
                        </a>
                      )}
                    </h4>
                    <span className="text-[10px] text-slate-500 font-mono block">Option {idx + 1}</span>
                  </div>
                  {isRec && (
                    <span className="px-2 py-0.5 bg-indigo-950 text-indigo-400 border border-indigo-800/30 text-[9px] font-extrabold uppercase rounded-full">
                      ★ Recommended
                    </span>
                  )}
                </div>

                {/* Layer mapping */}
                {opt.components && Object.entries(opt.components).length > 0 && (
                  <div className="space-y-2 bg-slate-950/40 p-3 rounded-lg border border-slate-850">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block">Stack Layers</span>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      {Object.entries(opt.components).map(([layer, tech]) => (
                        <div key={layer} className="flex flex-col">
                          <span className="text-slate-500 capitalize">{layer}</span>
                          <span className="text-slate-300 font-semibold truncate" title={tech}>{tech}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Ratings */}
                <div className="grid grid-cols-2 gap-4 border-b border-slate-850/60 pb-3 text-[11px]">
                  <div className="space-y-1">
                    <span className="text-slate-500 block">Scalability Rating</span>
                    {getRatingStars(opt.scalability_rating)}
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-500 block">Team Familiarity</span>
                    {getRatingStars(opt.team_familiarity_rating)}
                  </div>
                </div>

                {/* Cost and Risk info */}
                <div className="flex items-center justify-between text-xs pt-1">
                  <div className="flex items-center gap-1 text-slate-300">
                    <DollarSign size={14} className="text-slate-500" />
                    <span>Cost Estimate:</span>
                    <strong className="text-slate-100 font-mono">${opt.estimated_monthly_cost_usd.toLocaleString()}/mo</strong>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-500">Risk:</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${getRiskColor(opt.integration_risk)}`}>
                      {opt.integration_risk}
                    </span>
                  </div>
                </div>

                {/* Pros and Cons */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-slate-850">
                  {/* Pros */}
                  <div className="space-y-1.5">
                    <span className="text-[9px] font-bold text-green-400 uppercase tracking-wider block">Pros</span>
                    <ul className="space-y-1 text-[11px] text-slate-350">
                      {opt.pros && opt.pros.map((p, pIdx) => (
                        <li key={pIdx} className="flex gap-1 items-start leading-relaxed">
                          <span className="text-green-500 select-none">✓</span>
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  {/* Cons */}
                  <div className="space-y-1.5">
                    <span className="text-[9px] font-bold text-red-400 uppercase tracking-wider block">Cons</span>
                    <ul className="space-y-1 text-[11px] text-slate-355">
                      {opt.cons && opt.cons.map((c, cIdx) => (
                        <li key={cIdx} className="flex gap-1 items-start leading-relaxed">
                          <span className="text-red-500 select-none">✗</span>
                          <span>{c}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

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
