import React from 'react';
import { LandingWorkflow } from './LandingWorkflow';

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
  selectedFile: _selectedFile,
  isAuthenticated: _isAuthenticated,
}) => {
  return (
    <div className="space-y-3 w-full py-2">
      {/* Welcome & Subtitle Section */}
      <div className="space-y-1.5">
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Transform a BRD into an Engineering Plan in minutes, grounded in RAG
        </h2>
        <p className="text-xs text-muted-foreground max-w-3xl">
          EM Copilot transforms raw Business Requirements Documents into audit-ready engineering plans, grounded via RAG in your organization's own architectural patterns and approved tech stack. Artifacts are presented for review; on approval, pushed to Jira.
        </p>
      </div>


      {/* Loom demo video — shows the pipeline in motion so visitors feel the
          "AI-in-action" energy before they even sign in. Placed above the
          How-It-Works diagram so the sequence reads: pitch → watch it work
          → understand the mechanics.
          Card width capped at max-w-3xl (768px) so the 16:9 video renders at
          ~432px tall — leaving the How-It-Works card visible below in the
          same viewport (fixes the "first-time visitors miss the diagram"
          bug where a full-width video pushed everything below the fold).
          Loom URL params (hide_owner, hide_title, hideEmbedTopBar) strip the
          player chrome for a clean branded look. */}
      <div className="w-full max-w-2xl mx-auto bg-card border border-border rounded-xl p-3 md:p-4 shadow-lg space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-black text-primary uppercase tracking-wider"> 
            See It in Action
          </h3>
          <span className="text-[10px] text-muted-foreground font-semibold tracking-wider">
            97s · DEMO
          </span>
        </div>
        <div className="relative w-full aspect-video rounded-lg overflow-hidden border border-border bg-muted/30">
          <iframe
            src="https://www.loom.com/embed/b45c127069f84573b0a713a241155214?hide_owner=true&hide_title=true&hideEmbedTopBar=true"
            className="absolute inset-0 w-full h-full"
            allowFullScreen
            allow="fullscreen; picture-in-picture"
            title="EM Copilot demo — BRD to Engineering Plan in minutes"
          />
        </div>
      </div>

      {/* User-journey workflow diagram — story-first, non-technical audience.
          The technical System Architecture diagram (was TimelineStepper) has
          moved to the About page for engineers/technical evaluators who want
          the plumbing view. */}
      <LandingWorkflow title="How It Works" />
    </div>
  );
};
