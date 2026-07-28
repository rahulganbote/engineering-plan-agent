import React from 'react';
import { MessageSquare } from 'lucide-react';

import { ThemePicker } from './ThemePicker';

interface HomepageNavProps {
  onSignIn: (variant?: 'signin' | 'signup') => void;
  onFeedbackClick: () => void;
}

// Standalone marketing top-nav — signed-out landing only. Replaces the
// app-workspace header entirely for this state (rather than layering CTAs
// onto it) so the landing reads as a product page, not a dashboard with
// login buttons bolted on. Matches the approved top-nav + full-width
// landing mockup: logo left, section links centered-right, Sign in +
// Get started right. Both buttons open the same AuthPromptModal — that's
// the deliberate two-CTA SaaS pattern from the mockup (ghost "Sign in" for
// returning users, solid "Get started" for new visitors), not duplication.
export const HomepageNav: React.FC<HomepageNavProps> = ({ onSignIn, onFeedbackClick }) => {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    // Background bar goes full-bleed; inner content aligns to the same
    // max-w-6xl column as the page body so the logo/CTA line up with the
    // hero and cards below instead of floating at the browser edges.
    <header className="border-b border-border bg-card px-6 py-3 shrink-0 shadow-sm">
      <div className="max-w-5xl mx-auto flex items-center justify-between">
        <a href="#/" className="flex items-center gap-2 shrink-0">
          <img src="/favicon.svg" alt="" aria-hidden="true" className="w-6 h-6" />
          <span className="flex flex-col leading-tight">
            <span className="text-base font-extrabold tracking-tight text-primary">EM Copilot</span>
            <span className="hidden sm:block text-[10px] font-semibold text-muted-foreground tracking-wide">
              Next Gen Software Engineering Planning
            </span>
          </span>
        </a>

        <nav className="hidden md:flex items-center gap-1">
          <button
            onClick={() => scrollTo('see-it-in-action')}
            className="text-sm font-semibold text-muted-foreground hover:text-primary transition px-3 py-1.5 rounded-lg hover:bg-secondary/40"
          >
            How it works
          </button>
          <button
            onClick={() => scrollTo('how-it-works')}
            className="text-sm font-semibold text-muted-foreground hover:text-primary transition px-3 py-1.5 rounded-lg hover:bg-secondary/40"
          >
            Platform
          </button>
          <a
            href="#/about"
            className="text-sm font-semibold text-muted-foreground hover:text-primary transition px-3 py-1.5 rounded-lg hover:bg-secondary/40"
          >
            About
          </a>
        </nav>

        <div className="flex items-center gap-3 shrink-0">
          {/* Utility cluster — icon-only, muted, tightly grouped. Kept
              visually secondary so Sign in / Get started stay the clear
              endpoint for a first-time visitor. */}
          <div className="hidden sm:flex items-center gap-0.5">
            <button
              onClick={onFeedbackClick}
              aria-label="Feedback"
              title="Feedback"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            >
              <MessageSquare size={14} />
            </button>
            <ThemePicker />
          </div>
          <div className="border-r border-border h-4 hidden sm:block" />
          <div className="flex items-center gap-2">
            <button
              onClick={() => onSignIn('signup')}
              className="text-sm font-bold text-white bg-primary hover:bg-primary/90 transition px-4 py-1.5 rounded-lg shadow-sm"
            >
              Get started
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
