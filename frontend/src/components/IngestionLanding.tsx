import React, { useState, useEffect, useRef } from 'react';
import { ShieldCheck, Cpu, GitPullRequest, Milestone, Sparkles, Info, Wrench, BookOpen, Bot, CheckSquare, Bell, Database } from 'lucide-react';

interface IngestionLandingProps {
  selectedFile: File | null;
  onFileSelect: (file: File) => void;
  onRemoveFile: () => void;
  onTrigger: () => void;
  isLoading: boolean;
  isAuthenticated: boolean;
  onLogin: () => void;
}

export const IngestionLanding: React.FC<IngestionLandingProps> = ({
  selectedFile,
  isAuthenticated,
}) => {
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<{
    x1: number; y1: number;
    x2: number; y2: number;
    mx1: number; my1: number;
    mx2: number;
    colLeft: number;
    colRight: number;
    specMidY: number;
    ragMidY: number;
    bottomSpaceY: number;
    secX: number; secY1: number; secY2: number;
    orchX: number; orchY1: number; orchY2: number;
    ragTopY: number;
    critX: number; critY1: number; critY2: number;
    critLeft: number;
    critMidY: number;
  } | null>(null);

  useEffect(() => {
    const updateCoords = () => {
      const container = containerRef.current;
      const specialistsEl = document.getElementById('node-specialists');
      const managerEl = document.getElementById('node-manager');
      const toolsEl = document.getElementById('node-tools');
      const ragEl = document.getElementById('node-rag');
      const securityEl = document.getElementById('node-security');
      const orchestratorEl = document.getElementById('node-orchestrator');
      const criticEl = document.getElementById('node-critic');

      if (container && specialistsEl && managerEl && toolsEl && ragEl && securityEl && orchestratorEl && criticEl) {
        const containerRect = container.getBoundingClientRect();
        const specRect = specialistsEl.getBoundingClientRect();
        const mgrRect = managerEl.getBoundingClientRect();
        const toolsRect = toolsEl.getBoundingClientRect();
        const ragRect = ragEl.getBoundingClientRect();
        const secRect = securityEl.getBoundingClientRect();
        const orchRect = orchestratorEl.getBoundingClientRect();
        const criticRect = criticEl.getBoundingClientRect();

        // Specialists connection: starts bottom-center of specialists
        const x1 = (specRect.left + specRect.right) / 2 - containerRect.left;
        const y1 = specRect.bottom - containerRect.top;

        // Manager connection: starts from the right portion of manager to prevent crowding at RAG drop
        const mx1 = mgrRect.right - containerRect.left - 12;
        const my1 = mgrRect.bottom - containerRect.top;

        // Tools entry points: 25% and 75% of tool card width
        const x2 = toolsRect.left + toolsRect.width * 0.25 - containerRect.left;
        const mx2 = toolsRect.left + toolsRect.width * 0.75 - containerRect.left;
        const y2 = toolsRect.top - containerRect.top;

        // Specialists -> RAG U-bend (left side of the left column).
        // Same X for both cards since they share the column.
        const colLeft = specRect.left - containerRect.left;
        const colRight = specRect.right - containerRect.left;
        const specMidY = (specRect.top + specRect.bottom) / 2 - containerRect.top;
        const ragMidY = (ragRect.top + ragRect.bottom) / 2 - containerRect.top;
        const bottomSpaceY = (ragRect.bottom + toolsRect.top) / 2 - containerRect.top;

        // Security -> Orchestrator vertical line
        const secX = (secRect.left + secRect.right) / 2 - containerRect.left;
        const secY1 = secRect.bottom - containerRect.top;
        const secY2 = orchRect.top - containerRect.top;

        // Orchestrator -> Specialists vertical line
        const orchX = (orchRect.left + orchRect.right) / 2 - containerRect.left;
        const orchY1 = orchRect.bottom - containerRect.top;
        const orchY2 = specRect.top - containerRect.top;

        // Specialists -> RAG top center vertical line
        const ragTopY = ragRect.top - containerRect.top;

        // Critic -> Manager vertical line
        const critX = (criticRect.left + criticRect.right) / 2 - containerRect.left;
        const critY1 = criticRect.bottom - containerRect.top;
        const critY2 = mgrRect.top - containerRect.top;

        const critLeft = criticRect.left - containerRect.left;
        const critMidY = (criticRect.top + criticRect.bottom) / 2 - containerRect.top;

        setCoords({
          x1, y1, x2, y2, mx1, my1, mx2, colLeft, colRight, specMidY, ragMidY, bottomSpaceY,
          secX, secY1, secY2,
          orchX, orchY1, orchY2,
          ragTopY,
          critX, critY1, critY2,
          critLeft,
          critMidY
        });
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
      const ragEl = document.getElementById('node-rag');
      const criticEl = document.getElementById('node-critic');

      if (specialistsEl) observer.observe(specialistsEl);
      if (managerEl) observer.observe(managerEl);
      if (toolsEl) observer.observe(toolsEl);
      if (ragEl) observer.observe(ragEl);
      if (criticEl) observer.observe(criticEl);

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
  //   🔴 Security Validator (blocks unsafe/malformed input — defensive gate)
  //   💜 Orchestrator + Specialists + RAG (AI agents + their knowledge source)
  //   🟡 Critic Reviewer (judges + may loop back for revision)
  //   🟢 Manager (HITL) Gate (approves and ships)
  //
  // The three AI-tier nodes intentionally share --color-ai-spark (Electric
  // Purple) to visually group Orchestrator (hub) + Specialists (spokes) + RAG
  // (the knowledge surface the spokes query). Security uses --danger because
  // it's a defensive gate, not a quality check — keeps it visually distinct
  // from Critic so reviewers can tell "block-on-entry" from "review-on-exit".
  const pipelineNodes = [
    {
      id: 'security',
      label: 'Security Validator',
      desc: 'Performs file size check, BRD validity check, prompt injection assessment, and filters/redacts PII patterns.',
      icon: <ShieldCheck size={20} className="text-danger" />,
      color: 'border-danger/30 text-danger bg-danger/10',
      activeColor: 'ring-danger/50 shadow-[0_0_15px_rgba(239,68,68,0.3)]',
    },
    {
      id: 'orchestrator',
      label: 'Orchestrator',
      desc: 'Parses the BRD sections, evaluates structure completeness, and splits tasks for 5 specialists Agents.',
      icon: <Cpu size={20} className="text-ai-spark" />,
      color: 'border-ai-spark/30 text-ai-spark bg-ai-spark/10',
      activeColor: 'ring-ai-spark/50 shadow-[0_0_15px_rgba(139,92,246,0.3)]',
    },
    {
      id: 'specialists',
      label: '5 Specialist Agents (Parallel)',
      desc: 'Parallel 2-Pass Alignment: (1) All specialists run concurrently to draft plans. (2) Orchestrator reviews and issues an alignment memo. (3) Specialists run concurrently again to coordinate and refine final plans.',
      icon: <Sparkles size={20} className="text-ai-spark" />,
      color: 'border-ai-spark/30 text-ai-spark bg-ai-spark/10',
      activeColor: 'ring-ai-spark/50 shadow-[0_0_15px_rgba(139,92,246,0.3)]',
    },
    {
      id: 'rag',
      label: 'RAG (Pinecone Vector DB)',
      desc: 'Grounds outputs in organization guidelines, engineering standards, and template repositories via Pinecone semantic search.',
      icon: <BookOpen size={20} className="text-ai-spark" />,
      color: 'border-ai-spark/30 text-ai-spark bg-ai-spark/10',
      activeColor: 'ring-ai-spark/50 shadow-[0_0_15px_rgba(139,92,246,0.3)]',
    },
    {
      id: 'critic',
      label: 'Critic Reviewer - Evaluation',
      desc: 'Five-method evaluation suite (BERTScore F1 >= 0.85). Grades outputs on 4 quality dimensions (1.0-5.0 score) and triggers revisions if needed. Green badge requires all dimensions passing, overall >= 4.0, and zero unresolved warnings (otherwise capped at Amber).',
      icon: <GitPullRequest size={20} className="text-warning" />,
      color: 'border-warning/30 text-warning bg-warning/10',
      activeColor: 'ring-warning/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]',
    },
    {
      id: 'manager',
      label: 'Manager (HITL) Decision Gate',
      desc: 'Pauses execution to obtain engineering manager approval before exporting to Google Sheets and Jira. Voice AI support (ElevenLabs) at Decision Gate.',
      icon: <Milestone size={20} className="text-success" />,
      color: 'border-success/30 text-success bg-success/10',
      activeColor: 'ring-success/50 shadow-[0_0_15px_rgba(16,185,129,0.3)]',
    },
    {
      id: 'tools',
      label: 'Tool Layer (MCP & APIs)',
      desc: 'Provides Tavily web search, Slack alerts, GitHub pull requests, Pinecone store, Upstash Redis long-term cache & state store, and Atlassian Jira/Google Sheets export integrations.',
      icon: <Wrench size={20} className="text-primary" />,
      color: 'border-primary/30 text-primary bg-primary/10',
      activeColor: 'ring-primary/50 shadow-[0_0_15px_rgba(79,70,229,0.3)]',
    }
  ];

  return (
    <div className="space-y-3 w-full py-2">
      {/* Welcome & Subtitle Section */}
      <div className="space-y-1.5">
        <h2 className="text-base font-semibold tracking-tight text-foreground">
          Transform a BRD into an Engineering Plan in Minutes, grounded in RAG
        </h2>
        <p className="text-xs text-muted-foreground max-w-3xl">
          EM Copilot transforms raw Business Requirements Documents into audit-ready engineering plans, grounded via RAG in your organization's own architectural patterns and approved tech stack. Artifacts are presented for review; on approval, pushed to Jira.
        </p>
      </div>

      {/* Welcome Callout for logged in, pre-upload state */}
      {isAuthenticated && !selectedFile && (
        <div className="flex items-center gap-2 p-3 bg-[#f0f7ff] dark:bg-sky-950/20 border border-sky-200 dark:border-sky-800/40 rounded-lg text-xs text-sky-800 dark:text-sky-300 font-medium animate-in fade-in slide-in-from-top-1 duration-200 mt-3.5 mb-5 shadow-sm">
          <span className="text-sm">💡</span>
          <span><strong>Next Step:</strong> Drag and drop a BRD file on the left to generate your engineering plan.</span>
        </div>
      )}

      {/* System Architecture Diagram - full width, compact above-the-fold layout */}
      <div className="rounded-xl border border-border bg-card/60 p-3.5 space-y-2 shadow-md">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-bold text-foreground">System Architecture</h3>
        </div>

        {/* Interactive Flow Visualizer - compact (tooltip replaces the old 96px detail box) */}
        <div ref={containerRef} className="flex flex-col gap-3 bg-background/80 rounded-xl px-3.5 py-3 border border-border relative shadow-sm">

          {/* Top section: Columns and Center loop */}
          <div className="flex flex-col md:flex-row gap-4 md:gap-12 lg:gap-16 items-center justify-center w-full">
            {/* Spoke layout - left column.
                Includes RAG so it sits visually adjacent to Specialists (its
                actual consumer). Order: Security → Orchestrator → Specialists → RAG. */}
            <div className="flex flex-col gap-5 w-full md:w-5/12 z-10">
              {pipelineNodes.slice(0, 4).map((node) => (
                <div
                  key={node.id}
                  id={
                    node.id === 'specialists' ? 'node-specialists'
                      : node.id === 'rag' ? 'node-rag'
                        : node.id === 'security' ? 'node-security'
                          : node.id === 'orchestrator' ? 'node-orchestrator'
                            : undefined
                  }
                  className="relative group"
                  onMouseEnter={() => setActiveNode(node.id)}
                  onMouseLeave={() => setActiveNode(null)}
                  onClick={() => setActiveNode(activeNode === node.id ? null : node.id)}
                >
                  <div
                    className={`p-2 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-border'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {node.icon}
                        <span className="text-xs font-bold">{node.label}</span>
                      </div>
                      <Info size={12} className="text-foreground/60 group-hover:text-foreground transition-colors shrink-0 ml-2" />
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
            <div className="flex flex-col md:flex-row items-center justify-center gap-2 shrink-0 my-2 md:my-0 relative -translate-y-6">
              {/* Left to Center connection */}
              <div className="flex flex-col md:flex-row items-center gap-1">
                <div className="h-4 w-0.5 md:h-0.5 md:w-8 bg-gradient-to-b md:bg-gradient-to-r from-ai-spark to-primary" />
                <span className="text-[10px] text-primary select-none transform rotate-90 md:rotate-0">▶</span>
              </div>

              {/* Circular Loop Graphic container */}
              <div className="relative flex items-center justify-center w-32 h-24 shrink-0 select-none">
                {/* Loop arrows (SVG) */}
                <svg className="absolute inset-0 w-full h-full text-warning/45 dark:text-warning/35 animate-[spin_5s_linear_infinite]" viewBox="0 0 100 100" fill="none">
                  {/* Loop path */}
                  <path
                    d="M 50,10 A 40,40 0 1,1 49.9,10"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeDasharray="5, 3"
                  />
                  {/* Arrow heads pointing clockwise */}
                  <path d="M 50,10 L 44,4 L 44,16 Z" fill="currentColor" />
                  <path d="M 50,90 L 56,96 L 56,84 Z" fill="currentColor" />
                </svg>

                <span className="text-[10px] font-bold px-3 py-1.5 bg-card border border-border rounded-full text-muted-foreground text-center select-none font-mono shadow-sm z-10 max-w-[110px] leading-tight">
                  Revision & Alignment Loop
                </span>
              </div>

              {/* Center to Right connection */}
              <div className="flex flex-col md:flex-row items-center gap-1">
                <div className="h-4 w-0.5 md:h-0.5 md:w-8 bg-gradient-to-b md:bg-gradient-to-r from-warning to-success" />
                <span className="text-[10px] text-success select-none transform rotate-90 md:rotate-0">▶</span>
              </div>
            </div>

            {/* Right column — review + approval lane.
                RAG moved to left column adjacent to Specialists since that's
                where it's actually queried (not by Critic/Manager). */}
             <div className="flex flex-col gap-5 w-full md:w-5/12 z-10">
              {pipelineNodes.filter(n => ['critic', 'manager'].includes(n.id)).map((node) => (
                <div
                  key={node.id}
                  id={node.id === 'manager' ? 'node-manager' : node.id === 'critic' ? 'node-critic' : undefined}
                  className="relative group"
                  onMouseEnter={() => setActiveNode(node.id)}
                  onMouseLeave={() => setActiveNode(null)}
                  onClick={() => setActiveNode(activeNode === node.id ? null : node.id)}
                >
                  <div
                    className={`p-2 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-border'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {node.icon}
                        <span className="text-xs font-bold">{node.label}</span>
                      </div>
                      <Info size={12} className="text-foreground/60 group-hover:text-foreground transition-colors shrink-0 ml-2" />
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
            const mMidY = coords.my1 + (coords.y2 - coords.my1) * 0.80;
            return (
              <svg className="absolute inset-0 w-full h-full pointer-events-none hidden md:block z-0" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <marker id="green-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10B981" />
                  </marker>
                  <marker id="purple-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#8B5CF6" />
                  </marker>
                  <marker id="gray-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748B" />
                  </marker>
                  <marker id="orange-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#F59E0B" />
                  </marker>
                </defs>

                {/* Security -> Orchestrator vertical line - neutral slate gray to blend into flow */}
                <path
                  d={`M ${coords.secX},${coords.secY1} L ${coords.secX},${coords.secY2 - 2}`}
                  fill="none"
                  stroke="#64748B"
                  strokeWidth="2"
                  markerEnd="url(#gray-arrow)"
                />

                {/* Orchestrator -> Specialists vertical line */}
                <path
                  d={`M ${coords.orchX},${coords.orchY1} L ${coords.orchX},${coords.orchY2 - 2}`}
                  fill="none"
                  stroke="#8B5CF6"
                  strokeWidth="2"
                  markerEnd="url(#purple-arrow)"
                />

                {/* Critic -> Manager vertical line */}
                <path
                  d={`M ${coords.critX},${coords.critY1} L ${coords.critX},${coords.critY2 - 2}`}
                  fill="none"
                  stroke="#F59E0B"
                  strokeWidth="2"
                  markerEnd="url(#orange-arrow)"
                />

                {/* Critic -> RAG citation verification check line */}
                {(() => {
                  const startX = coords.critLeft + 15;
                  const verticalX = coords.critLeft - 6;
                  return (
                    <>
                      <path
                        d={`M ${startX},${coords.critY1} L ${verticalX},${coords.critY1} L ${verticalX},${coords.ragMidY} L ${coords.colRight + 2},${coords.ragMidY}`}
                        fill="none"
                        stroke="#F59E0B"
                        strokeWidth="2"
                        strokeDasharray="4, 3"
                        markerEnd="url(#orange-arrow)"
                      />
                      <text
                        x={(verticalX + coords.colRight) / 2}
                        y={coords.ragMidY - 8}
                        fill="#F59E0B"
                        className="text-[9px] font-extrabold tracking-wider"
                        textAnchor="middle"
                      >
                        RAG Citation Verification
                      </text>
                    </>
                  );
                })()}

                {/* Specialists -> RAG: straight vertical line between stacked cards */}
                <path
                  d={`M ${coords.x1},${coords.y1} L ${coords.x1},${coords.ragTopY - 2}`}
                  fill="none"
                  stroke="#8B5CF6"
                  strokeWidth="2"
                  markerEnd="url(#purple-arrow)"
                />

                {/* Specialists -> Tools: goes right, then straight down into Tools */}
                <path
                  d={`M ${coords.colRight},${coords.specMidY} L ${coords.colRight + 30},${coords.specMidY} L ${coords.colRight + 30},${coords.y2 - 2}`}
                  fill="none"
                  stroke="#8B5CF6"
                  strokeWidth="2"
                  strokeDasharray="4, 3"
                  markerEnd="url(#purple-arrow)"
                />
                <text
                  x={coords.colRight + 36}
                  y={coords.bottomSpaceY - 17}
                  fill="#8B5CF6"
                  className="text-[9px] font-extrabold tracking-wider"
                  textAnchor="start"
                >
                  Autonomous Tool Call
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
                  y={mMidY + 14}
                  fill="#10B981"
                  className="text-[9px] font-extrabold tracking-wider"
                  textAnchor="middle"
                >
                  Tool Call on Human Decision
                </text>
              </svg>
            );
          })()}

          {/* Bottom section: Tool Layer centered at the bottom */}
          <div className="flex flex-col items-center w-full z-10 relative mt-2 pt-1.5 border-t border-border/40">
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
                    className={`py-4 px-4 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-border'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-3 flex-1">
                        {node.icon}
                        <div className="flex-1">
                          <span className="text-xs md:text-sm font-extrabold text-foreground/90">{node.label}</span>
                          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-2 mt-1.5 border-t border-primary/20">
                            {/* Sub-cluster 1: Autonomous Tools */}
                            <div className="space-y-0.5">
                              <div className="text-[10px] md:text-xs uppercase font-extrabold text-purple-500 tracking-wider flex items-center gap-1">
                                <Bot size={12} />
                                Autonomous
                              </div>
                              <div className="flex flex-col gap-y-1 mt-1 text-[10px] md:text-xs text-muted-foreground">
                                <span>🔍 Tavily Search</span>
                                <span>💻 GitHub</span>
                              </div>
                            </div>
 
                            {/* Sub-cluster 2: Export on Approval */}
                            <div className="space-y-0.5 md:border-l md:border-border/60 md:pl-3">
                              <div className="text-[10px] md:text-xs uppercase font-extrabold text-success tracking-wider flex items-center gap-1">
                                <CheckSquare size={12} />
                                Export
                              </div>
                              <div className="flex flex-col gap-y-1 mt-1 text-[10px] md:text-xs text-muted-foreground">
                                <span>📋 Jira Epic</span>
                                <span>📊 Google Sheets</span>
                              </div>
                            </div>
 
                            {/* Sub-cluster 3: State & Cache */}
                            <div className="space-y-0.5 md:border-l md:border-border/60 md:pl-3">
                              <div className="text-[10px] md:text-xs uppercase font-extrabold text-indigo-500 tracking-wider flex items-center gap-1">
                                <Database size={12} />
                                State & Cache
                              </div>
                              <div className="flex flex-col gap-y-1 mt-1 text-[10px] md:text-xs text-muted-foreground">
                                <span>💾 Upstash Redis</span>
                              </div>
                            </div>

                            {/* Sub-cluster 4: Operations & Monitoring */}
                            <div className="space-y-0.5 md:border-l md:border-border/60 md:pl-3">
                              <div className="text-[10px] md:text-xs uppercase font-extrabold text-warning tracking-wider flex items-center gap-1">
                                <Bell size={12} />
                                Alerts
                              </div>
                              <div className="flex flex-col gap-y-1 mt-1 text-[10px] md:text-xs text-muted-foreground">
                                <span>💬 Slack Alerts</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                      <Info size={14} className="text-foreground/60 group-hover:text-foreground transition-colors shrink-0 ml-2" />
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
