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
 *   - foreignObject wraps lucide icons + HTML text inside the SVG so we can
 *     use the shared Tailwind utility classes for typography and native HTML
 *     `title=` tooltips without inventing an SVG-native tooltip system.
 *   - Tightened geometry (viewBox 1160×300): the whole diagram fits without
 *     horizontal scroll on ~1200px+ viewports so the terminal "Export to Jira"
 *     node stays visible above the fold.
 *
 * NOT for pipeline progress — LandingWorkflow is static and marketing-facing.
 * The live pipeline state visualization lives in TimelineStepper (now moved
 * off the landing page onto the About page for technical evaluators).
 */

import React from 'react';
import { Upload, Search, FileText, Scale, UserCheck, Rocket } from 'lucide-react';

// ─── Phase card data (bottom tier) ─────────────────────────────────────────
// Kept as data (not JSX) so the four cards render via a single .map() with a
// consistent structure — easier to reorder, translate, or extend later.
const PHASES: Array<{
  num: string;
  title: string;
  tagline: string;
  body: string;
  /** Tailwind color-shorthand keys resolved via colorClasses below. */
  color: 'primary' | 'ai-spark' | 'warning' | 'success';
}> = [
  {
    num: '1',
    title: 'Analyze',
    color: 'primary',
    tagline: 'Upload & understand the BRD.',
    body: "You drop in a Business Requirements Doc; the AI extracts requirements and passes safety checks before drafting.",
  },
  {
    num: '2',
    title: 'Generate',
    color: 'ai-spark',
    tagline: 'Draft five deliverables in parallel.',
    body: "Specialist agents produce PoC, Architect, Tech Stack, Schedule, and Plan — grounded via RAG in your team's own docs.",
  },
  {
    num: '3',
    title: 'Verify',
    color: 'warning',
    tagline: 'Critic grades and self-corrects.',
    body: 'Four-dimension score (Groundedness, Completeness, Consistency, Actionability). Loops back to Generate if gate fails.',
  },
  {
    num: '4',
    title: 'Ship',
    color: 'success',
    tagline: 'You approve; it ships everywhere.',
    body: 'Manager review gate. On approval, plan writes to Jira Epic, logs to Sheets, and pings Slack — audit trail preserved.',
  },
];

// Token-driven class maps. Keeping bar/text pairs together avoids drift when
// we add a new phase color later; the compiler catches missing entries.
const colorClasses: Record<
  'primary' | 'ai-spark' | 'warning' | 'success',
  { bar: string; text: string }
> = {
  primary:    { bar: 'bg-primary',   text: 'text-primary' },
  'ai-spark': { bar: 'bg-ai-spark',  text: 'text-ai-spark' },
  warning:    { bar: 'bg-warning',   text: 'text-warning-strong' },
  success:    { bar: 'bg-success',   text: 'text-success' },
};

interface LandingWorkflowProps {
  /** Optional header override. Default: "How It Works". */
  title?: string;
}

export const LandingWorkflow: React.FC<LandingWorkflowProps> = ({ title }) => {
  return (
    <div className="w-full bg-card border border-border rounded-xl p-3 md:p-4 shadow-lg space-y-4">
      {/* Header — matches the standardized section-title treatment. */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-black text-primary uppercase tracking-wider">
          {title || 'How It Works'}
        </h3>
      </div>

      {/* ─── TIER 1: SVG workflow chain ─────────────────────────────────
          overflow-x-auto keeps a graceful fallback on very narrow viewports.
          min-w-[880px] means on ~1200px+ laptops the whole diagram fits
          without scroll — critical for keeping the "Export to Jira" terminal
          node visible above the fold. */}
      <div className="overflow-x-auto -mx-1 md:mx-0">
        <svg
          viewBox="0 0 1160 250"
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-labelledby="lw-title lw-desc"
          className="w-full h-auto min-w-[880px]"
        >
          <title id="lw-title">EM Copilot user workflow</title>
          <desc id="lw-desc">
            Six-step user journey from BRD upload to Jira export, with a
            self-verification revision loop and human approval gate.
          </desc>

          <defs>
            {/* Three arrowhead variants matching the three semantic edge colors
                (neutral connector, warning revision loop, success terminal). */}
            <marker id="lw-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-muted-foreground)" />
            </marker>
            <marker id="lw-arrow-warn" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-warning)" />
            </marker>
            <marker id="lw-arrow-success" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-success)" />
            </marker>
          </defs>

          {/* Revision loop: dashed amber curve from Critic-Verify back to Draft.
              Anchor points at node tops (y=75). Curve arcs up to y=15. */}
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

          {/* Straight connector arrows between adjacent nodes. Node y-center
              = 75+40 = 115. Node x-positions: 20, 220, 420, 620, 820, 1020. */}
          <line x1={160} y1={115} x2={220} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={360} y1={115} x2={420} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={560} y1={115} x2={620} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          <line x1={760} y1={115} x2={820} y2={115} stroke="var(--color-muted-foreground)" strokeWidth={2} markerEnd="url(#lw-arrow)" />
          {/* Final leg gets the success color to signal "handoff to shipped" */}
          <line x1={960} y1={115} x2={1020} y2={115} stroke="var(--color-success)" strokeWidth={2.5} markerEnd="url(#lw-arrow-success)" />

          {/* ─── Six nodes: icon-on-top, label-below (vertical stack).
              Node dims: 140w × 80h. Position y=75 (arrow center at 115).
              Every node has a native HTML `title=` tooltip — hover for detail. */}

          {/* NODE 1 · Upload BRD ─── Phase 1 (Analyze, primary) */}
          <foreignObject x={20} y={75} width={140} height={80}>
            <div
              title="Upload a Business Requirements Document (PDF, DOCX, or TXT) to kick off the pipeline."
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-primary/35 rounded-2xl bg-card px-2 py-1 shadow-sm"
            >
              <Upload className="text-foreground shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Upload BRD</span>
              <span className="text-[10px] text-muted-foreground leading-tight">PDF · DOCX · TXT</span>
            </div>
          </foreignObject>

          {/* NODE 2 · Analyze BRD ─── Phase 1 (Analyze, primary) */}
          <foreignObject x={220} y={75} width={140} height={80}>
            <div
              title="The AI parses your BRD, extracts requirements, and runs safety checks before drafting."
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-primary/35 rounded-2xl bg-card px-2 py-1 shadow-sm"
            >
              <Search className="text-primary shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Analyze BRD</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Extract requirements</span>
            </div>
          </foreignObject>

          {/* NODE 3 · Draft & Refine ─── Phase 2 (Generate, ai-spark) */}
          <foreignObject x={420} y={75} width={140} height={80}>
            <div
              title="Five specialist agents draft artifacts in parallel with multi-pass alignment refinement."
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-ai-spark/50 rounded-2xl bg-card px-2 py-1 shadow-sm"
            >
              <FileText className="text-ai-spark shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Draft &amp; Refine</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Multi-pass alignment</span>
            </div>
          </foreignObject>

          {/* Artifact pills below Node 3 — the 5 deliverables + RAG annotation.
              Single row (flex-nowrap) so all five stay visible; container
              widened past Node 3's footprint so "Plan" doesn't drop to a
              second line. RAG grounding note sits BELOW the pills so it
              doesn't compete with the arrows above. */}
          <foreignObject x={280} y={175} width={420} height={80}>
            <div className="w-full">
              <div className="text-[12px] text-success text-center font-semibold tracking-wider mb-1">
                ↓ 5 DELIVERABLES GENERATED
              </div>
              <div className="flex flex-nowrap items-center justify-center gap-1.5 whitespace-nowrap">
                {['PoC', 'Architect', 'Tech Stack', 'Schedule', 'Plan'].map((name) => (
                  <span
                    key={name}
                    className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-ai-spark/10 text-ai-spark border border-ai-spark/35"
                  >
                    {name}
                  </span>
                ))}
              </div>
              <div className="text-[12px] text-ai-spark text-center italic mt-2">
                ↑ grounded via RAG
              </div>
            </div>
          </foreignObject>

          {/* NODE 4 · Critic-Verify ─── Phase 3 (Verify, ai-spark) */}
          <foreignObject x={620} y={75} width={140} height={80}>
            <div
              title="Independent Critic grades outputs on 4 dimensions (Groundedness, Completeness, Consistency, Actionability) and triggers a revision loop if the quality gate fails."
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-ai-spark/50 rounded-2xl bg-card px-2 py-1 shadow-sm"
            >
              <Scale className="text-ai-spark shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">Critic-Verify</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Score &amp; revise loop</span>
            </div>
          </foreignObject>

          {/* NODE 5 · HITL Approval ─── Phase 4 (Ship, warning) */}
          <foreignObject x={820} y={75} width={140} height={80}>
            <div
              title="You review the deliverables and approve — or reject with notes to trigger another revision."
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-warning/55 rounded-2xl bg-card px-2 py-1 shadow-sm"
            >
              <UserCheck className="text-warning-strong shrink-0" size={30} />
              <span className="text-sm font-bold text-foreground leading-tight">HITL Approval</span>
              <span className="text-[10px] text-muted-foreground leading-tight">Human-in-the-loop</span>
            </div>
          </foreignObject>

          {/* NODE 6 · Export to Jira ─── Phase 4 (Ship, success) */}
          <foreignObject x={1020} y={75} width={140} height={80}>
            <div
              title="On approval, the plan writes to a Jira Epic, logs to Google Sheets, and pings Slack - audit trail preserved."
              className="w-full h-full flex flex-col items-center justify-center gap-0.5 border border-success rounded-2xl bg-success/10 px-2 py-1 shadow-sm"
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
          Same story told in prose. Responsive grid: 1 col mobile,
          2 col tablet, 4 col desktop. Colored top bar mirrors the node
          borders above so the two tiers read as one system. */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 border-t border-border pt-4">
        {PHASES.map((p) => (
          <div key={p.num} className="space-y-1.5">
            <div className={`h-1 rounded-full ${colorClasses[p.color].bar}`} />
            <div className="pt-1 space-y-1">
              <h4 className={`text-base font-bold ${colorClasses[p.color].text}`}>
                {p.num} · {p.title}
              </h4>
              <p className="text-sm font-semibold text-foreground">{p.tagline}</p>
              <p className="text-xs text-muted-foreground leading-relaxed">{p.body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
