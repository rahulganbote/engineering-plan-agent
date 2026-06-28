import React, { useState } from 'react';
import { ShieldCheck, Cpu, GitPullRequest, Milestone, Sparkles, Info } from 'lucide-react';

interface IngestionLandingProps {
  selectedFile: File | null;
  onFileSelect: (file: File) => void;
  onRemoveFile: () => void;
  onTrigger: () => void;
  isLoading: boolean;
  isAuthenticated: boolean;
  onLogin: () => void;
}

export const IngestionLanding: React.FC<IngestionLandingProps> = () => {
  const [activeNode, setActiveNode] = useState<string | null>(null);

  // Node details for interactive flowchart.
  //
  // Color semantics - traffic-light progression mirroring the data flow:
  //   🔴 Error/Failures (API errors, BudgetBreachedError, timeouts, etc)
  //   💜 Orchestrator + Specialists (AI agents doing the work - share token)
  //   🟡 Security Validator (quaility check + blocks unsafe input)+ Critic Reviewer (judges + may loop back for revision) 
  //   🟢 Manager (HITL) Gate (approves and ships)
  //
  // The two AI-agent nodes intentionally share --color-ai-spark (Electric
  // Purple) to visually group them as one agent family: hub + spokes.
  const pipelineNodes = [
    {
      id: 'security',
      label: 'Security Validator',
      desc: 'Performs file size scans, prompt injection assessment, and filters/redacts PII patterns.',
      icon: <ShieldCheck size={20} className="text-warning" />,
      color: 'border-warning/30 text-warning bg-warning/10',
      activeColor: 'ring-warning/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]',
    },
    {
      id: 'orchestrator',
      label: 'Orchestrator',
      desc: 'Parses the BRD sections, evaluates structure completeness, and splits tasks for specialists.',
      icon: <Cpu size={20} className="text-ai-spark" />,
      color: 'border-ai-spark/30 text-ai-spark bg-ai-spark/10',
      activeColor: 'ring-ai-spark/50 shadow-[0_0_15px_rgba(139,92,246,0.3)]',
    },
    {
      id: 'specialists',
      label: '5 Specialists (AI Agent)',
      desc: 'Parallel agents: Plan Generator, Schedule Estimator, Solution Architect, PoC Engineer, and Tech Stack Matcher.',
      icon: <Sparkles size={20} className="text-ai-spark" />,
      color: 'border-ai-spark/30 text-ai-spark bg-ai-spark/10',
      activeColor: 'ring-ai-spark/50 shadow-[0_0_15px_rgba(139,92,246,0.3)]',
    },
    {
      id: 'critic',
      label: 'Critic Reviewer',
      desc: 'Grades the outputs on 4 quality dimensions (1.0 - 5.0 score) and initiates revision loops if needed.',
      icon: <GitPullRequest size={20} className="text-warning" />,
      color: 'border-warning/30 text-warning bg-warning/10',
      activeColor: 'ring-warning/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]',
    },
    {
      id: 'manager',
      label: 'Manager (HITL) Gate',
      desc: 'Pauses execution to obtain engineering manager approval before exporting to Google Sheets and Jira.',
      icon: <Milestone size={20} className="text-success" />,
      color: 'border-success/30 text-success bg-success/10',
      activeColor: 'ring-success/50 shadow-[0_0_15px_rgba(16,185,129,0.3)]',
    },
  ];



  return (
    <div className="space-y-8 max-w-6xl mx-auto py-4">
      {/* Welcome & Subtitle Section */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-foreground">
          Transform BRDs into Implementation Plans in Minutes
        </h2>
        <p className="text-sm text-muted-foreground max-w-3xl leading-relaxed">
          EM Copilot is a multi-agent AI system that transforms raw Business Requirements Documents (BRDs) into an audit-ready engineering plan package presented to you for review. Upon approval, it pushes the artifacts into Jira.
        </p>
        {/* Runtime hint moved next to the Generate Engineering Plan button in
            the sidebar - that's the action surface where this anticipation
            actually matters for the user. */}
      </div>

      {/* System Architecture Diagram - full width, compact above-the-fold layout */}
      <div className="rounded-xl border border-border bg-card/60 p-5 space-y-4 shadow-md">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-bold text-foreground">System Architecture</h3>
        </div>

        {/* Interactive Flow Visualizer - compact (tooltip replaces the old 96px detail box) */}
        <div className="flex flex-col md:flex-row gap-4 items-center justify-center pt-2 pb-6 md:pb-5 bg-background/80 rounded-xl px-3 border border-border relative">
          {/* Spoke layout - left column */}
          <div className="flex flex-col gap-2.5 w-full md:w-5/12 z-10">
            {pipelineNodes.slice(0, 3).map((node) => (
              <div
                key={node.id}
                className="relative group"
                onMouseEnter={() => setActiveNode(node.id)}
                onMouseLeave={() => setActiveNode(null)}
                onClick={() => setActiveNode(activeNode === node.id ? null : node.id)}
              >
                <div
                  className={`p-2.5 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-border'}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {node.icon}
                      <span className="text-xs font-bold">{node.label}</span>
                    </div>
                    <Info size={12} className="text-muted-foreground/60 group-hover:text-foreground transition-colors shrink-0 ml-2" />
                  </div>
                </div>

                {/* Hover tooltip - anchored above the card, fades in */}
                {activeNode === node.id && (
                  <div
                    role="tooltip"
                    className="absolute z-30 left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 p-3
                               bg-background border border-border rounded-lg shadow-2xl
                               pointer-events-none animate-in fade-in zoom-in-95 duration-150"
                  >
                    <div className="flex items-center gap-2 mb-1.5 pb-1.5 border-b border-border">
                      {node.icon}
                      <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">{node.label}</h4>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">{node.desc}</p>
                    {/* Tooltip arrow */}
                    <span className="absolute top-full left-1/2 -translate-x-1/2 w-3 h-3 -mt-1.5 rotate-45 bg-background border-r border-b border-border" />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Central "State Loop" loop visualizer */}
          <div className="flex flex-col md:flex-row items-center justify-center gap-2 shrink-0 my-2 md:my-0">
            {/* Left to Center connection */}
            <div className="flex flex-col md:flex-row items-center gap-1">
              <div className="h-4 w-0.5 md:h-0.5 md:w-8 bg-gradient-to-b md:bg-gradient-to-r from-ai-spark to-primary" />
              <span className="text-[10px] text-primary select-none transform rotate-90 md:rotate-0">▶</span>
            </div>

            {/* Circular Loop Graphic container */}
            <div className="relative flex items-center justify-center w-28 h-20 shrink-0 select-none">
              {/* Loop arrows (SVG) */}
              <svg className="absolute inset-0 w-full h-full text-warning/45 dark:text-warning/35 animate-[spin_6s_linear_infinite]" viewBox="0 0 100 100" fill="none">
                {/* Loop path */}
                <path
                  d="M 50,15 A 35,35 0 1,1 49.9,15"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeDasharray="5, 3"
                />
                {/* Arrow heads pointing clockwise */}
                <path d="M 50,15 L 44,9 L 44,21 Z" fill="currentColor" />
                <path d="M 50,85 L 56,91 L 56,79 Z" fill="currentColor" />
              </svg>
              
              <span className="text-[11px] font-bold px-3 py-1.5 bg-card border border-border rounded-full text-muted-foreground text-center select-none font-mono shadow-sm z-10">
                State Loop
              </span>
            </div>

            {/* Center to Right connection */}
            <div className="flex flex-col md:flex-row items-center gap-1">
              <div className="h-4 w-0.5 md:h-0.5 md:w-8 bg-gradient-to-b md:bg-gradient-to-r from-warning to-success" />
              <span className="text-[10px] text-success select-none transform rotate-90 md:rotate-0">▶</span>
            </div>
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-2.5 w-full md:w-5/12 z-10">
            {pipelineNodes.slice(3).map((node) => (
              <div
                key={node.id}
                className="relative group"
                onMouseEnter={() => setActiveNode(node.id)}
                onMouseLeave={() => setActiveNode(null)}
                onClick={() => setActiveNode(activeNode === node.id ? null : node.id)}
              >
                <div
                  className={`p-2.5 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-border'}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {node.icon}
                      <span className="text-xs font-bold">{node.label}</span>
                    </div>
                    <Info size={12} className="text-muted-foreground/60 group-hover:text-foreground transition-colors shrink-0 ml-2" />
                  </div>
                </div>

                {activeNode === node.id && (
                  <div
                    role="tooltip"
                    className="absolute z-30 left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 p-3
                               bg-background border border-border rounded-lg shadow-2xl
                               pointer-events-none animate-in fade-in zoom-in-95 duration-150"
                  >
                    <div className="flex items-center gap-2 mb-1.5 pb-1.5 border-b border-border">
                      {node.icon}
                      <h4 className="text-xs font-bold text-foreground uppercase tracking-wide">{node.label}</h4>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">{node.desc}</p>
                    <span className="absolute top-full left-1/2 -translate-x-1/2 w-3 h-3 -mt-1.5 rotate-45 bg-background border-r border-b border-border" />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Helper text placed absolutely inside the diagram box */}
          <span className="text-[10px] text-muted-foreground/60 italic select-none absolute bottom-1.5 right-3">
            Hover each step for execution details
          </span>
        </div>
      </div>
    </div>
  );
};
