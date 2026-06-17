import { createContext, useContext, useState, type ReactNode } from 'react';
import { useSSE, type LogEvent, type CriticOutput, type ApprovalResult, type ArtifactsState } from '../hooks/useSSE';

interface WorkspaceContextType {
  runId: string | null;
  setRunId: (runId: string | null) => void;
  apiBaseUrl: string;
  setApiBaseUrl: (url: string) => void;
  logs: LogEvent[];
  pipelineStatus: string;
  completedAgents: Set<string>;
  artifacts: ArtifactsState | null;
  elapsedSeconds: number;
  tokenUsage: { input: number; output: number } | null;
  criticOutput: CriticOutput | null;
  approvalResult: ApprovalResult | null;
  clearRun: () => void;
  fetchArtifacts: () => Promise<void>;
  setPipelineStatus: (status: string) => void;
  setApprovalResult: (result: ApprovalResult | null) => void;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider = ({ children }: { children: ReactNode }) => {
  const [runId, setRunId] = useState<string | null>(null);
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(() => {
    // Default to the current window host if not local, otherwise proxy is used.
    if (typeof window !== 'undefined') {
      return window.location.origin;
    }
    return 'http://localhost:8000';
  });

  const sseData = useSSE(runId, apiBaseUrl);

  return (
    <WorkspaceContext.Provider
      value={{
        runId,
        setRunId,
        apiBaseUrl,
        setApiBaseUrl,
        ...sseData,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error('useWorkspace must be used within a WorkspaceProvider');
  return context;
};
