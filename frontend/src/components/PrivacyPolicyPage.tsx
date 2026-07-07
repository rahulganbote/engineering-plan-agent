/**
 * PrivacyPolicyPage - the /#/privacy route.
 *
 * Reached from the footer/upload area of the copilot page.
 * Details the sandbox nature, data upload advisory, Jira integration, and security guardrails.
 */
import { ArrowLeft, Shield, AlertTriangle, CloudLightning, Key, Lock, Mail, Trash2, Server } from "lucide-react";
import { ThemePicker } from "./ThemePicker";

const goHome = () => {
  window.history.pushState(null, '', '/');
  window.dispatchEvent(new Event('hashchange'));
};

export const PrivacyPolicyPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans antialiased">
      {/* Sticky header mirrors AboutPage for visual continuity */}
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

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        {/* Page Title */}
        <section className="space-y-3 pb-6 border-b border-border/40">
          <h1 className="text-3xl font-extrabold tracking-tight flex items-center gap-3">
            <Shield className="text-primary" size={32} />
            Privacy & Data Security Policy
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Effective Date: July 1<sup>st</sup>, 2026. This policy describes how EM Copilot handles data, sets out expectations for sandbox users, and explains the built-in isolation and integration pipelines.
          </p>
        </section>

        {/* Advisory Block */}
        <section className="p-5 rounded-xl border border-warning/30 bg-warning/5 space-y-3">
          <div className="flex items-center gap-2 text-warning">
            <AlertTriangle size={20} />
            <h3 className="text-sm font-bold">Important Sandbox Upload Advisory</h3>
          </div>
          <p className="text-xs leading-relaxed text-foreground">
            EM Copilot is currently configured as a <strong>sandbox environment</strong>. While we implement multiple security guardrails, users are strongly advised to <strong>avoid uploading highly confidential business documentation, proprietary algorithms, or sensitive trade secrets</strong>. Do not upload documents containing unredacted customer PII (Personally Identifiable Information).
          </p>
        </section>

        {/* Three Pillar Cards */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Card 1: Jira Push */}
          <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary flex items-center gap-1.5">
              <CloudLightning size={14} />
              Automated Jira Sync
            </h3>
            <p className="text-xs leading-relaxed text-muted-foreground">
              When you decide to <strong>Approve</strong> a generated engineering plan, the synthesized project plan, sprints, schedule, components, and architecture diagrams are pushed to the configured Jira instance as a new <strong>Jira Epic</strong> containing nested Tasks. Rejections at the decision gate bypass this step and discard the sync payload. All approved-plan payloads land in the maintainer's demonstration Jira sandbox — not in your own organization's Jira, unless you deploy your own instance and configure the credentials.
            </p>
          </div>

          {/* Card 2: Tenant Isolation */}
          <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-success flex items-center gap-1.5">
              <Lock size={14} />
              Tenant Data Isolation
            </h3>
            <p className="text-xs leading-relaxed text-muted-foreground">
              EM Copilot enforces logical <strong>tenant data isolation</strong> at the session, run-state, and cache levels. Runs and documents uploaded by one authenticated user are partitioned from those of other users, preventing cross-tenant leakage or shared access in multi-user deployments. Run-state is namespaced by the authenticated user's identifier.
            </p>
          </div>

          {/* Card 3: Security Sanitization */}
          <div className="p-4 rounded-xl border border-border bg-card/40 space-y-2 md:col-span-2">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-primary flex items-center gap-1.5">
              <Key size={14} />
              Pre-Processing Sanitization & Circuit Breakers
            </h3>
            <p className="text-xs leading-relaxed text-muted-foreground">
              The Security Validator screen scans every uploaded document prior to LLM submission. It redacts common PII patterns (names, email formats, phone numbers, IP addresses) and flags potential prompt injections. Per-agent budget limits and execution circuit breakers prevent infinite processing loops.
            </p>
          </div>
        </section>

        {/* Detailed Sections */}
        <section className="space-y-6 pt-4 text-sm leading-relaxed text-foreground">
          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">1. Data Storage & Lifespans</h2>
            <p className="text-xs text-muted-foreground">
              All uploaded files and synthesized plans remain under your active run context. You can wipe this data instantly by clicking the <strong>"Clear Plan & Reset"</strong> button in the control panel. Background trace logs captured in developer consoles (such as LangSmith) are strictly used for diagnostics and debugging and do not retain raw files permanently.
            </p>
          </div>

          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">2. Model Provider Boundary</h2>
            <p className="text-xs text-muted-foreground">
              The multi-agent orchestrator makes API requests to foundation model providers (OpenAI and Anthropic — selected via the Model Selection dropdown in the control panel). By uploading a document, you acknowledge that processed BRD content and derived prompts flow through these API services. Neither OpenAI nor Anthropic uses paid-API traffic to train their models under their default enterprise API terms of service. You should still review each provider's current policy before submitting proprietary content.
            </p>
          </div>

          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">3. Third-Party Services That May See BRD Content</h2>
            <p className="text-xs text-muted-foreground">
              A run touches multiple third-party services. Uploads and the artifacts derived from them may be transmitted to the following, in this order:
            </p>
            <ul className="text-xs text-muted-foreground space-y-1 pl-4 list-disc marker:text-primary">
              <li><strong>OpenAI / Anthropic</strong> — receive the sanitized BRD text and all specialist / critic prompts.</li>
              <li><strong>Pinecone (vector database)</strong> — receives embeddings derived from the BRD for retrieval, alongside the organization's knowledge-base index.</li>
              <li><strong>Tavily (web search)</strong> — receives short, derived-metadata queries only. A helper (<code className="text-[10px] px-1 rounded bg-secondary/40">build_tavily_query</code>) constructs each query from an allowlist of ~35 safe engineering concept keywords (e.g., <em>availability, microservices, payments</em>) plus bounded structural labels (section names). Raw BRD content, customer names, and PII never leave the process boundary to Tavily.</li>
              <li><strong>GitHub API</strong> — receives repository lookup requests only (no BRD content) when the Tech Stack agent verifies library metadata.</li>
              <li><strong>Jira / Google Sheets</strong> — receive the approved plan artifacts (post-HITL approval only).</li>
              <li><strong>ElevenLabs Conversational AI</strong> — receives plan-summary context if you use the voice approval flow.</li>
              <li><strong>LangSmith</strong> — receives execution traces (prompts, responses, latencies) for observability. Retained per LangSmith retention settings (currently 14 days on this deployment).</li>
            </ul>
          </div>

          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">4. Your Rights & How to Delete Data</h2>
            <p className="text-xs text-muted-foreground">
              You can wipe your active run and all in-memory artifacts at any time using the <strong>"Clear Plan &amp; Reset"</strong> button in the sidebar. Closing your browser tab discards the client-side in-memory state (including any unsaved plans). Authentication uses a session-only cookie (<code className="text-[10px] px-1 rounded bg-secondary/40">em_copilot_session</code>) with no persistent expiry, which is cleared when the browser is closed or when you explicitly click <strong>Sign Out</strong>. No BRD content, run artifacts, or authentication tokens are persisted in browser <code className="text-[10px] px-1 rounded bg-secondary/40">localStorage</code> — the only value the frontend stores locally is your Light / Dark theme preference. For deletion of trace data captured in LangSmith, exports pushed to the demonstration Jira sandbox, or any other trailing footprint, email the maintainer using the contact below and reference the approximate date/time of your run.
            </p>
          </div>

          <div className="space-y-2">
            <h2 className="text-lg font-bold text-foreground">5. User Accountability at the HITL Gate</h2>
            <p className="text-xs text-muted-foreground">
              As the reviewing Engineering Manager, you are the final checkpoint. Every artifact generated by the specialist agents requires your explicit approval before any external sync operation runs. Verify that model outputs are safe, realistic, and compliant with your organization's internal standards before clicking approve.
            </p>
          </div>

          <div className="space-y-2 pt-2">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Server size={16} className="text-muted-foreground" />
              6. Demonstration Project Disclaimer
            </h2>
            <p className="text-xs text-muted-foreground">
              EM Copilot is an independently maintained portfolio and research demonstration, not a commercial product. It is provided <em>as-is</em>, without warranty of any kind, express or implied. Any deployment on <code className="text-[10px] px-1 rounded bg-secondary/40">emcopilot.ai</code> or a Google Cloud Run URL is for evaluation only. Do not rely on it for regulated, production, or business-critical workloads.
            </p>
          </div>

          <div className="space-y-2 pt-2">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Trash2 size={16} className="text-muted-foreground" />
              7. Data Retention Summary
            </h2>
            <ul className="text-xs text-muted-foreground space-y-1 pl-4 list-disc marker:text-muted-foreground/60">
              <li><strong>Uploaded BRD file</strong> — held in-memory for the duration of the run; discarded on reset, tab close, or process restart.</li>
              <li><strong>Run state / generated artifacts</strong> — kept in per-user in-memory maps; not persisted across server restarts on the current single-instance deployment.</li>
              <li><strong>LLM prompt / response caches</strong> — hashed keys retained per configured TTL (typically 1 hour for L1, session-length for L2 Redis if enabled).</li>
              <li><strong>Structured logs</strong> (<code className="text-[10px] px-1 rounded bg-secondary/40">logs/pipeline.jsonl</code>) — retained for developer diagnostics; rotated per operator policy.</li>
              <li><strong>LangSmith traces</strong> — retained under the LangSmith account's retention setting (14 days on this deployment).</li>
            </ul>
          </div>

          <div className="space-y-2 pt-2">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Mail size={16} className="text-muted-foreground" />
              8. Contact
            </h2>
            <p className="text-xs text-muted-foreground">
              Questions about this policy, data deletion requests, or security-disclosure reports:{" "}
              <a href="mailto:contact@emcopilot.ai" className="text-primary hover:underline font-medium">
                contact@emcopilot.ai
              </a>
              . Please allow up to seven business days for a response.
            </p>
          </div>
        </section>

        {/* Footer info */}
        <footer className="text-center pt-8 border-t border-border/40 text-xs text-muted-foreground space-y-1">
          <p>Last updated: July 1<sup>st</sup> , 2026.</p>
          <p>© 2026 EM Copilot. Independently maintained demonstration project.</p>
        </footer>
      </main>
    </div>
  );
};
