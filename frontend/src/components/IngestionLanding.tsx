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


      {/* User-journey workflow diagram — story-first, non-technical audience.
          The technical System Architecture diagram (was TimelineStepper) has
          moved to the About page for engineers/technical evaluators who want
          the plumbing view. */}
      <LandingWorkflow title="How It Works" />
    </div>
  );
};
