/**
 * IntegrationNotConfigured - shared fallback hint for optional integrations
 * (Jira, Tavily, ElevenLabs Voice, GitHub) that aren't set up on a deployment.
 *
 * Same visual pattern across all four surfaces so users learn the convention:
 *   - Muted card surface (signals "not an error, just missing")
 *   - Bold title + plain-language description
 *   - Required env var(s) shown as code chips
 *   - "View setup reference →" link to .env.example on GitHub (anchored)
 */
import React from "react";

const REPO_DOCS_BASE =
  "https://github.com/rahulganbote/engineering-plan-agent/blob/main/.env.example";

interface IntegrationNotConfiguredProps {
  /** Short title shown in bold - e.g. "Jira push not available". */
  title: string;
  /** Required env vars shown as inline <code> chips. */
  envVars: string[];
  /** Plain-language description of what the feature does. */
  description: string;
  /** Anchor at the docs base, e.g. "#L59-L65" to jump to the Jira section. */
  docsAnchor?: string;
  /** Optional override for the docs link CTA label. */
  ctaLabel?: string;
}

export const IntegrationNotConfigured: React.FC<IntegrationNotConfiguredProps> = ({
  title,
  envVars,
  description,
  docsAnchor = "",
  ctaLabel = "View setup reference (.env.example) →",
}) => {
  return (
    <div className="p-4 bg-card border border-border rounded-lg space-y-2 animate-fade-in">
      <div className="text-xs font-bold text-muted-foreground">{title}</div>
      <div className="text-[11px] text-muted-foreground leading-relaxed">
        {description}{" "}
        Configure
        {envVars.map((v, i) => (
          <React.Fragment key={v}>
            {" "}
            <code className="mx-0.5 px-1 py-0.5 rounded bg-secondary text-foreground font-mono">
              {v}
            </code>
            {i < envVars.length - 1 ? "," : ""}
          </React.Fragment>
        ))}{" "}
        to enable it.
      </div>
      <a
        href={`${REPO_DOCS_BASE}${docsAnchor}`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:text-primary/80 hover:underline transition-colors"
      >
        {ctaLabel}
      </a>
    </div>
  );
};
