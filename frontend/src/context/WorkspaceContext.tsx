import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { useSSE, type LogEvent, type CriticOutput, type ApprovalResult, type ArtifactsState } from '../hooks/useSSE';
import { type PipelineStatus } from '../lib/pipelineStatus';

interface WorkspaceContextType {
  runId: string | null;
  setRunId: (runId: string | null) => void;
  apiBaseUrl: string;
  setApiBaseUrl: (url: string) => void;
  logs: LogEvent[];
  pipelineStatus: PipelineStatus;
  completedAgents: Set<string>;
  artifacts: ArtifactsState | null;
  elapsedSeconds: number;
  tokenUsage: { input: number; output: number } | null;
  costUsd: number | null;
  criticOutput: CriticOutput | null;
  approvalResult: ApprovalResult | null;
  clearRun: (newStatus?: PipelineStatus) => void;
  fetchArtifacts: () => Promise<void>;
  setPipelineStatus: (status: PipelineStatus) => void;
  setApprovalResult: (result: ApprovalResult | null) => void;
  errorMessage: string | null;
  longRunningWarning: string | null;
  fallbackActive: { from: string; to: string } | null;
  elevenlabsAgentId: string;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider = ({ children }: { children: ReactNode }) => {
  const [runId, setRunId] = useState<string | null>(null);
  const [apiBaseUrl, setApiBaseUrl] = useState<string>(() => {
    // Default to the current window host if not local, otherwise proxy is used.
    if (typeof window !== 'undefined') {
      return window.location.origin;
    }
    // Fallback to 127.0.0.1 instead of localhost to bypass macOS IPv6 resolution delays.
    return 'http://127.0.0.1:8000';
  });
  const [elevenlabsAgentId, setElevenlabsAgentId] = useState<string>('');

  // Fetch ElevenLabs widget config on component mount
  useEffect(() => {
    fetch(`${apiBaseUrl}/api/config`)
      .then(r => r.json())
      .then(cfg => setElevenlabsAgentId(cfg.elevenlabs_agent_id || ''))
      .catch(err => console.error('Failed to load ElevenLabs config:', err));
  }, [apiBaseUrl]);

  const sseData = useSSE(runId, apiBaseUrl);

  return (
    <WorkspaceContext.Provider
      value={{
        runId,
        setRunId,
        apiBaseUrl,
        setApiBaseUrl,
        ...sseData,
        elevenlabsAgentId,
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
