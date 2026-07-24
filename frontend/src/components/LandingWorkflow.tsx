/**
 * LandingWorkflow — landing-page hero visual.
 *
 * Story-first user-journey diagram. Six-step chain (Upload → Analyze → Draft &
 * Refine → Critic-Verify → HITL Approval → Export) paired with a 4-card
 * mechanism breakdown below.
 *
 * Strictly adheres to the 3-Color System:
 *   - Electric Indigo: Ingestion, Analysis & Multi-Agent Drafting
 *   - Amber Yellow: Critic Verification & Human-in-the-Loop Review
 *   - Tech Green: Final Export & External Integrations
 */

import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { Upload, Search, FileText, Scale, UserCheck, Rocket, type LucideIcon } from 'lucide-react';

// ─── Node Tooltip Data (Tier 1) ──────────────────────────────────────────
type NodeId = 'upload' | 'analyze' | 'draft' | 'critic' | 'hitl' | 'export';

const NODE_TOOLTIPS: Record<NodeId, { Icon: LucideIcon; iconClass: string; title: string; desc: string }> = {
  upload: {
    Icon: Upload,
    iconClass: 'text-foreground',
    title: 'Upload BRD',
    desc: 'Upload a Business Requirement Document (PDF, DOCX, or TXT) to kick off the multi-agent planning pipeline.',
  },
  analyze: {
    Icon: Search,
    iconClass: 'text-indigo-600 dark:text-indigo-400',
    title: 'Analyze BRD',
    desc: 'The AI parses your BRD, extracts requirements, and runs safety checks (size, PII, prompt injection) before drafting.',
  },
  draft: {
    Icon: FileText,
    iconClass: 'text-indigo-600 dark:text-indigo-400',
    title: 'Draft & Refine Plan',
    desc: "Five specialist agents draft PoC, Architect, Tech Stack, Schedule, and Plan artifacts in parallel — grounded via RAG in your team's own docs — with multi-pass alignment refinement.",
  },
  critic: {
    Icon: Scale,
    iconClass: 'text-amber-600 dark:text-amber-400',
    title: 'Critic-Verify',
    desc: 'Independent Critic grades outputs on 4 quality dimensions (Groundedness, Completeness, Consistency, Actionability) and triggers a revision loop if the gate fails.',
  },
  hitl: {
    Icon: UserCheck,
    iconClass: 'text-amber-600 dark:text-amber-400',
    title: 'HITL Review & Approval',
    desc: 'You review the deliverables and approve — or reject with notes to trigger another revision. Voice AI support (ElevenLabs) is available at the Decision Gate.',
  },
  export: {
    Icon: Rocket,
    iconClass: 'text-emerald-600 dark:text-emerald-400',
    title: 'Export to Jira',
    desc: 'On approval, the plan writes to a Jira Epic, logs to Google Sheets, and pings Slack — full audit trail preserved for compliance.',
  },
};

// ─── Phase Card Data (Tier 2) ─────────────────────────────────────────────
const PHASES = [
  {
    title: 'Ingest & Validate',
    tagline: 'Upload BRD + Analyze BRD',
    body: 'You drop in a requirements document (PDF, DOCX, or TXT). The AI validates size, format, PII, and security checks before passing to Orchestrator Agent.',
    bar: 'bg-slate-300 dark:bg-slate-700',
    text: 'text-slate-700 dark:text-slate-300',
  },
  {
    title: 'Multi-Agent Draft',
    tagline: '5 AI Agents Draft the Plan',
    body: 'Five specialist agents (PoC, Architect, Tech Stack, Schedule, Plan) run in parallel to generate first draft, aligned via Orchestrator Agent directives.',
    bar: 'bg-[#4f46e5]',
    text: 'text-[#4f46e5]',
  },
  {
    title: 'Critic & Revise',
    tagline: 'Verify Output + Quality Rating',
    body: 'Independent Agent grades outputs on 4 dimensions (Groundedness, Completeness, Consistency, Actionability). Automated self-correction loops kick in if needed.',
    bar: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
  },
  {
    title: 'Approve & Ship',
    tagline: 'HITL Approval + Export to Jira',
    body: 'Review artifacts at Decision Gate with Voice AI. On user approval, plan is pushed into Jira (MCP). Pipeline metrics are logged to Google Sheets for audit.',
    bar: 'bg-emerald-500',
    text: 'text-emerald-600 dark:text-emerald-400',
  },
];

interface LandingWorkflowProps {
  title?: string;
}

export const LandingWorkflow: React.FC<LandingWorkflowProps> = ({ title }) => {
  const [tooltipState, setTooltipState] = useState<{ id: NodeId; x: number; y: number } | null>(null);

  const handleMouseEnter = (id: NodeId, event: React.MouseEvent) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltipState({
      id,
      x: rect.left + rect.width / 2,
      y: rect.top - 8,
    });
  };

  const handleMouseLeave = () => setTooltipState(null);

  const getTooltipPosition = (): React.CSSProperties => {
    if (!tooltipState) return { left: 0, top: 0, position: 'fixed' };
    const tooltipWidth = 288; // w-72
    const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1440;
    const leftX = Math.max(
      12 + tooltipWidth / 2,
      Math.min(tooltipState.x, viewportWidth - tooltipWidth / 2 - 12)
    );
    return { left: `${leftX}px`, top: `${tooltipState.y}px`, position: 'fixed' };
  };

  const active = tooltipState ? NODE_TOOLTIPS[tooltipState.id] : null;

  return (
    <div className="w-full bg-card border border-border/80 rounded-xl p-4 shadow-sm space-y-4">

      {/* ─── SECTION HEADER ───────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
        <h3 className="text-xs font-extrabold text-[#4f46e5] uppercase tracking-wider">
          {title || 'How It Works'}
        </h3>
      </div>

      {/* ─── TIER 1: SVG WORKFLOW CHAIN ───────────────────────────────── */}
      <div className="overflow-x-auto -mx-1 md:mx-0">
        <svg
          viewBox="0 0 750 250"
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-label="EM Copilot user workflow: six-step user journey from BRD upload to Jira export."
          className="w-full h-auto"
        >
          <defs>
            <marker id="lw-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-muted-foreground)" />
            </marker>
            <marker id="lw-arrow-warn" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
            </marker>
            <marker id="lw-arrow-success" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
            </marker>
            <marker id="lw-arrow-primary" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#4f46e5" />
            </marker>
          </defs>

          {/* Revision Loop */}
          <path
            d="M 437 75 C 437 15, 312 15, 312 75"
            fill="none"
            stroke="#f59e0b"
            strokeWidth={2}
            strokeDasharray="6 4"
            markerEnd="url(#lw-arrow-warn)"
          />
          <text x={374} y={12} fontSize={11} fill="#f59e0b" fontWeight={700} textAnchor="middle">
            ↻ Revision loop
          </text>

          {/* Connectors */}
          <line x1={115} y1={115} x2={135} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={240} y1={115} x2={260} y2={115} stroke="#4f46e5" strokeWidth={2} markerEnd="url(#lw-arrow-primary)" />
          <line x1={365} y1={115} x2={385} y2={115} stroke="#4f46e5" strokeWidth={2} markerEnd="url(#lw-arrow-primary)" />
          <line x1={490} y1={115} x2={510} y2={115} stroke="#f59e0b" strokeWidth={2} markerEnd="url(#lw-arrow-warn)" />
          <line x1={615} y1={115} x2={635} y2={115} stroke="#10b981" strokeWidth={2.5} markerEnd="url(#lw-arrow-success)" />

          {/* Down Arrow to Artifact Pills */}
          <line x1="312" y1="156" x2="312" y2="171" stroke="#4f46e5" strokeWidth="2" markerEnd="url(#lw-arrow-primary)" />

          {/* Node 1: Upload */}
          <foreignObject x={10} y={75} width={105} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('upload', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border-2 border-slate-300 dark:border-slate-700 hover:border-indigo-600 rounded-2xl bg-card px-1 py-1 shadow-sm transition-all duration-200 cursor-help"
            >
              <Upload className="text-foreground shrink-0" size={24} />
              <span className="text-[11px] font-bold text-foreground leading-tight text-center">Upload BRD</span>
              <span className="text-[9px] text-muted-foreground leading-tight text-center">Document</span>
            </div>
          </foreignObject>

          {/* Node 2: Analyze */}
          <foreignObject x={135} y={75} width={105} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('analyze', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border-2 border-indigo-400 dark:border-indigo-500 hover:border-indigo-600 rounded-2xl bg-card px-1 py-1 shadow-sm transition-all duration-200 cursor-help"
            >
              <Search className="text-[#4f46e5] shrink-0" size={24} />
              <span className="text-[11px] font-bold text-foreground leading-tight text-center">Analyze Requirements</span>
              <span className="text-[9px] text-muted-foreground leading-tight text-center">Verification</span>
            </div>
          </foreignObject>

          {/* Node 3: Draft & Refine */}
          <foreignObject x={260} y={75} width={105} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('draft', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border-2 border-indigo-400 dark:border-indigo-500 hover:border-indigo-600 rounded-2xl bg-card px-1 py-1 shadow-sm transition-all duration-200 cursor-help"
            >
              <FileText className="text-[#4f46e5] shrink-0" size={24} />
              <span className="text-[11px] font-bold text-foreground leading-tight text-center">Draft &amp; Refine Plan</span>
              <span className="text-[9px] text-muted-foreground leading-tight text-center">Multi-pass alignment</span>
            </div>
          </foreignObject>

          {/* Artifact Pills */}
          <foreignObject x={142} y={178} width={340} height={80}>
            <div className="w-full">
              <div className="text-[10px] text-[#4f46e5] text-center font-extrabold uppercase tracking-wider mb-1">
                5 Agents - Generate The Plan
              </div>
              <div className="flex flex-nowrap items-center justify-center gap-1 whitespace-nowrap">
                {['PoC', 'Architect', 'Tech Stack', 'Schedule', 'Plan'].map((name) => (
                  <span
                    key={name}
                    className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#4f46e5]/10 text-[#4f46e5] border border-[#4f46e5]/30 shadow-sm"
                  >
                    {name}
                  </span>
                ))}
              </div>
              <div className="text-[10px] text-[#4f46e5]/80 text-center italic mt-1.5 font-medium">
                ↑ grounded via RAG using Organization's docs
              </div>
            </div>
          </foreignObject>

          {/* Node 4: Critic */}
          <foreignObject x={385} y={75} width={105} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('critic', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border-2 border-amber-400 dark:border-amber-500 hover:border-amber-600 rounded-2xl bg-card px-1 py-1 shadow-sm transition-all duration-200 cursor-help"
            >
              <Scale className="text-amber-500 shrink-0" size={24} />
              <span className="text-[11px] font-bold text-foreground leading-tight text-center">Critic - Verify</span>
              <span className="text-[9px] text-muted-foreground leading-tight text-center">Score &amp; revise loop</span>
            </div>
          </foreignObject>

          {/* Node 5: HITL */}
          <foreignObject x={510} y={75} width={105} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('hitl', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border-2 border-amber-400 dark:border-amber-500 hover:border-amber-600 rounded-2xl bg-card px-1 py-1 shadow-sm transition-all duration-200 cursor-help"
            >
              <UserCheck className="text-amber-500 shrink-0" size={24} />
              <span className="text-[11px] font-bold text-foreground leading-tight text-center">HITL Review &amp; Approval</span>
              <span className="text-[9px] text-muted-foreground leading-tight text-center">Human-in-the-loop</span>
            </div>
          </foreignObject>

          {/* Node 6: Export */}
          <foreignObject x={635} y={75} width={105} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('export', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border-2 border-emerald-500 hover:border-emerald-600 rounded-2xl bg-emerald-500/10 px-1 py-1 shadow-sm transition-all duration-200 cursor-help"
            >
              <div className="w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center shrink-0">
                <Rocket className="text-white" size={14} />
              </div>
              <span className="text-[11px] font-bold text-foreground leading-tight text-center">Export to Jira</span>
              <span className="text-[9px] text-muted-foreground leading-tight text-center">Epic · Sheets · Slack</span>
            </div>
          </foreignObject>
        </svg>
      </div>

      {/* Tier 2 JSX Render Loop */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t border-border/60">
        {PHASES.map((p) => (
          <div key={p.title} className="space-y-2">
            {/* 1. Top Accent Line */}
            <div className={`h-1 w-full rounded-full ${p.bar}`} />

            <div className="pt-1 space-y-1">
              {/* 2. Clean Category Header without Numbering */}
              <div className={`text-[11px] font-extrabold ${p.text} uppercase tracking-wider`}>
                {p.title}
              </div>

              {/* 3. Subtitle / Tagline */}
              <div className="text-xs font-bold text-foreground tracking-tight">
                {p.tagline}
              </div>

              {/* 4. Body Description */}
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {p.body}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* ─── RICH HOVER TOOLTIP PORTAL ─────────────────────────────────── */}
      {tooltipState && active && typeof document !== 'undefined' && createPortal(
        <div
          className="z-50 p-3 bg-background border border-border/90 rounded-xl shadow-xl text-[11px] text-muted-foreground leading-relaxed pointer-events-none w-72 -translate-x-1/2 -translate-y-full animate-in fade-in zoom-in-95 duration-150"
          style={getTooltipPosition()}
        >
          <div className="flex items-center gap-1.5 mb-1.5 pb-1.5 border-b border-border font-extrabold text-foreground uppercase tracking-wider text-[10px]">
            <active.Icon size={14} className={`${active.iconClass} shrink-0`} />
            <span>{active.title}</span>
          </div>
          {active.desc}
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1.5 w-3 h-3 rotate-45 bg-background border-r border-b border-border/90" />
        </div>,
        document.body
      )}

    </div>
  );
};