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
  selectedFile,
  isAuthenticated,
}) => {
  return (
    <div className="space-y-3 w-full py-2">
      {/* Welcome & Subtitle Section */}
      <div className="space-y-1.5">
        <h2 className="text-base font-semibold tracking-tight text-foreground">
          Transform a BRD into an Engineering Plan in Minutes, grounded in RAG
        </h2>
        <p className="text-xs text-muted-foreground max-w-3xl">
          EM Copilot transforms raw Business Requirements Documents into audit-ready engineering plans, grounded via RAG in your organization's own architectural patterns and approved tech stack. Artifacts are presented for review; on approval, pushed to Jira.
        </p>
      </div>

      {/* Welcome Callout for logged in, pre-upload state */}
      {/* Integrated Action Token — Locked to your strict Amber Yellow Theme */}
      {isAuthenticated && !selectedFile && (
        <div className="flex items-center gap-1.5 px-3 py-1 bg-amber-500/5 border border-amber-500/20 rounded-lg text-[10px] font-bold text-amber-600 dark:text-amber-400 animate-pulse shrink-0 self-start sm:self-center shadow-sm">
          <span>Next Step:</span> Drag & drop a BRD file on the left panel to begin.
        </div>
      )}
      {/*
      {isAuthenticated && !selectedFile && (
        <div className="flex items-center gap-1 p-3 bg-[#f0f7ff] dark:bg-sky-950/20 border border-sky-200 dark:border-sky-800/40 rounded-lg text-xs text-sky-800 dark:text-sky-300 font-medium animate-in fade-in slide-in-from-top-1 duration-200 mt-3.5 mb-5 shadow-sm">
        <span><strong>Next Step:</strong> Drag and drop a BRD file on the left to generate your engineering plan.</span>
        </div>
      )}
      */}
      {/* User-journey workflow diagram — story-first, non-technical audience.
          The technical System Architecture diagram (was TimelineStepper) has
          moved to the About page for engineers/technical evaluators who want
          the plumbing view. */}
      <LandingWorkflow title="How It Works" />
    </div>
  );
};
