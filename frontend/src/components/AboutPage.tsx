/**
 * AboutPage - the /#/about route.
 *
 * Reached from the "Who built this?" link on the auth gate (and a footer link).
 * Tells visitors who built EM Copilot, what it is, the engineering principles
 * behind it, and how to make contact. Theme-aware via the same tokens the rest
 * of the app uses.
 *
 * Linkified "Principles" section points each rule of thumb at the matching
 * section in the public demo README, so the page doubles as a navigable index
 * into the engineering reasoning.
 */
import { ArrowLeft, ExternalLink, Mail, Link2, Cpu, Coins, ShieldCheck, Shield, Wrench, CheckCircle } from "lucide-react";
import { ThemePicker } from "./ThemePicker";

const DEMO_REPO_URL = "https://github.com/rahulganbote/engineering-plan-agent-demo";

const PRINCIPLES: Array<{ headline: string; body: string; anchor: string }> = [
  {
    headline: "Start simple.",
    body: "Default to a single agent and earn every extra one. Use modular design, build for evaluation, and think about reliability from day one.",
    anchor: "#challenges--lessons-learned",
  },
  {
    headline: "Clarity beats cleverness.",
    body: "Router, Planner/Executor, Multi-Agent, Reflection, Human Escalation are well-worn patterns for a reason; reach for them before inventing.",
    anchor: "#architectural-overview",
  },
  {
    headline: "Structure everything.",
    body: "Plans, tool contracts, agent outputs, handoffs. If it's not structured, it's not production-ready.",
    anchor: "#tech-stack-justification",
  },
  {
    headline: "Design for failure.",
    body: "Assume tools fail, agents disagree, and users are confused, then show how your system survives.",
    anchor: "#system-design--core-pillars",
  },
  {
    headline: "Measure what matters.",
    body: "Success rate, escalation quality, cost, latency, and trust.",
    anchor: "#evaluation-framework",
  },
];

const goHome = () => {
  window.history.pushState(null, '', '/');
  window.dispatchEvent(new Event('hashchange'));
};

export const AboutPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans antialiased">
      {/* Sticky header mirrors AgentWorkspace for visual continuity */}
      <header className="sticky top-0 z-30 bg-background/90 backdrop-blur border-b border-border">
        <div className="max-w-3xl mx-auto px-6 min-h-16 flex items-center justify-between gap-4 py-3">
          <button
            onClick={goHome}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition font-semibold"
            aria-label="Back to Copilot"
          >
            <ArrowLeft size={16} />
            <span>Back to Copilot</span>
          </button>
          <div className="flex items-center gap-4">
            <span className="text-sm font-bold text-primary">EM Copilot</span>
            <ThemePicker />
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-6 space-y-6">
        {/* About EM Copilot */}
        <section className="space-y-6 border-b border-border/40 pb-6">
          <div className="space-y-2">
            <h2 className="text-2xl font-bold tracking-tight">About EM Copilot</h2>
            <p className="text-sm text-muted-foreground">
              EM Copilot is built with enterprise requirements in mind. Below is a structural overview of its core features and capabilities.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Summary */}
            <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary flex items-center gap-1.5">
                <CheckCircle size={14} />
                Summary
              </h3>
              <p className="text-xs leading-relaxed text-foreground">
                A production-grade, RAG-augmented multi-agent AI system that automates the translation of Business Requirements Documents (BRDs) into audit-ready engineering deliverables: namely, an Engineering Plan, System Architecture, Project Schedule, Tech Stack recommendation, and PoC, all ready for a manager to review, and push into Jira upon approval.
              </p>
            </div>

            {/* Enterprise Grade */}
            <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-ai-spark flex items-center gap-1.5">
                <Cpu size={14} />
                Enterprise Grade
              </h3>
              <p className="text-xs leading-relaxed text-foreground">
                Multi-Agent Orchestration built on LangGraph with Pinecone RAG for knowledge grounding, Pydantic contracts, a multi-stage BRD sanitization security (PII redaction, format validation, and prompt injection protection), isolated resilience, a dual-tier (L1/L2) cache, multi-provider LLM with intelligent failover, and full execution observability via LangSmith.
              </p>
            </div>

            {/* AI Governance */}
            <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-success flex items-center gap-1.5">
                <ShieldCheck size={14} />
                AI Governance
              </h3>
              <p className="text-xs leading-relaxed text-foreground">
                <strong>$2.00 per-run budget ceiling</strong>. Citation-grounded outputs via a vector database, Quality Gate (F3-Score across 5 dimensions) and self-correcting Critic loop on every run: a measured <strong>28% lift in plan quality</strong> (3.38 → 4.33 on a 5-point scale). Quality Gate presents audit-readiness scoring with Green/Amber/Red badge, and <strong>Human-in-the-Loop (HITL)</strong> review & approval before taking any irreversible action.
              </p>
            </div>

            {/* Resilience & Guardrails */}
            <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-ai-spark flex items-center gap-1.5">
                <Shield size={14} />
                Resilience & Guardrails
              </h3>
              <p className="text-xs leading-relaxed text-foreground">
                Pre-defined Contracts, Intelligent Multi-provider LLM Failover, Per-agent Circuit Breakers, Bulkhead Isolation (per-provider + per-family + global), per-tenant data isolation and an innovative <strong>idempotent approval</strong>.
              </p>
            </div>

            {/* Tools & Integrations */}
            <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2 md:col-span-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-warning flex items-center gap-1.5">
                <Wrench size={14} />
                Tools & Integrations
              </h3>
              <p className="text-xs leading-relaxed text-foreground">
                Tavily Search, Voice AI (ElevenLabs) support for HITL, and direct export handlers (Google Sheets, ReportLab PDF, and Jira Epic creation via MCP), and Slack alerts.
              </p>
            </div>
          </div>

          {/* ROI Callout Box */}
          <div className="border-l-4 border-primary bg-secondary/35 p-5 rounded-r-xl space-y-3">
            <div className="flex items-center gap-2">
              <Coins className="text-primary" size={18} />
              <h4 className="text-sm font-bold text-foreground">The ROI</h4>
            </div>
            <p className="text-xs leading-normal text-foreground font-semibold">
              Reduces planning scoping and drafting from days to under two minutes.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
              <div className="space-y-1 bg-background/55 p-3 rounded-lg border border-border/40">
                <span className="text-[10px] uppercase font-bold text-muted-foreground block tracking-wider">Latency Comparison</span>
                <div className="text-xs font-medium space-y-0.5 text-foreground">
                  <p><strong>OpenAI (n=13):</strong> p50 ~26s · p95 ~72s</p>
                  <p><strong>Anthropic (n=9):</strong> p50 ~86s · p95 ~102s <span className="text-muted-foreground">(~2.2× latency)</span></p>
                </div>
              </div>
              <div className="space-y-1 bg-background/55 p-3 rounded-lg border border-border/40">
                <span className="text-[10px] uppercase font-bold text-muted-foreground block tracking-wider">Median Cost per Run</span>
                <div className="text-xs font-medium space-y-0.5 text-foreground">
                  <p><strong>OpenAI:</strong> ~$0.08 per run</p>
                  <p><strong>Anthropic:</strong> ~$0.20 per run <span className="text-muted-foreground">(~2.5× cost; ~20-50% higher token rate)</span></p>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-3 pt-2">
            <p className="text-sm leading-relaxed text-foreground">
              The public demo repository below has detailed design documents, evaluation framework, and a mock pipeline anyone can run without API keys. The production prompts, RAG ingestion logic, production pipeline and integration logic stay in a private repository.
            </p>
            <a
              href={DEMO_REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
            >
              Browse Github public demo repo
              <ExternalLink size={14} />
            </a>
          </div>
        </section>
        {/* About Me */}
        <section className="space-y-4 border-b border-border/40 pb-6">
          <h1 className="text-3xl font-extrabold tracking-tight">About Me</h1>
          <p className="text-sm leading-relaxed text-foreground">
            I'm Rahul Ganbote. My forte is taking a business need or a client goal, building a PoC, and operationalizing it into a reliable AI system. I handle the design, cost, security, and scalability decisions required to turn a prototype into a product in production. Adoption and reliability are the metrics I measure my work against, and observability belongs in the product from day one.
          </p>
        </section>

        {/* Principles behind EM Copilot */}
        <section className="space-y-2 border-b border-border/40 pb-4">
          <h2 className="text-2xl font-bold tracking-tight">
            Principles behind EM Copilot
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Five rules of thumb that were followed while building EM Copilot, and that I bring into every system.
          </p>
          <ul className="space-y-2 pt-1">
            {PRINCIPLES.map((p) => (
              <li key={p.headline} className="text-sm leading-relaxed space-y-0">
                <a
                  href={`${DEMO_REPO_URL}${p.anchor}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-bold text-primary hover:underline block w-fit"
                >
                  {p.headline}
                </a>
                <p className="text-muted-foreground leading-normal text-xs">{p.body}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* What I'm Looking For */}
        <section className="space-y-3 border-b border-border/40 pb-6">
          <h2 className="text-2xl font-bold tracking-tight">What I'm Looking For</h2>
          <p className="text-sm leading-relaxed text-foreground">
            If you're building something in AI space and would like to discuss, I am just a message away.
          </p>
        </section>
        <section className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">Contact</h2>
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-3">
              <Mail size={14} className="text-muted-foreground shrink-0" />
              <a
                href="mailto:contact@emcopilot.ai"
                className="text-primary hover:underline font-medium"
              >
                contact@emcopilot.ai
              </a>
            </li>
            <li className="flex items-center gap-3">
              <Link2 size={14} className="text-muted-foreground shrink-0" />
              <a
                href="https://www.linkedin.com/in/rahul-ganbote-040a7b/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline font-medium"
              >
                LinkedIn: linkedin.com/in/rahul-ganbote
              </a>
            </li>
            <li className="flex items-center gap-3">
              <Link2 size={14} className="text-muted-foreground shrink-0" />
              <a
                href="https://github.com/rahulganbote"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline font-medium"
              >
                GitHub: github.com/rahulganbote
              </a>
            </li>
          </ul>
        </section>

        {/* Footer */}
        <footer className="pt-8 border-t border-border text-center flex flex-col items-center justify-between gap-4 sm:flex-row">
          <button
            onClick={goHome}
            className="text-xs text-muted-foreground hover:text-foreground transition font-semibold"
          >
            ← Back to demo
          </button>
          <span className="text-xs text-muted-foreground font-medium">
            © 2026 Rahul Ganbote · All rights reserved.
          </span>
        </footer>
      </main>
    </div>
  );
};
