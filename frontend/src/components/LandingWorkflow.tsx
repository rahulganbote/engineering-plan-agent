/**
 * LandingWorkflow — landing-page hero visual.
 *
 * Story-first user-journey diagram. Six-step chain (Upload → Analyze → Draft &
 * Refine → Critic-Verify → HITL Approval → Export) with the five artifact pills
 * below the Draft step, a dashed revision loop above, and four numbered phase
 * cards below the chain that explain the WHY of each phase in prose.
 *
 * Design decisions (locked in with product):
 *   - Icons + labels (lucide-react), not emoji, to match the rest of the app.
 *   - Vertical node layout (icon on top, label below) so full-node width is
 *     available for the label text — no truncation of "Critic-Verify" etc.
 *   - Semantic color tokens: primary (Analyze) · ai-spark (Generate) ·
 *     warning (Verify + HITL) · success (Ship). No hardcoded palette hex.
 *   - Two-tier layout: SVG chain on top, HTML grid of phase cards below.
 *     Split lets the prose tier use CSS grid for responsive stacking; the SVG
 *     tier scrolls horizontally on narrow viewports.
 *   - Rich branded tooltips (ported from TimelineStepper): absolute-positioned
 *     card above each node with icon + uppercase title + prose body. Instant
 *     appearance, matches the app's design system. Replaces native `title=`
 *     which had a 500ms hover delay and a browser-styled yellow rectangle.
 *   - Tightened geometry (viewBox 1160×250): the whole diagram fits without
 *     horizontal scroll on ~1200px+ viewports so the terminal "Export to Jira"
 *     node stays visible above the fold.
 *
 * NOT for pipeline progress — LandingWorkflow is static and marketing-facing.
 * The live pipeline state visualization lives in TimelineStepper (now moved
 * off the landing page onto the About page for technical evaluators).
 */

import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { Upload, Search, FileText, Scale, UserCheck, Rocket, type LucideIcon } from 'lucide-react';

// ─── Node tooltip data ─────────────────────────────────────────────────────
// One row per Tier 1 node. `id` is the discriminator; `Icon` + `color` drive
// the tooltip header; `title` + `desc` are the content shown on hover.
// Extracted as data (not scattered inline) so the JSX stays sparse and adding
// a 7th node is a one-line append rather than a JSX edit.
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
    iconClass: 'text-primary',
    title: 'Analyze BRD',
    desc: 'The AI parses your BRD, extracts requirements, and runs safety checks (size, PII, prompt injection) before drafting.',
  },
  draft: {
    Icon: FileText,
    iconClass: 'text-ai-spark',
    title: 'Draft & Refine',
    desc: "Five specialist agents draft PoC, Architect, Tech Stack, Schedule, and Plan artifacts in parallel — grounded via RAG in your team's own docs — with multi-pass alignment refinement.",
  },
  critic: {
    Icon: Scale,
    iconClass: 'text-warning-strong',
    title: 'Critic-Verify',
    desc: 'Independent Critic grades outputs on 4 quality dimensions (Groundedness, Completeness, Consistency, Actionability) and triggers a revision loop if the gate fails.',
  },
  hitl: {
    Icon: UserCheck,
    iconClass: 'text-success',
    title: 'HITL Approval',
    desc: 'You review the deliverables and approve — or reject with notes to trigger another revision. Voice AI support (ElevenLabs) is available at the Decision Gate.',
  },
  export: {
    Icon: Rocket,
    iconClass: 'text-success',
    title: 'Export to Jira',
    desc: 'On approval, the plan writes to a Jira Epic, logs to Google Sheets, and pings Slack — full audit trail preserved for compliance.',
  },
};

// ─── Phase card data (bottom tier) ─────────────────────────────────────────
// Tier 2 tells the "HOW does the AI do it" story — the four mechanisms that
// make the pipeline work. Complements Tier 1 (which shows WHAT it does).
const PHASES: Array<{
  num: string;
  title: string;
  tagline: string;
  body: string;
  color: 'primary' | 'ai-spark' | 'warning' | 'success' | 'neutral';
}> = [
    {
      num: '1',
      title: 'Ingest & Validate',
      color: 'neutral',
      tagline: 'Upload BRD + Analyze BRD',
      body: 'You drop in a requirement document (PDF, DOCX, or TXT). The AI validates the document and runs size, format, PII and security checks before it is passed to Orchestrator Agent.',
    },
    {
      num: '2',
      title: 'Multi-Agent Draft',
      color: 'primary',
      tagline: '5 AI Agents Draft the Plan',
      body: "Five specialist Agents (PoC, Architect, Tech Stack, Schedule, and Plan) run in parallel to generate first draft. Plan is then revised and aligned via Orchestrator Agent directives.",
    },
    {
      num: '3',
      title: 'Critic & Revise',
      color: 'warning',
      tagline: 'Verify output + Quality Rating',
      body: 'Independent Agent grades outputs on 4 dimensions (Groundedness, Completeness, Consistency, Actionability). Automated self-correction loops kick in if rating does not meet the quality threshold.',
    },
    {
      num: '4',
      title: 'Approve & Ship',
      color: 'success',
      tagline: 'HITL Approval + Export to Jira',
      body: 'Review artifacts at the Decision Gate with Voice AI. On user\'s approval, the plan is pushed into Jira (MCP). Pipeline metrics are logged to Google Sheets for audit. On error Slack notification.',
    },
  ];

const colorClasses: Record<
  'primary' | 'ai-spark' | 'warning' | 'success' | 'neutral',
  { bar: string; text: string }
> = {
  primary: { bar: 'bg-primary', text: 'text-primary' },
  'ai-spark': { bar: 'bg-ai-spark', text: 'text-ai-spark' },
  warning: { bar: 'bg-warning', text: 'text-warning-strong' },
  success: { bar: 'bg-success', text: 'text-success' },
  neutral: { bar: 'bg-muted-foreground/35', text: 'text-muted-foreground' },
};

interface LandingWorkflowProps {
  /** Optional header override. Default: "How It Works". */
  title?: string;
}

export const LandingWorkflow: React.FC<LandingWorkflowProps> = ({ title }) => {
  // ─── Tooltip state + handlers ──────────────────────────────────────────
  // Position captured in VIEWPORT coords (rect.left/top directly) and the
  // tooltip is rendered via createPortal into document.body so it has zero
  // layout impact on the card. This avoids the flicker/card-resize bug that
  // occurred when the tooltip was a `space-y-3` child of the container —
  // Tailwind's space-y selector applied margin-top to the tooltip which,
  // even on an absolute element, triggered browser layout recalcs.
  const [tooltipState, setTooltipState] = useState<{
    id: NodeId;
    x: number;
    y: number;
  } | null>(null);

  const handleMouseEnter = (id: NodeId, event: React.MouseEvent) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltipState({
      id,
      x: rect.left + rect.width / 2, // viewport X of node center
      y: rect.top - 8,               // viewport Y just above node
    });
  };

  const handleMouseLeave = () => setTooltipState(null);

  // Clamp horizontal position so the tooltip never overflows the viewport edges.
  const getTooltipPosition = (): React.CSSProperties => {
    if (!tooltipState) return { left: 0, top: 0, position: 'fixed' };
    const tooltipWidth = 288; // w-72 = 18rem
    const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1440;
    const leftX = Math.max(
      12 + tooltipWidth / 2,
      Math.min(tooltipState.x, viewportWidth - tooltipWidth / 2 - 12)
    );
    return { left: `${leftX}px`, top: `${tooltipState.y}px`, position: 'fixed' };
  };

  const active = tooltipState ? NODE_TOOLTIPS[tooltipState.id] : null;

  return (
    <div className="w-full bg-card border border-border rounded-xl p-3 md:p-4 shadow-lg space-y-3">
      {/* Header — matches the standardized section-title treatment. */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-black text-primary uppercase tracking-wider">
          {title || 'How It Works'}
        </h3>
      </div>

      {/* ─── TIER 1: SVG workflow chain ───────────────────────────────── */}
      <div className="overflow-x-auto -mx-1 md:mx-0">
        <svg
          viewBox="0 0 1160 250"
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-label="EM Copilot user workflow: six-step user journey from BRD upload to Jira export, with a self-verification revision loop and human approval gate."
          className="w-full h-auto min-w-[880px]"
        >
          {/* Intentionally NO <title> element — browsers render <title> as a
              native tooltip on hover which competes with our custom rich
              tooltip. aria-label above provides equivalent screen-reader
              accessibility without the native tooltip side-effect. */}

          <defs>
            <marker id="lw-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-muted-foreground)" />
            </marker>
            <marker id="lw-arrow-warn" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-warning)" />
            </marker>
            <marker id="lw-arrow-success" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-success)" />
            </marker>
            <marker id="lw-arrow-primary" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#6366F1" />
            </marker>
          </defs>

          {/* Revision loop */}
          <path
            d="M 690 75 C 690 15, 490 15, 490 75"
            fill="none"
            stroke="var(--color-warning)"
            strokeWidth={2}
            strokeDasharray="6 4"
            markerEnd="url(#lw-arrow-warn)"
          />
          <text x={590} y={12} fontSize={11} fill="var(--color-warning)" fontWeight={600} textAnchor="middle">
            ↻ Revision loop
          </text>

          {/* Connectors */}
          <line x1={160} y1={115} x2={220} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={360} y1={115} x2={420} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={560} y1={115} x2={620} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={760} y1={115} x2={820} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={960} y1={115} x2={1020} y2={115} stroke="var(--color-success)" strokeWidth={2.5} markerEnd="url(#lw-arrow-success)" />

          {/* Vertical arrow from Draft & Refine bottom to Artifacts label */}
          <line x1="490" y1="156" x2="490" y2="171" stroke="#6366F1" strokeWidth="2" markerEnd="url(#lw-arrow-primary)" />

          {/* ─── Six nodes with rich hover tooltips (see NODE_TOOLTIPS above).
              onMouseEnter/Leave replaces the native title= approach so the
              tooltip appears instantly with branded styling. */}

          <foreignObject x={20} y={75} width={140} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('upload', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-primary/35 rounded-2xl bg-card px-2 py-1 shadow-sm cursor-help"
            >
              <Upload className="text-foreground shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Upload BRD</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Document</span>
            </div>
          </foreignObject>

          <foreignObject x={220} y={75} width={140} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('analyze', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-primary/35 rounded-2xl bg-card px-2 py-1 shadow-sm cursor-help"
            >
              <Search className="text-primary shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Analyze BRD</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Verification</span>
            </div>
          </foreignObject>

          <foreignObject x={420} y={75} width={140} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('draft', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-ai-spark/50 rounded-2xl bg-card px-2 py-1 shadow-sm cursor-help"
            >
              <FileText className="text-ai-spark shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Draft &amp; Refine</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Multi-pass alignment</span>
            </div>
          </foreignObject>

          {/* Artifact pills below Node 3 — the 5 artifacts + RAG annotation. */}
          <foreignObject x={280} y={178} width={420} height={80}>
            <div className="w-full">
              <div className="text-[11px] text-indigo-600 dark:text-indigo-400 text-center font-bold tracking-wider mb-1.5">
                5 ARTIFACTS GENERATED
              </div>
              <div className="flex flex-nowrap items-center justify-center gap-1.5 whitespace-nowrap">
                {['PoC', 'Architect', 'Tech Stack', 'Schedule', 'Plan'].map((name) => (
                  <span
                    key={name}
                    className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-ai-spark/10 text-ai-spark border border-ai-spark/35"
                  >
                    {name}
                  </span>
                ))}
              </div>
              <div className="text-[11.5px] text-ai-spark text-center italic mt-2 font-medium">
                ↑ grounded via RAG using Organization's docs
              </div>
            </div>
          </foreignObject>

          <foreignObject x={620} y={75} width={140} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('critic', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-warning/55 rounded-2xl bg-card px-2 py-1 shadow-sm cursor-help"
            >
              <Scale className="text-warning-strong shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Critic-Verify</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Score &amp; revise loop</span>
            </div>
          </foreignObject>

          <foreignObject x={820} y={75} width={140} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('hitl', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-success/50 rounded-2xl bg-card px-2 py-1 shadow-sm cursor-help"
            >
              <UserCheck className="text-success shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">HITL Approval</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Human-in-the-loop</span>
            </div>
          </foreignObject>

          <foreignObject x={1020} y={75} width={140} height={80}>
            <div
              onMouseEnter={(e) => handleMouseEnter('export', e)}
              onMouseLeave={handleMouseLeave}
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-success rounded-2xl bg-success/10 px-2 py-1 shadow-sm cursor-help"
            >
              <div className="w-8 h-8 rounded-full bg-success flex items-center justify-center shrink-0">
                <Rocket className="text-white" size={18} />
              </div>
              <span className="text-sm font-bold text-foreground leading-tight">Export to Jira</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Epic · Sheets · Slack</span>
            </div>
          </foreignObject>
        </svg>
      </div>

      {/* ─── TIER 2: Numbered phase cards ─────────────────────────────
          4-column grid on desktop (one per phase); wraps to 2 on tablet
          and 1 on mobile. Extra vertical breathing room (mt-10 + pt-7)
          separates Tier 2 from the diagram above so the four colored
          headings feel like a distinct section rather than crowding the
          Tier 1 visual. Phase H4 uses font-semibold (not font-bold) to
          reduce visual mass — four bold colored headings in a row was
          out-shouting the marketing hero above the card. */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mt-10 border-t border-border pt-7">
        {PHASES.map((p) => (
          <div key={p.num} className="space-y-1.5">
            <div className={`h-1 rounded-full ${colorClasses[p.color].bar}`} />
            <div className="pt-1 space-y-1.5">
              <h4 className={`text-base font-semibold ${colorClasses[p.color].text}`}>
                {p.num} · {p.title}
              </h4>
              <p className="text-sm font-semibold text-foreground leading-tight">{p.tagline}</p>
              <p className="text-xs text-muted-foreground leading-relaxed">{p.body}</p>
            </div>
          </div>
        ))}
      </div>

      {/* ─── Rich hover tooltip — rendered via Portal into document.body so
          it has ZERO layout impact on the card above. Fixed positioning
          uses viewport coordinates. Fades in instantly. */}
      {tooltipState && active && typeof document !== 'undefined' && createPortal(
        <div
          className="z-50 p-3 bg-background border border-border rounded-lg shadow-2xl text-[11px] text-muted-foreground leading-relaxed pointer-events-none w-72 -translate-x-1/2 -translate-y-full animate-in fade-in zoom-in-95 duration-100"
          style={getTooltipPosition()}
        >
          <div className="flex items-center gap-1.5 mb-1.5 pb-1.5 border-b border-border font-bold text-foreground uppercase tracking-wide text-[11px]">
            <active.Icon size={13} className={`${active.iconClass} shrink-0`} />
            <span>{active.title}</span>
          </div>
          {active.desc}
          {/* Down-pointing tail — a small rotated square at bottom center,
              overlapping the tooltip's bottom border to create a triangle. */}
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1.5 w-3 h-3 rotate-45 bg-background border-r border-b border-border" />
        </div>,
        document.body
      )}
    </div>
  );
};
