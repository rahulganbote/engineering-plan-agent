import React from 'react';

interface MarketingNavProps {
  onSignIn: () => void;
}

// Standalone marketing top-nav — signed-out landing only. Replaces the
// app-workspace header entirely for this state (rather than layering CTAs
// onto it) so the landing reads as a product page, not a dashboard with
// login buttons bolted on. Matches the approved top-nav + full-width
// landing mockup: logo left, section links centered-right, Sign in +
// Get started right. Both buttons open the same AuthPromptModal — that's
// the deliberate two-CTA SaaS pattern from the mockup (ghost "Sign in" for
// returning users, solid "Get started" for new visitors), not duplication.
export const MarketingNav: React.FC<MarketingNavProps> = ({ onSignIn }) => {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <header className="border-b border-border bg-card px-6 py-3 flex items-center justify-between shrink-0 shadow-sm">
      <a href="#/" className="flex items-center gap-2 shrink-0">
        <span className="w-6 h-6 rounded-md bg-primary" aria-hidden="true" />
        <span className="text-base font-extrabold tracking-tight text-primary">EM Copilot</span>
      </a>

      <nav className="hidden md:flex items-center gap-1">
        <button
          onClick={() => scrollTo('how-it-works')}
          className="text-sm font-semibold text-muted-foreground hover:text-primary transition px-3 py-1.5 rounded-lg hover:bg-secondary/40"
        >
          How it works
        </button>
        <button
          onClick={() => scrollTo('see-it-in-action')}
          className="text-sm font-semibold text-muted-foreground hover:text-primary transition px-3 py-1.5 rounded-lg hover:bg-secondary/40"
        >
          See it in action
        </button>
        <a
          href="#/about"
          className="text-sm font-semibold text-muted-foreground hover:text-primary transition px-3 py-1.5 rounded-lg hover:bg-secondary/40"
        >
          About
        </a>
      </nav>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onSignIn}
          className="text-sm font-semibold text-muted-foreground hover:text-primary transition px-3 py-1.5 rounded-lg"
        >
          Sign in
        </button>
        <button
          onClick={onSignIn}
          className="text-sm font-bold text-white bg-primary hover:bg-primary/90 transition px-4 py-1.5 rounded-lg shadow-sm"
        >
          Get started
        </button>
      </div>
    </header>
  );
};
