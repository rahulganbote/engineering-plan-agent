import React from 'react';
import { AlertCircle, Star, Sparkles, DollarSign } from 'lucide-react';
import { useWorkspace } from '../context/WorkspaceContext';
import { IntegrationNotConfigured } from './IntegrationNotConfigured';

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
  // Detect whether GitHub velocity signal ran authenticated. The backend emits
  // tool_call_started with authenticated=true|false on every GitHub call. If we
  // see at least one such event with authenticated=false, GITHUB_TOKEN was not
  // configured and the call hit the 60 req/hour unauthenticated rate limit.
  const { logs } = useWorkspace();
  const githubUnauthenticated = logs.some((l) => {
    const event = (l as unknown) as Record<string, unknown>;
    const payload = (l.payload as Record<string, unknown> | undefined) || {};
    const isToolStart = event.type === 'tool_call_started';
    const tool = event.tool ?? payload.tool;
    const auth = event.authenticated ?? payload.authenticated;
    return isToolStart && tool === 'github' && auth === false;
  });

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
      <div className="p-6 bg-card border border-border rounded-xl text-center space-y-3">
        <AlertCircle className="mx-auto text-muted-foreground" size={32} />
        <h4 className="text-sm font-bold text-foreground">Tech Stack Matrix Unavailable</h4>
        <p className="text-xs text-muted-foreground max-w-md mx-auto">
          The technology stack recommendations structure could not be parsed. Below is the raw data:
        </p>
        <pre className="p-4 bg-background rounded text-left font-mono text-[10px] text-muted-foreground overflow-x-auto whitespace-pre-wrap max-h-60">
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
      <div className="flex gap-0.5 text-primary">
        {[1, 2, 3, 4, 5].map((s) => (
          <Star 
            key={s} 
            size={10} 
            className={s <= rating ? 'fill-primary stroke-primary' : 'text-foreground'} 
          />
        ))}
      </div>
    );
  };

  const getRiskColor = (level: string) => {
    const l = level.toLowerCase();
    if (l === 'high' || l === 'critical' || l === 'red') {
      return 'text-danger bg-danger/40 border-danger/30';
    }
    if (l === 'medium' || l === 'amber') {
      return 'text-warning bg-warning/40 border-warning/30';
    }
    return 'text-success bg-green-950/40 border-green-900/30';
  };

  return (
    <div className="space-y-8 animate-fade-in text-foreground">
      {/* GitHub fallback hint - surfaces when the Tech Stack agent's GitHub
          velocity-signal call ran unauthenticated (no GITHUB_TOKEN configured).
          The tool still works in unauthenticated mode, just at the 60 req/hour
          GitHub rate limit instead of 5,000 - so this is a soft hint. */}
      {githubUnauthenticated && (
        <IntegrationNotConfigured
          title="GitHub velocity signal ran unauthenticated"
          envVars={["GITHUB_TOKEN"]}
          description="The Tech Stack agent fetches GitHub repo velocity (stars/week, issue close rate) to inform its recommendations. Without a token, this falls back to GitHub's 60 req/hour anonymous rate limit - fine for demos, too low for repeated runs."
          docsAnchor="#L80-L81"
        />
      )}

      {/* Recommended option and rationale */}
      {rec && (
        <div className="bg-gradient-to-r from-primary/20 to-card border border-primary/40 rounded-xl p-5 space-y-3 shadow-md relative overflow-hidden">
          <div className="absolute right-0 top-0 translate-x-3 -translate-y-3 bg-primary/10 h-24 w-24 rounded-full blur-xl" />
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-primary" />
            <h4 className="text-xs font-bold text-primary uppercase tracking-wider">Recommended Architecture Stack</h4>
          </div>
          <span className="text-xl font-black text-foreground bg-background px-3 py-1 rounded-lg border border-border inline-block">
            {rec}
          </span>
          {stack.recommendation_rationale && (
            <p className="text-xs text-muted-foreground leading-relaxed border-t border-border/60 pt-3">
              <strong>Rationale:</strong> {stack.recommendation_rationale}
            </p>
          )}
        </div>
      )}

      {/* Side-by-side Options Comparison */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider border-b border-border/60 pb-2">Technology Stack Matrix</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {options.map((opt, idx) => {
            const isRec = opt.name === rec;
            return (
              <div 
                key={idx} 
                className={`rounded-xl p-5 flex flex-col justify-between space-y-4 border transition ${
                  isRec 
                    ? 'bg-card/90 border-primary/50 shadow-[0_0_15px_rgba(99,102,241,0.1)]' 
                    : 'bg-card border-border hover:border-border'
                }`}
              >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-foreground">
                      {opt.name}
                      {opt.citation && (
                        <a 
                          href={`#cite-${opt.citation}`} 
                          className="text-[9px] text-primary hover:text-primary font-black align-super ml-0.5"
                          title={`Citation: ${opt.citation}`}
                        >
                          [{getCitationIndex(opt.citation)}]
                        </a>
                      )}
                    </h4>
                    <span className="text-[10px] text-muted-foreground font-mono block">Option {idx + 1}</span>
                  </div>
                  {isRec && (
                    <span className="px-2 py-0.5 bg-primary/10 text-primary border border-primary/30 text-[9px] font-extrabold uppercase rounded-full">
                      ★ Recommended
                    </span>
                  )}
                </div>

                {/* Layer mapping */}
                {opt.components && Object.entries(opt.components).length > 0 && (
                  <div className="space-y-2 bg-background/40 p-3 rounded-lg border border-border">
                    <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider block">Stack Layers</span>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      {Object.entries(opt.components).map(([layer, tech]) => (
                        <div key={layer} className="flex flex-col">
                          <span className="text-muted-foreground capitalize">{layer}</span>
                          <span className="text-foreground font-semibold truncate" title={tech}>{tech}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Ratings */}
                <div className="grid grid-cols-2 gap-4 border-b border-border/60 pb-3 text-[11px]">
                  <div className="space-y-1">
                    <span className="text-muted-foreground block">Scalability Rating</span>
                    {getRatingStars(opt.scalability_rating)}
                  </div>
                  <div className="space-y-1">
                    <span className="text-muted-foreground block">Team Familiarity</span>
                    {getRatingStars(opt.team_familiarity_rating)}
                  </div>
                </div>

                {/* Cost and Risk info */}
                <div className="flex items-center justify-between text-xs pt-1">
                  <div className="flex items-center gap-1 text-foreground">
                    <DollarSign size={14} className="text-muted-foreground" />
                    <span>Cost Estimate:</span>
                    <strong className="text-foreground font-mono">${opt.estimated_monthly_cost_usd.toLocaleString()}/mo</strong>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Risk:</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${getRiskColor(opt.integration_risk)}`}>
                      {opt.integration_risk}
                    </span>
                  </div>
                </div>

                {/* Pros and Cons */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-border">
                  {/* Pros */}
                  <div className="space-y-1.5">
                    <span className="text-[9px] font-bold text-success uppercase tracking-wider block">Pros</span>
                    <ul className="space-y-1 text-[11px] text-muted-foreground">
                      {opt.pros && opt.pros.map((p, pIdx) => (
                        <li key={pIdx} className="flex gap-1 items-start leading-relaxed">
                          <span className="text-success select-none">✓</span>
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  {/* Cons */}
                  <div className="space-y-1.5">
                    <span className="text-[9px] font-bold text-danger uppercase tracking-wider block">Cons</span>
                    <ul className="space-y-1 text-[11px] text-muted-foreground">
                      {opt.cons && opt.cons.map((c, cIdx) => (
                        <li key={cIdx} className="flex gap-1 items-start leading-relaxed">
                          <span className="text-danger select-none">✗</span>
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
