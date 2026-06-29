import React, { useState, useEffect, useRef } from 'react';
import { ShieldCheck, Cpu, GitPullRequest, Milestone, Sparkles, Info, Wrench, BookOpen } from 'lucide-react';

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
  const containerRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<{
    x1: number; y1: number;
    x2: number; y2: number;
    mx1: number; my1: number;
    mx2: number;
  } | null>(null);

  useEffect(() => {
    const updateCoords = () => {
      const container = containerRef.current;
      const specialistsEl = document.getElementById('node-specialists');
      const managerEl = document.getElementById('node-manager');
      const toolsEl = document.getElementById('node-tools');

      if (container && specialistsEl && managerEl && toolsEl) {
        const containerRect = container.getBoundingClientRect();
        const specRect = specialistsEl.getBoundingClientRect();
        const mgrRect = managerEl.getBoundingClientRect();
        const toolsRect = toolsEl.getBoundingClientRect();

        // Specialists connection: starts bottom-center of specialists
        const x1 = (specRect.left + specRect.right) / 2 - containerRect.left;
        const y1 = specRect.bottom - containerRect.top;

        // Manager connection: starts bottom-center of manager
        const mx1 = (mgrRect.left + mgrRect.right) / 2 - containerRect.left;
        const my1 = mgrRect.bottom - containerRect.top;

        // Tools entry points: 25% and 75% of tool card width
        const x2 = toolsRect.left + toolsRect.width * 0.25 - containerRect.left;
        const mx2 = toolsRect.left + toolsRect.width * 0.75 - containerRect.left;
        const y2 = toolsRect.top - containerRect.top;

        setCoords({ x1, y1, x2, y2, mx1, my1, mx2 });
      }
    };

    if (typeof ResizeObserver === 'undefined') {
      updateCoords();
      window.addEventListener('resize', updateCoords);
      const t1 = setTimeout(updateCoords, 100);
      const t2 = setTimeout(updateCoords, 500);
      return () => {
        window.removeEventListener('resize', updateCoords);
        clearTimeout(t1);
        clearTimeout(t2);
      };
    }

    // Create ResizeObserver to observe layout settling shifts
    const observer = new ResizeObserver(() => {
      updateCoords();
    });

    const container = containerRef.current;
    if (container) {
      observer.observe(container);
    }

    const checkAndObserve = () => {
      const specialistsEl = document.getElementById('node-specialists');
      const managerEl = document.getElementById('node-manager');
      const toolsEl = document.getElementById('node-tools');

      if (specialistsEl) observer.observe(specialistsEl);
      if (managerEl) observer.observe(managerEl);
      if (toolsEl) observer.observe(toolsEl);

      updateCoords();
    };

    checkAndObserve();
    
    // Multiple timeouts as fail-safe for hot reloading / font loads
    const t1 = setTimeout(checkAndObserve, 100);
    const t2 = setTimeout(checkAndObserve, 400);
    const t3 = setTimeout(checkAndObserve, 800);

    window.addEventListener('resize', updateCoords);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', updateCoords);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [activeNode]);

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
      label: '5 Specialists Agents  ',
      desc: 'Parallel agents: Plan Generator, Schedule Estimator, Solution Architect, PoC Engineer, and Tech Stack Matcher.',
      icon: <Sparkles size={20} className="text-ai-spark" />,
      color: 'border-ai-spark/30 text-ai-spark bg-ai-spark/10',
      activeColor: 'ring-ai-spark/50 shadow-[0_0_15px_rgba(139,92,246,0.3)]',
    },
    {
      id: 'rag',
      label: 'RAG (Pinecone Store)',
      desc: 'Grounds outputs in organization guidelines, engineering standards, and template repositories via Pinecone semantic search.',
      icon: <BookOpen size={20} className="text-ai-spark" />,
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
    {
      id: 'tools',
      label: 'Tool Layer (MCP & APIs)',
      desc: 'Provides Tavily web search, Slack alerts, GitHub pull requests, Pinecone store, and Atlassian Jira/Google Sheets export integrations.',
      icon: <Wrench size={20} className="text-primary" />,
      color: 'border-primary/30 text-primary bg-primary/10',
      activeColor: 'ring-primary/50 shadow-[0_0_15px_rgba(79,70,229,0.3)]',
    }
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
        <div ref={containerRef} className="flex flex-col gap-4 bg-background/80 rounded-xl px-4 py-5 border border-border relative">
          
          {/* Top section: Columns and Center loop */}
          <div className="flex flex-col md:flex-row gap-4 items-center justify-center">
            {/* Spoke layout - left column */}
            <div className="flex flex-col gap-2.5 w-full md:w-5/12 z-10">
              {pipelineNodes.slice(0, 3).map((node) => (
                <div
                  key={node.id}
                  id={node.id === 'specialists' ? 'node-specialists' : undefined}
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
              {pipelineNodes.filter(n => ['critic', 'manager', 'rag'].includes(n.id)).map((node) => (
                <div
                  key={node.id}
                  id={node.id === 'manager' ? 'node-manager' : undefined}
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
          </div>

          {/* Dynamic SVG paths overlay drawing the physical connection lines */}
          {coords && (() => {
            const midY = (coords.y1 + coords.y2) / 2;
            const mMidY = (coords.my1 + coords.y2) / 2;
            return (
              <svg className="absolute inset-0 w-full h-full pointer-events-none hidden md:block z-20" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <marker id="green-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10B981" />
                  </marker>
                </defs>
                
                {/* Specialists -> Tools: goes down, then horizontally, then down into Tools */}
                <path
                  d={`M ${coords.x1},${coords.y1} L ${coords.x1},${midY} L ${coords.x2},${midY} L ${coords.x2},${coords.y2 - 2}`}
                  fill="none"
                  stroke="#10B981"
                  strokeWidth="2"
                  strokeDasharray="4, 3"
                  markerEnd="url(#green-arrow)"
                />
                <text
                  x={(coords.x1 + coords.x2) / 2}
                  y={midY - 4}
                  fill="#10B981"
                  className="text-[9px] font-extrabold tracking-wider uppercase"
                  textAnchor="middle"
                >
                  tool call
                </text>
                
                {/* Manager -> Tools: goes down, then horizontally, then down into Tools */}
                <path
                  d={`M ${coords.mx1},${coords.my1} L ${coords.mx1},${mMidY} L ${coords.mx2},${mMidY} L ${coords.mx2},${coords.y2 - 2}`}
                  fill="none"
                  stroke="#10B981"
                  strokeWidth="2"
                  strokeDasharray="4, 3"
                  markerEnd="url(#green-arrow)"
                />
                <text
                  x={(coords.mx1 + coords.mx2) / 2}
                  y={mMidY - 4}
                  fill="#10B981"
                  className="text-[9px] font-extrabold tracking-wider uppercase"
                  textAnchor="middle"
                >
                  tool call
                </text>
              </svg>
            );
          })()}

          {/* Bottom section: Tool Layer centered at the bottom */}
          <div className="flex flex-col items-center w-full z-10 relative mt-6 pt-3 border-t border-border/40">
            {/* Tool Layer Card centered at the bottom */}
            <div className="w-full md:w-8/12">
              {pipelineNodes.filter(n => n.id === 'tools').map((node) => (
                <div
                  key={node.id}
                  id="node-tools"
                  className="relative group"
                  onMouseEnter={() => setActiveNode(node.id)}
                  onMouseLeave={() => setActiveNode(null)}
                  onClick={() => setActiveNode(activeNode === node.id ? null : node.id)}
                >
                  <div
                    className={`p-3 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-border'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-3">
                        {node.icon}
                        <div className="flex flex-col">
                          <span className="text-xs font-extrabold">{node.label}</span>
                          <span className="text-[10px] text-muted-foreground/80 font-medium mt-0.5">
                            📋 Jira Epic · 📊 Google Sheets · 🔍 Tavily Search · 💬 Slack · 💻 GitHub
                          </span>
                        </div>
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
          </div>
        </div>
      </div>
    </div>
  );
};
