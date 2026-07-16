import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useWorkspace } from '../context/WorkspaceContext';
import { useAuth } from '../context/AuthContext';
import { PlanSkeleton } from './PlanSkeleton';
import { ErrorBoundary } from './ErrorBoundary';
import { HITLApprovalGate, type ApprovalResponse } from './HITLApprovalGate';
import { apiFetch } from '../lib/apiClient';
import { IngestionLanding } from './IngestionLanding';
import { TimelineStepper } from './TimelineStepper';
import { type PipelineStatus, PIPELINE_STATUS, CANCELLABLE_STATES } from '../lib/pipelineStatus';
import { LogConsole } from './LogConsole';
import { CriticFindings } from './CriticFindings';
import { PlanTab } from './PlanTab';
import { ScheduleTab } from './ScheduleTab';
import { ArchitectureTab } from './ArchitectureTab';
import { PoCTab } from './PoCTab';
import { TechStackTab } from './TechStackTab';
import { X, LogOut, Upload, ShieldAlert, ChevronDown, ChevronUp, Download, Copy, Check, Loader2, Plus } from 'lucide-react';
import { ThemePicker } from './ThemePicker';
import { generateVoiceBrief } from '../lib/voiceBrief';
import { IntegrationNotConfigured } from './IntegrationNotConfigured';
import FeedbackModal from './FeedbackModal';
import ConsentModal from './ConsentModal';
import { type AlignmentDirective } from '../hooks/useSSE';

/* eslint-disable @typescript-eslint/no-namespace */
declare global {
  namespace React {
    namespace JSX {
      interface IntrinsicElements {
        'elevenlabs-convai': React.DetailedHTMLProps<
          React.HTMLAttributes<HTMLElement> & {
            'agent-id': string;
            'dynamic-variables'?: string;
            'variant'?: string;
          },
          HTMLElement
        >;
      }
    }
  }
}
/* eslint-enable @typescript-eslint/no-namespace */

type TabId = 'plan' | 'schedule' | 'arch' | 'poc' | 'stack';

interface AgentMetadata {
  icon: string;
  name: string;
  tab: TabId;
}

const AGENT_META: Record<string, AgentMetadata> = {
  engineering_plan_generator: { icon: '📝', name: 'Engineering Plan Generator', tab: 'plan' },
  schedule_estimator: { icon: '📊', name: 'Schedule Estimator', tab: 'schedule' },
  solution_architect: { icon: '🏗️', name: 'Solution Architect', tab: 'arch' },
  poc_planner: { icon: '⏱️', name: 'PoC Planner', tab: 'poc' },
  tech_stack_recommender: { icon: '💻', name: 'Tech Stack Recommender', tab: 'stack' },
  plan: { icon: '📝', name: 'Engineering Plan Generator', tab: 'plan' },
  schedule: { icon: '📊', name: 'Schedule Estimator', tab: 'schedule' },
  arch: { icon: '🏗️', name: 'Solution Architect', tab: 'arch' },
  poc: { icon: '⏱️', name: 'PoC Planner', tab: 'poc' },
  stack: { icon: '💻', name: 'Tech Stack Recommender', tab: 'stack' },
};

const getAgentMeta = (agentName: string): AgentMetadata => {
  const normalized = agentName.toLowerCase().replace(/_/g, '_');
  if (AGENT_META[normalized]) {
    return AGENT_META[normalized];
  }
  for (const key of Object.keys(AGENT_META)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return AGENT_META[key];
    }
  }
  return {
    icon: '🤖',
    name: agentName.replace(/_/g, ' '),
    tab: 'plan',
  };
};

interface DirectiveCardProps {
  d: AlignmentDirective;
  setActiveTab: (tab: TabId) => void;
}

const DirectiveCard: React.FC<DirectiveCardProps> = ({ d, setActiveTab }) => {
  const [expanded, setExpanded] = useState(false);
  const meta = getAgentMeta(d.agent_name);

  return (
    <div className="p-4 rounded-lg bg-background/50 border border-border/80 flex flex-col gap-2.5 text-xs transition-all duration-200 shadow-sm hover:shadow">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-bold text-primary capitalize text-[13px]">
          <span>{meta.icon}</span>
          <span>{meta.name}</span>
        </div>
        {meta.tab && (
          <button
            onClick={() => setActiveTab(meta.tab)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 cursor-pointer font-semibold uppercase transition-colors"
            title={`View ${meta.name} details`}
          >
            View Tab
          </button>
        )}
      </div>
      
      <p className="text-foreground leading-relaxed font-bold">
        {d.directive}
      </p>

      <div className="mt-1">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 text-[11px] font-semibold text-primary hover:text-primary-hover transition-colors focus:outline-none cursor-pointer"
        >
          <span className="text-[10px] transform transition-transform duration-200 block" style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>
            ▶
          </span>
          <span>{expanded ? 'Hide reasoning & agent evidence' : 'Show reasoning & agent evidence'}</span>
        </button>

        {expanded && (
          <div className="mt-2.5 pl-3 border-l-2 border-primary/20 space-y-2 text-muted-foreground animate-fade-in">
            <p className="text-[11px] leading-relaxed">
              <strong>Reasoning:</strong> {d.reasoning}
            </p>
            {d.evidence && (
              <p className="text-[10px] italic leading-relaxed bg-muted/40 p-2 rounded border border-border/30">
                <strong>Quote:</strong> "{d.evidence}"
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export const AgentWorkspace: React.FC = () => {
  const { user, loading, login, logout, isAuthenticated } = useAuth();
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [runIdCopied, setRunIdCopied] = useState(false);
  const [isStartingPipeline, setIsStartingPipeline] = useState(false);
  const [modelFamily, setModelFamily] = useState('openai');
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [isConsentModalOpen, setIsConsentModalOpen] = useState(false);
  const [isExampleLoading, setIsExampleLoading] = useState(false);


  // Provider availability map - populated at mount from /api/providers so the
  // dropdown reflects whichever API keys are configured on this deployment.
  // Shape: { openai: {available: true}, anthropic: {available: true, reason?: string}, ... }
  // The "Coming soon" entries (llama, mistral) are always present but disabled.
  const [providers, setProviders] = useState<Record<string, { available: boolean; reason?: string | null }>>({});

  // Fetch the provider availability once on mount. We rely on the existing
  // Vite proxy (/api → :8000 in dev; same-origin in prod via FastAPI StaticFiles)
  // so no special CORS handling needed.
  useEffect(() => {
    fetch('/api/providers')
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setProviders(data))
      .catch((err) => {
        // Soft-fail: dropdown falls back to its default state (OpenAI enabled,
        // others disabled). Worst case the user sees the legacy hardcoded
        // options. Logged for debugging without breaking the page.
        console.warn('[providers] Could not load /api/providers:', err);
      });
  }, []);

  const {
    runId,
    setRunId,
    apiBaseUrl,
    setApiBaseUrl,
    logs,
    pipelineStatus,
    completedAgents,
    artifacts,
    elapsedSeconds,
    tokenUsage,
    costUsd,
    criticOutput,
    approvalResult,
    clearRun,
    fetchArtifacts,
    setPipelineStatus,
    setApprovalResult,
    errorMessage,
    longRunningWarning,
    fallbackActive,
    elevenlabsAgentId,
  } = useWorkspace();

  const [startupError, setStartupError] = useState<string | null>(null);
  const [confirmResetActive, setConfirmResetActive] = useState(false);
  const [isStepperCollapsed, setIsStepperCollapsed] = useState(false);

  // Auto-collapse the timeline stepper when pipeline lands at a post-running/decision state
  useEffect(() => {
    const autoCollapseStatuses = [
      PIPELINE_STATUS.AWAITING_HITL,
      PIPELINE_STATUS.EXPORTING,
      PIPELINE_STATUS.EXPORTED,
      PIPELINE_STATUS.REJECTED,
      PIPELINE_STATUS.ERROR,
      PIPELINE_STATUS.EXPORT_FAILED
    ];
    if (autoCollapseStatuses.includes(pipelineStatus as any)) {
      setIsStepperCollapsed(true);
    } else if (pipelineStatus !== PIPELINE_STATUS.IDLE) {
      // Auto-expand when a new execution starts
      setIsStepperCollapsed(false);
    }
  }, [pipelineStatus]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const exportResultsRef = useRef<HTMLDivElement | null>(null);
  const tabsRef = useRef<HTMLDivElement>(null);
  const hasShownToastForRunId = useRef<string | null>(null);

  // ── Issue 2 fix: Sonner toast when a provider fallback kicks in ──────────
  // The inline banner (further down in JSX) persists for the rest of the run,
  // which is good for context. But the EM might be scrolling through artifacts
  // when the swap happens - a toast adds an attention-grabbing notification
  // for the moment of the swap so they see it immediately.
  // Auto-dismisses after 6s; the banner stays as durable context.
  useEffect(() => {
    if (!fallbackActive || !runId) return;

    // Don't show if we are in the post-decision/exporting/terminal phase
    const POST_DECISION_STATES: string[] = [
      PIPELINE_STATUS.EXPORTING,
      PIPELINE_STATUS.EXPORTED,
      PIPELINE_STATUS.REJECTED,
      PIPELINE_STATUS.EXPORT_FAILED,
    ];
    if (POST_DECISION_STATES.includes(pipelineStatus)) return;

    // Don't show if already shown for this runId
    if (hasShownToastForRunId.current === runId) return;

    const fromName = fallbackActive.from.charAt(0).toUpperCase() + fallbackActive.from.slice(1);
    const toName = fallbackActive.to.charAt(0).toUpperCase() + fallbackActive.to.slice(1);
    toast.warning(
      `${fromName} quota exceeded - using ${toName} for this run.`,
      {
        duration: 6000,
        description: 'Cost is computed against the active provider. See the banner above for full details.',
      }
    );

    hasShownToastForRunId.current = runId;
  }, [fallbackActive, runId, pipelineStatus]);

  // Scroll to Export Results banner once export completes or run is rejected
  useEffect(() => {
    if (
      pipelineStatus === PIPELINE_STATUS.EXPORTED ||
      pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED ||
      pipelineStatus === PIPELINE_STATUS.REJECTED
    ) {
      const timer = setTimeout(() => {
        exportResultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [pipelineStatus]);

  // Auto-reset confirmation state after 4 seconds of inactivity
  useEffect(() => {
    if (!confirmResetActive) return;
    const timer = setTimeout(() => {
      setConfirmResetActive(false);
    }, 4000);
    return () => clearTimeout(timer);
  }, [confirmResetActive]);

  // Shared reset - clears run state and returns the UI to the empty landing.
  // Used by the sidebar Clear Plan & Reset button, the error-banner "Clear &
  // Try Again" button, and the mid-run "Cancel Run" button. When there's an
  // active run, we fire POST /cancel/{run_id} first so the backend can observe
  // the cooperative cancel flag between pipeline nodes and unwind. The UI
  // reset happens either way - 404 (gone) or 409 (already terminal) from the
  // endpoint is expected and not user-facing, so X-Skip-Toast keeps the
  // reset flow visually silent regardless of the response.
  const handleReset = () => {
    const currentRunId = runId;
    if (currentRunId) {
      apiFetch(`${apiBaseUrl}/cancel/${currentRunId}`, {
        method: 'POST',
        headers: { 'X-Skip-Toast': 'true' },
      }).catch(() => { /* Best-effort; UI reset proceeds either way. */ });
    }
    setSelectedFile(null);
    clearRun();
    setRunId(null);
    setStartupError(null);
  };

  const handleDecisionSubmitted = (data: ApprovalResponse) => {
    setPipelineStatus(data.pipeline_status as PipelineStatus);
    setApprovalResult({
      decision: data.decision,
      sheet_url: data.sheet_url || undefined,
      jira_url: data.jira_url || undefined,
      rejection_count: data.rejection_count,
    });
    fetchArtifacts();
  };

  const [activeTab, setActiveTab] = useState<'plan' | 'schedule' | 'arch' | 'poc' | 'stack'>('plan');

  const navigateToTab = (tab: 'plan' | 'schedule' | 'arch' | 'poc' | 'stack') => {
    setActiveTab(tab);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        tabsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  };



  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setStartupError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setStartupError(null);
    }
  };

  const triggerPipeline = async (bypassConsentCheck = false) => {
    if (!selectedFile) return;

    if (!bypassConsentCheck && sessionStorage.getItem("em_copilot_consent_accepted") !== "true") {
      setIsConsentModalOpen(true);
      return;
    }

    setIsStartingPipeline(true);
    setStartupError(null);
    const form = new FormData();
    form.append("file", selectedFile);
    form.append("model_family", modelFamily);
    form.append("consent_accepted", "true");
    try {
      const data = await apiFetch<{ run_id: string }>(`${apiBaseUrl}/run-pipeline`, {
        method: "POST",
        body: form,
        headers: {
          'X-Skip-Toast': 'true'
        }
      });
      setRunId(data.run_id);
    } catch (e: unknown) {
      console.error("Failed to start pipeline:", e);
      if (e instanceof Error) {
        setStartupError(e.message);
      } else {
        setStartupError("An unexpected error occurred while starting the pipeline.");
      }
    } finally {
      setIsStartingPipeline(false);
    }
  };

  const loadExampleBRD = async () => {
    setIsExampleLoading(true);
    setStartupError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/example-brd`);
      if (!response.ok) {
        throw new Error(`Failed to load example BRD: ${response.statusText}`);
      }
      const data = await response.json();
      const file = new File([data.content], data.filename, { type: 'text/plain' });
      setSelectedFile(file);
    } catch (e: unknown) {
      console.error("Failed to load example BRD:", e);
      if (e instanceof Error) {
        setStartupError(e.message);
      } else {
        setStartupError("Failed to load example BRD template.");
      }
    } finally {
      setIsExampleLoading(false);
    }
  };

  const handleDownloadPDF = () => {
    if (!runId) return;
    window.location.href = `${apiBaseUrl}/download/${runId}`;
  };

  return (
    <div className="flex flex-col md:flex-row min-h-[100dvh] md:h-[100dvh] bg-background text-foreground md:overflow-hidden font-sans">
      {/* Left Sidebar Control Panel */}
      <aside className="w-full md:w-80 bg-card border-b md:border-b-0 md:border-r border-border flex flex-col justify-between overflow-hidden shadow-xl shrink-0 order-2 md:order-1">
        <div className="p-6 space-y-6 flex-1 overflow-y-auto">
          {/* User Sign-In/Sign-Out Container */}
          {loading ? (
            <div className="bg-background p-4 rounded-lg border border-border text-center text-xs text-muted-foreground">
              Loading session...
            </div>
          ) : isAuthenticated ? (
            <div className="bg-background p-4 rounded-lg border border-border shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground font-medium">Signed in:</span>
                <button
                  onClick={logout}
                  className="text-xs text-primary hover:text-primary hover:underline flex items-center gap-1 font-semibold"
                >
                  Sign out <LogOut size={12} />
                </button>
              </div>
              <div className="text-sm font-semibold text-foreground truncate">{user?.name || user?.email}</div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-background p-4 rounded-lg border border-border shadow-sm space-y-3 text-center">
                <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Authentication</div>
                <p className="text-xs text-muted-foreground">Please <strong className="text-foreground font-semibold">sign in with Google</strong> to launch your live demo of EM Copilot. Signing in keeps your workspace private, and helps us maintain EM Copilot as a free, high-quality experience for everyone. Your email is only used to identify your sessions.</p>
                <button
                  onClick={login}
                  className="w-full py-2 bg-primary hover:bg-primary/90 text-white rounded font-bold text-xs transition duration-155"
                >
                  Sign in with Google
                </button>
              </div>

              {/* Added checklist list to balance visual weight on the landing page */}
              <div className="bg-secondary/40 border border-border/50 rounded-lg p-4 space-y-3">
                <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-foreground">What you can do:</h4>
                <ul className="text-xs text-muted-foreground space-y-2">
                  <li className="flex items-start gap-2">
                    <span className="text-success font-bold shrink-0">✓</span>
                    <span><strong>Upload complex BRDs</strong> (PDF, DOCX, or TXT)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-success font-bold shrink-0">✓</span>
                    <span>Observe Agentic Pipeline run and <strong>Review Engineering Plan Artifacts</strong> with confidence score</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-success font-bold shrink-0">✓</span>
                    <span><strong>Download or Sync approved Engineering Plan</strong> directly into Jira Epic</span>
                  </li>
                </ul>
              </div>
            </div>
          )}

          {/* Model Selection Section */}
          {isAuthenticated && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Model Selection</h3>
              <div className="relative">
                <select
                  id="model-family-select"
                  value={modelFamily}
                  onChange={(e) => setModelFamily(e.target.value)}
                  disabled={!!runId || isStartingPipeline}
                  className="w-full bg-background border border-primary/30 text-primary font-semibold rounded px-3 py-2 text-xs focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/30 cursor-pointer appearance-none disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {/* Family options - dynamic from /api/providers.
                      `disabled` reflects real backend availability (missing API key,
                      "coming soon" for unimplemented providers). Hover-title surfaces
                      the reason so the user knows WHY an option is greyed out. */}
                  {[
                    { key: 'openai', label: 'OpenAI (Default: GPT-4o)' },
                    { key: 'anthropic', label: 'Anthropic (Default: Claude 4.5 Sonnet)' },
                    { key: 'llama', label: 'Llama' },
                    { key: 'mistral', label: 'Mistral' },
                  ].map(({ key, label }) => {
                    // Default to "available" if we haven't received the providers
                    // payload yet - keeps the dropdown usable on first paint.
                    const p = providers[key];
                    const isAvailable = p?.available ?? (key === 'openai' || key === 'anthropic');
                    const reason = p?.reason;
                    return (
                      <option
                        key={key}
                        value={key}
                        disabled={!isAvailable}
                        title={reason || undefined}
                      >
                        {label}{!isAvailable && reason ? ` - ${reason}` : ''}
                      </option>
                    );
                  })}
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground">
                  <ChevronDown size={14} />
                </div>
              </div>
            </div>
          )}

          {/* Upload BRD Section */}
          {isAuthenticated && (
            <div className="space-y-3">
              <div className="flex items-center justify-center">
                <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider text-center">Upload BRD</h3>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileChange}
                // Clear value on every click so re-selecting the same file after
                // clearing it (or after the picker is cancelled) reliably fires
                // the change event. Without this, <input type="file"> silently
                // no-ops when the browser thinks the value hasn't changed.
                onClick={(e) => {
                  e.stopPropagation(); // Avoid event bubbling loop to dropzone
                  (e.target as HTMLInputElement).value = '';
                }}
                accept=".pdf,.docx,.txt"
                className="hidden"
              />
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                className="border-2 border-dashed border-border rounded-lg p-6 bg-background hover:bg-card/60 hover:border-primary/50 transition cursor-pointer text-center relative"
              >
                <Upload className="mx-auto text-primary mb-2" size={24} />
                <p className="text-xs font-semibold text-primary">Drag and drop file here</p>
                <p className="text-[10px] text-muted-foreground mt-1">Limit 5MB per file • PDF, DOCX, TXT</p>
                <div className="flex flex-col gap-2 mt-3 items-center justify-center">
                  <button 
                    type="button"
                    className="w-full px-3 py-1.5 bg-primary/10 text-primary border border-primary/30 rounded hover:bg-primary/20 hover:border-primary/50 text-xs font-semibold transition-colors"
                  >
                    Browse files
                  </button>
                  <button 
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      loadExampleBRD();
                    }}
                    disabled={isExampleLoading}
                    className="w-full px-3 py-1.5 bg-muted/20 text-muted-foreground border border-border rounded hover:bg-muted/45 hover:text-foreground text-[10px] font-semibold transition-all disabled:opacity-50"
                  >
                    {isExampleLoading ? "Loading Example..." : "⚡ Try with example BRD"}
                  </button>
                </div>
              </div>

              {selectedFile && (
                <div className="flex items-center justify-between p-2 bg-background rounded border border-border text-xs">
                  <span className="truncate max-w-[180px] font-medium text-foreground">{selectedFile.name}</span>
                  <span className="text-muted-foreground text-[10px] ml-2">{(selectedFile.size / 1024).toFixed(1)}KB</span>
                  <button
                    onClick={() => setSelectedFile(null)}
                    className="text-muted-foreground hover:text-danger ml-2"
                    aria-label="Remove selected file"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Trigger Button + runtime expectation hint */}
          {isAuthenticated && (
            <div>
              <div 
                className="relative group/btn w-full"
                title={!selectedFile ? "Please upload a BRD file to enable generation." : ""}
              >
                <button
                  onClick={() => triggerPipeline()}
                  disabled={!selectedFile || !!runId || isStartingPipeline}
                  className={`w-full py-2.5 rounded-lg font-bold text-sm transition-all duration-150 flex items-center justify-center gap-2 transform ${runId || isStartingPipeline
                    ? 'bg-secondary/40 text-muted-foreground/60 border border-border/50 cursor-not-allowed shadow-none'
                    : selectedFile
                      ? 'bg-[#4f46e5] hover:bg-[#4338ca] text-white shadow-[0_4px_14px_rgba(79,70,229,0.25)] hover:shadow-[0_4px_20px_rgba(79,70,229,0.4)] cursor-pointer hover:-translate-y-0.5 active:translate-y-0'
                      : 'bg-secondary/40 text-muted-foreground/60 border border-border/50 cursor-not-allowed shadow-none'
                    }`}
                >
                  {isStartingPipeline ? (
                    <>
                      <Loader2 className="animate-spin text-primary" size={16} />
                      <span>Starting Pipeline...</span>
                    </>
                  ) : (
                    <span>Generate Engineering Plan</span>
                  )}
                </button>

                {!selectedFile && !runId && !isStartingPipeline && (
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-popover border border-border text-popover-foreground text-[11px] rounded-md shadow-md pointer-events-none opacity-0 group-hover/btn:opacity-100 transition-opacity duration-150 z-20 text-center font-medium w-[220px]">
                    Please upload or drag a BRD file first
                    <span className="absolute top-full left-1/2 -translate-x-1/2 w-2 h-2 -mt-1 rotate-45 bg-popover border-r border-b border-border" />
                  </div>
                )}
              </div>
              {/* Runtime expectation - sits with the action surface so the user
                  knows what to expect at the moment they're about to commit. */}
              {!runId && (
                <div className="mt-3 flex items-start gap-2 text-[11px] text-muted-foreground">
                  <span className="inline-flex h-1.5 w-1.5 rounded-full bg-primary animate-pulse shrink-0 mt-1" />
                  <span>Anticipate <strong className="text-foreground">60s &ndash; 120s</strong> total run time per BRD. Runtime varies based on the size and complexity of the BRD.</span>
                </div>
              )}

              {/* Cancel Run - primary access, right where users look for run
                  controls. Only appears during active states (excludes idle,
                  awaiting_hitl, terminal). The subtle header link in the
                  timeline stepper is a secondary access path. */}
              {runId && CANCELLABLE_STATES.includes(pipelineStatus) && (
                <button
                  onClick={handleReset}
                  className="mt-2 w-full py-2 border border-danger bg-danger/10 hover:bg-danger/25 rounded text-xs font-bold text-danger transition flex items-center justify-center gap-2"
                  title="Reset the UI. The pipeline task will finish in the background."
                >
                  <X size={14} />
                  Cancel Run
                </button>
              )}
            </div>
          )}

          {runId && (
            <div className="border-t border-border pt-4 space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Current Run</h4>
              <div className="flex items-center gap-1.5">
                <div className="flex-1 bg-background p-2 rounded font-sans text-[10px] text-foreground border border-border truncate" title={runId}>
                  Run #{runId.slice(0, 5)}: {selectedFile ? selectedFile.name : 'BRD Pipeline'}
                </div>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(runId);
                    setRunIdCopied(true);
                    setTimeout(() => setRunIdCopied(false), 2000);
                  }}
                  className="p-1.5 bg-background border border-border rounded hover:bg-secondary hover:text-white transition text-muted-foreground shrink-0"
                  title="Copy Run ID"
                >
                  {runIdCopied ? (
                    <Check size={12} className="text-success animate-scale-in" />
                  ) : (
                    <Copy size={12} />
                  )}
                </button>
              </div>
              <div className="text-xs text-muted-foreground">
                Status: <span className="font-semibold text-success capitalize">{pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ? 'awaiting decision' : pipelineStatus === PIPELINE_STATUS.EVALUATING ? 'Evaluating' : (pipelineStatus ? pipelineStatus.replace(/_/g, ' ') : "Starting...")}</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (pipelineStatus === PIPELINE_STATUS.AWAITING_HITL) {
                    if (!confirmResetActive) {
                      setConfirmResetActive(true);
                      return;
                    }
                  }
                  handleReset();
                  setConfirmResetActive(false);
                }}
                disabled={CANCELLABLE_STATES.includes(pipelineStatus) || pipelineStatus === PIPELINE_STATUS.EXPORTED || pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED || pipelineStatus === PIPELINE_STATUS.REJECTED}
                className={`w-full py-1.5 rounded text-xs font-semibold transition ${
                  (CANCELLABLE_STATES.includes(pipelineStatus) || pipelineStatus === PIPELINE_STATUS.EXPORTED || pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED || pipelineStatus === PIPELINE_STATUS.REJECTED)
                    ? 'bg-secondary/40 text-muted-foreground/60 border border-border/50 cursor-not-allowed shadow-none'
                    : confirmResetActive
                      ? 'border border-danger bg-danger text-white animate-pulse'
                      : 'border border-destructive bg-destructive/10 hover:bg-destructive/40 text-destructive hover:text-destructive shadow-[0_0_10px_rgba(244,63,94,0.05)]'
                }`}
              >
                {confirmResetActive ? "Confirm Reset? (Click again)" : "Clear Plan & Reset"}
              </button>
            </div>
          )}
        </div>

        {/* Collapsible Advanced Settings Accordion (Only visible on localhost for developers) */}
        {typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && (
          <div className="border-t border-border bg-card/40">
            <button
              onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
              className="w-full px-6 py-4 flex items-center justify-between text-xs font-bold text-muted-foreground hover:bg-card/40 transition uppercase tracking-wider"
            >
              <span>⚙️ Advanced settings</span>
              {isAdvancedOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {isAdvancedOpen && (
              <div className="px-6 pb-6 pt-2 space-y-3">
                <div>
                  <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">API Base URL</label>
                  <input
                    type="text"
                    value={apiBaseUrl}
                    onChange={(e) => setApiBaseUrl(e.target.value)}
                    className="w-full bg-background border border-border rounded px-2.5 py-1.5 text-xs focus:ring-1 focus:ring-primary focus:border-primary outline-none text-foreground font-mono"
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </aside>

      {/* Main Workstation Panel */}
      <main className="flex-1 flex flex-col md:overflow-hidden bg-background order-1 md:order-2">
        {/* Main Header - uses min-h instead of fixed h so the title can wrap
            cleanly at narrow viewports (e.g. devtools open) without overflowing
            into the IngestionLanding hero below. items-start keeps the controls
            (Theme picker, API status) pinned to the top-right of the title block. */}
        <header className="min-h-12 border-b border-border px-6 py-2.5 gap-4 flex flex-col sm:flex-row sm:items-center justify-between bg-card shrink-0 shadow-sm relative">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight leading-tight">
              <span className="text-primary">EM Copilot</span>
              <span className="text-foreground">: BRD → Engineering Plan</span>
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">Multi-Agent AI Software Engineering Planning System</p>
          </div>
          {elevenlabsAgentId && runId && pipelineStatus === PIPELINE_STATUS.AWAITING_HITL && (
            <elevenlabs-convai
              agent-id={elevenlabsAgentId}
              variant="compact"
              dynamic-variables={JSON.stringify({
                run_id: runId,
                api_base_url: apiBaseUrl,
                artifact_brief: generateVoiceBrief(artifacts, criticOutput, runId),
                voice_brief: generateVoiceBrief(artifacts, criticOutput, runId),
              })}
            />
          )}
          <div className="flex items-center gap-3 self-end sm:self-auto shrink-0">
            <a
              href="#/about"
              className="text-xs font-bold text-muted-foreground hover:text-primary transition flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-secondary/40 rounded-lg"
            >
              ℹ️ About
            </a>
            <button
              onClick={() => setIsFeedbackOpen(true)}
              className="text-xs font-bold text-muted-foreground hover:text-primary transition flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-secondary/40 rounded-lg"
            >
              📝 Feedback
            </button>
            <ThemePicker />
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${Object.keys(providers).length > 0 ? 'bg-success animate-pulse' : 'bg-muted-foreground'}`} />
              <span className="text-xs font-semibold text-muted-foreground">
                {Object.keys(providers).length > 0 ? "API connected" : "API Offline"}
              </span>
            </div>
          </div>
        </header>
        {/* Scrollable Workstation Body */}
        <div className="flex-1 overflow-y-auto p-4 pb-4 space-y-4">
          {!runId ? (
            <div className="space-y-6">
              {startupError && (
                <div className="max-w-3xl bg-danger/10 border border-danger/30 p-5 rounded-xl flex gap-3 animate-fade-in shadow-[0_0_15px_rgba(239,68,68,0.05)]">
                  <span className="text-xl shrink-0">📋</span>
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-danger uppercase tracking-wider">BRD Quality Gate Validation Failure</h4>
                    <p className="text-xs text-foreground/95 font-semibold leading-relaxed whitespace-pre-wrap">
                      {startupError.replace(/^API Failure:\s*/i, '')}
                    </p>
                  </div>
                </div>
              )}
              <IngestionLanding
                selectedFile={selectedFile}
                onFileSelect={setSelectedFile}
                onRemoveFile={() => setSelectedFile(null)}
                onTrigger={triggerPipeline}
                isLoading={pipelineStatus === PIPELINE_STATUS.INITIALIZING}
                isAuthenticated={isAuthenticated}
                onLogin={login}
              />
            </div>
          ) : (
            <>
              {/* Fallback Active Alert Banner */}
              {fallbackActive && (
                <div className="bg-warning/20 border-l-4 border-warning py-2 px-4 rounded-lg shadow-sm text-[11px] text-warning flex items-center justify-between animate-fade-in">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm select-none">⚠️</span>
                    <div>
                      <h4 className="font-bold text-warning text-xs">Automatic LLM Provider Fallback Triggered</h4>
                      <p className="text-warning/80 mt-0.5 text-[11px] leading-snug">
                        The primary <strong>{fallbackActive.from.toUpperCase()}</strong> provider limits were reached or key expired. Switched to <strong>{fallbackActive.to.toUpperCase()}</strong> successfully to complete execution.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {longRunningWarning && (
                <div className="bg-warning/20 border-l-4 border-warning py-3 px-4 rounded-lg shadow-sm flex items-center justify-between animate-pulse">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm select-none">⏳</span>
                    <div>
                      <h4 className="font-bold text-warning text-xs">Processing Update</h4>
                      <p className="text-warning/80 mt-0.5 text-[11px] leading-snug">
                        {longRunningWarning}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Loop Warnings / Non-terminal Flagged Concerns Banner */}
              {pipelineStatus !== PIPELINE_STATUS.ERROR && artifacts?.warnings && artifacts.warnings.length > 0 && (
                <div className="bg-warning/20 border border-warning/45 p-5 rounded-xl shadow-lg flex flex-col gap-3 animate-fade-in">
                  <div className="flex items-start justify-between gap-4">
                    <h4 className="text-sm font-bold text-warning flex items-center gap-2">
                      <span>⚠️</span> Design Loop Warning / Flagged Concern
                    </h4>
                  </div>
                  {artifacts.warnings.map((warn, i) => (
                    <p key={i} className="text-xs text-warning leading-relaxed font-semibold">
                      {warn}
                    </p>
                  ))}
                </div>
              )}

              {/* Pipeline Error Alert Banner */}
              {pipelineStatus === PIPELINE_STATUS.ERROR && (
                <div className="bg-danger/30 border border-danger/50 p-5 rounded-xl shadow-lg flex flex-col gap-3 animate-fade-in">
                  <div className="flex items-start justify-between gap-4">
                    <h4 className="text-sm font-bold text-danger flex items-center gap-2">
                      <span>❌</span> Agentic Workflow Execution Failed
                    </h4>
                    <button
                      onClick={handleReset}
                      className="shrink-0 px-3 py-1.5 bg-danger/20 hover:bg-danger/40 border border-danger/50 text-danger text-xs font-bold rounded transition"
                    >
                      Clear & Try Again
                    </button>
                  </div>
                  <p className="text-xs text-danger/90 leading-relaxed font-semibold">
                    {errorMessage || "An unexpected error occurred during execution. Please check the logs."}
                  </p>
                </div>
              )}

              {/* HITL Awaiting Alert Banner */}
              {pipelineStatus === PIPELINE_STATUS.AWAITING_HITL && !approvalResult && (
                <div className="bg-warning/20 border-l-4 border-warning py-2 px-4 rounded-lg shadow-sm flex items-center justify-between animate-fade-in">
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm select-none">⏸️</span>
                    <div>
                      <h4 className="text-xs font-bold text-warning leading-snug">Action Required: Review the Artifacts. Approval needed to push plan into Jira.</h4>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      const element = document.getElementById('decision-gate');
                      if (element) {
                        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                      }
                    }}
                    className="px-3 py-1 bg-[#4f46e5] hover:bg-[#4338ca] text-white font-bold text-[11px] rounded transition shadow hover:shadow-md shrink-0 cursor-pointer"
                  >
                    Scroll to Decision Gate
                  </button>
                </div>
              )}

              {/* Stepper Timeline Progress Nodes */}
              <TimelineStepper
                pipelineStatus={pipelineStatus}
                completedAgents={completedAgents}
                artifacts={artifacts}
                criticOutput={criticOutput}
                logs={logs}
                isCollapsed={isStepperCollapsed}
                onToggleCollapse={() => setIsStepperCollapsed(!isStepperCollapsed)}
              />


              {/* Performance Metrics Summary Header Row */}
              <div className="flex flex-wrap justify-between items-center gap-4 text-xs text-muted-foreground bg-card p-3 rounded-xl border border-border shadow-sm">
                <div className="flex items-center gap-1.5">
                  <strong>Evaluation Score:</strong> 
                  <code className={`inline-flex items-center justify-center text-center min-w-[70px] bg-background border border-border px-2.5 py-1 rounded font-mono ${criticOutput ? 'text-[#047857] dark:text-[#34d399] font-bold' : 'text-muted-foreground'}`}>
                    {criticOutput ? `${criticOutput.overallScore.toFixed(2)}/5.0` : '-/5.0'}
                  </code>
                  {criticOutput && (
                    <span 
                      className="cursor-help text-muted-foreground hover:text-primary transition-colors text-[13px] ml-0.5"
                      title="Calculation Formula:\n(Groundedness + Completeness + Consistency + Actionability) / 4"
                    >
                      ⓘ
                    </span>
                  )}
                </div>
                <div>
                  <strong>Total Processing Time:</strong> <code className={`inline-flex items-center justify-center text-center min-w-[50px] bg-background border border-border px-2.5 py-1 rounded font-mono ${elapsedSeconds ? 'text-[#047857] dark:text-[#34d399] font-bold' : 'text-muted-foreground'}`}>{elapsedSeconds ? `${elapsedSeconds}s` : '-'}</code>
                </div>
                <div>
                  <strong>Tokens used:</strong> <code className={`inline-flex items-center justify-center text-center bg-background border border-border px-2.5 py-1 rounded font-mono ${tokenUsage ? 'text-[#047857] dark:text-[#34d399] font-bold' : 'text-muted-foreground'}`}>{tokenUsage ? `${tokenUsage.input.toLocaleString()} in / ${tokenUsage.output.toLocaleString()} out` : '-'}</code>
                </div>
                <div>
                  <strong>Cost Spent:</strong> <code className={`inline-flex items-center justify-center text-center min-w-[75px] bg-background border border-border px-2.5 py-1 rounded font-mono ${costUsd != null ? 'text-[#047857] dark:text-[#34d399] font-bold' : 'text-muted-foreground'}`}>{costUsd != null ? `$${costUsd.toFixed(4)}` : '-'}</code>
                </div>
              </div>

              {/* Critic Scoring Cards Box */}
              {criticOutput && (
                <ErrorBoundary fallback={
                  <div className="p-6 bg-danger/20 border border-danger/40 rounded-xl space-y-3">
                    <div className="flex items-center gap-2 text-danger font-bold text-sm uppercase tracking-wider">
                      <ShieldAlert size={16} />
                      <span>Critic Component Failure</span>
                    </div>
                    <p className="text-xs text-danger/80 leading-relaxed">
                      An error occurred while rendering the Critic scorecards.
                    </p>
                  </div>
                }>
                  <div className="space-y-4 border border-border rounded-xl p-5 bg-card shadow-md">
                    <div className="flex items-center justify-between border-b border-border/60 pb-3">
                      <div className="space-y-0.5">
                        <h3 className="text-xs font-extrabold text-primary uppercase tracking-wider">Independent Critic Score</h3>
                        <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-1">
                          <span>Final Score:</span>
                          <strong className={criticOutput.badge === 'green' ? 'text-success font-extrabold' : criticOutput.badge === 'amber' ? 'text-warning font-extrabold' : 'text-danger font-extrabold'}>
                            {criticOutput.overallScore.toFixed(2)}/5.0
                          </strong>
                          <span className="text-[11px] text-muted-foreground/80">
                            (Target: &ge;4.00 for Green)
                          </span>
                          <span className="text-muted-foreground/40 px-1">•</span>
                          <span>Revision(s):</span>
                          <strong className="text-foreground font-bold">{criticOutput.revisionNumber}</strong>
                        </div>
                        {/* Transparent Mathematical Formula Breakdown String */}
                        <span className="text-[10px] text-muted-foreground/80 block font-mono mt-1 bg-background px-2 py-0.5 rounded border border-border/40 w-fit">
                          Formula: ({criticOutput.dimensions.groundedness?.score.toFixed(2)} + {criticOutput.dimensions.completeness?.score.toFixed(2)} + {criticOutput.dimensions.consistency?.score.toFixed(2)} + {criticOutput.dimensions.actionability?.score.toFixed(2)}) ÷ 4 = {criticOutput.overallScore.toFixed(2)}
                        </span>
                      </div>
                      <span
                        title="Green badge requires an overall score of ≥4.00 and all sub-metrics to pass."
                        className={`px-3 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wider cursor-help transition ${
                          criticOutput.badge === 'green'
                            ? 'bg-success/20 text-success border border-success/40'
                            : criticOutput.badge === 'amber'
                            ? 'bg-warning/50 text-warning border border-warning/50'
                            : 'bg-danger/50 text-danger border border-danger/50'
                        }`}
                      >
                        {criticOutput.badge === 'green' ? '🟢 GREEN' : criticOutput.badge === 'amber' ? '🟡 AMBER' : '🔴 RED'}
                      </span>
                    </div>

                    {/* Quality Cap Alert Module */}
                    {criticOutput.capReasons && criticOutput.capReasons.length > 0 && (
                      <div className="space-y-2 pb-1 animate-fade-in">
                        {criticOutput.capReasons.map((reason, index) => (
                          <div key={index} className="flex items-center justify-between text-xs px-3 py-2 rounded-lg border border-warning/30 bg-warning/5 text-warning font-medium leading-relaxed">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-extrabold uppercase tracking-wider text-[9px] px-1.5 py-0.5 rounded bg-warning/20 border border-warning/30">
                                {reason.mechanism}
                              </span>
                              <span><strong>{reason.verb} by Quality Safeguard:</strong> {reason.detail}</span>
                            </div>
                            <span className="font-mono text-[10px] font-bold whitespace-nowrap ml-4">
                              {reason.before.toFixed(2)} &rarr; {reason.after.toFixed(2)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Metrics Row */}
                    <div className="flex flex-wrap md:flex-nowrap gap-4 items-center justify-between text-xs text-muted-foreground pt-1">
                      {(['groundedness', 'completeness', 'consistency', 'actionability'] as const).map((metric) => {
                        const data = criticOutput.dimensions[metric];
                        if (!data) return null;
                        return (
                          <div key={metric} className="flex items-center gap-1.5 bg-background/40 px-2 py-1 rounded-md border border-border/50 flex-1 justify-center">
                            <strong className="capitalize text-foreground">{metric}:</strong>
                            <code className={`font-mono font-bold text-[11px] ${data.passed ? 'text-success' : 'text-danger'}`}>
                              {data.score.toFixed(2)}
                            </code>
                            <span className={`text-[11px] font-bold ${data.passed ? 'text-success' : 'text-danger'}`}>
                              {data.passed ? '✓' : '✗'}
                            </span>
                            <span className="text-[10px] text-muted-foreground">
                              ({data.threshold === 5 ? '=' : '≥'}{data.threshold})
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </ErrorBoundary>
              )}

              {/* EM Alignment Directives Container Block */}
              {artifacts?.alignment_memo && (
                <div className="flex flex-col items-stretch gap-4 bg-card p-5 rounded-xl border border-border my-2 shadow-md">
                  
                  {/* Clean Title Component Header */}
                  <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
                    <h4 className="text-xs font-extrabold text-primary uppercase tracking-wider flex items-center gap-1.5">
                      <img
                        src="/favicon.svg"
                        alt="EM Copilot"
                        className="h-3.5 w-3.5 object-contain select-none shrink-0"
                      />
                      Alignment Recommendations
                    </h4>
                    {artifacts.alignment_memo.directives && artifacts.alignment_memo.directives.length > 0 && (
                      <span className="bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded text-[10px] font-mono font-bold">
                        {artifacts.alignment_memo.directives.length} Directives Issued
                      </span>
                    )}
                  </div>

                  {/* Directives Output Content Grid */}
                  {artifacts.alignment_memo.directives && artifacts.alignment_memo.directives.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {artifacts.alignment_memo.directives.map((d: AlignmentDirective, idx: number) => (
                        <DirectiveCard key={idx} d={d} setActiveTab={navigateToTab} />
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 p-4 rounded-lg bg-success/10 border border-success/30 text-success text-xs font-semibold">
                      <span>🟢</span> All Pass 1 drafts aligned — no arbitration needed.
                    </div>
                  )}
                </div>
              )}

              {/* Tabbed Viewport for Artifacts */}
              {artifacts && (
                <div className="bg-card border border-border rounded-xl p-5 shadow-md space-y-4">
                  
                  {/* Clean, Bounded Module Action Header Row */}
                  <div className="flex items-center justify-between border-b border-border/60 pb-3">
                    <div className="space-y-0.5">
                      <h3 className="text-xs font-extrabold text-primary uppercase tracking-wider">Generated Artifacts</h3>
                      <p className="text-[11px] text-muted-foreground">Review individual multi-agent operational planning deliverables</p>
                    </div>
                    <button
                      onClick={handleDownloadPDF}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-background hover:bg-secondary/40 text-foreground border border-border rounded-lg text-xs font-bold transition shadow-sm cursor-pointer"
                    >
                      <Download size={14} /> Download PDF
                    </button>
                  </div>

                  {/* Integrated Navigation Tabs Ribbon Container */}
                  <div ref={tabsRef} className="flex bg-background p-1 rounded-xl border border-border/80 w-full overflow-x-auto scrollbar-none whitespace-nowrap">
                    {(['plan', 'schedule', 'arch', 'poc', 'stack'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2 rounded-lg text-xs font-bold capitalize transition-all min-w-[110px] text-center flex-1 cursor-pointer ${
                          activeTab === tab
                            ? 'bg-card text-primary shadow-sm border border-border font-extrabold'
                            : 'text-muted-foreground hover:text-foreground border border-transparent'
                        }`}
                      >
                        {tab === 'arch' ? 'Architecture' : tab === 'stack' ? 'Tech Stack' : tab}
                      </button>
                    ))}
                  </div>

                  {/* Tab Active Content Window Canvas */}
                  <div className="bg-background/30 rounded-xl border border-border/60 p-5 min-h-[250px]">
                    <ErrorBoundary fallback={<div className="p-4 bg-danger/20 border border-danger/40 text-danger rounded-lg text-sm">Failed to render artifact.</div>}>
                      {([
                        PIPELINE_STATUS.DRAFTING,
                        PIPELINE_STATUS.ALIGNING,
                        PIPELINE_STATUS.REVISING,
                      ] as PipelineStatus[]).includes(pipelineStatus) ? (
                        <PlanSkeleton />
                      ) : (
                        <div>
                          {activeTab === 'plan' && <PlanTab planData={artifacts.plan_output} />}
                          {activeTab === 'schedule' && <ScheduleTab scheduleData={artifacts.schedule_output} />}
                          {activeTab === 'arch' && <ArchitectureTab architectureData={artifacts.arch_output} />}
                          {activeTab === 'poc' && <PoCTab pocData={artifacts.poc_output} />}
                          {activeTab === 'stack' && <TechStackTab techStackData={artifacts.stack_output} />}
                        </div>
                      )}
                    </ErrorBoundary>
                  </div>
                </div>
              )}

              {/* ========================================== */}
              {/* MASTER WORKFLOW GATE & DELIVERY PIPELINE */}
              {/* ========================================== */}
              {(([
                PIPELINE_STATUS.AWAITING_HITL, 
                PIPELINE_STATUS.EXPORTING, 
                PIPELINE_STATUS.EXPORTED, 
                PIPELINE_STATUS.EXPORT_FAILED, 
                PIPELINE_STATUS.REJECTED
              ] as string[]).includes(pipelineStatus)) && (
                <div ref={exportResultsRef} className="border-t border-border pt-5 mt-4">
                  <div className="max-w-4xl mx-auto p-5 bg-card border border-border rounded-xl shadow-lg transition-all duration-300">
                    
                   {/* 1. DYNAMIC SYSTEM ACTION STATE HEADER */}
                    {pipelineStatus !== PIPELINE_STATUS.AWAITING_HITL && (
                      <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
                        <h3 className="text-xs font-extrabold text-foreground uppercase tracking-wider flex items-center gap-2">
                          {pipelineStatus === PIPELINE_STATUS.EXPORTING && <Loader2 className="animate-spin text-primary" size={14} />}
                          {pipelineStatus === PIPELINE_STATUS.EXPORTED && <span className="text-success text-sm">✅</span>}
                          {pipelineStatus === PIPELINE_STATUS.REJECTED && <span className="text-danger text-sm">❌</span>}
                          {pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED && <span className="text-warning text-sm">⚠️</span>}
                          
                          <span>
                            {pipelineStatus === PIPELINE_STATUS.EXPORTING && "Exporting & Syncing Plan..."}
                            {!( [PIPELINE_STATUS.AWAITING_HITL, PIPELINE_STATUS.EXPORTING] as string[]).includes(pipelineStatus) && "Export Results & Audit Trace"}
                          </span>
                        </h3>
                        
                        <span className={`px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase tracking-wider border ${
                          pipelineStatus === PIPELINE_STATUS.EXPORTING ? 'bg-primary/20 border-primary/30 text-primary animate-pulse' :
                          pipelineStatus === PIPELINE_STATUS.EXPORTED ? 'bg-success/20 border-success/40 text-success' :
                          pipelineStatus === PIPELINE_STATUS.REJECTED ? 'bg-danger/20 border-danger/40 text-danger' :
                          'bg-warning/20 border-warning/40 text-warning'
                        }`}>
                          {pipelineStatus === PIPELINE_STATUS.EXPORTING && 'Syncing integrations'}
                          {pipelineStatus === PIPELINE_STATUS.EXPORTED && '✓ Export Complete'}
                          {pipelineStatus === PIPELINE_STATUS.REJECTED && 'Plan Rejected'}
                          {pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED && 'Export Failed'}
                        </span>
                      </div>
                    )}

                    {/* 2. STATE STEP A: INTERACTIVE HUMAN APPROVAL GATE */}
                    {pipelineStatus === PIPELINE_STATUS.AWAITING_HITL && (
                      <ErrorBoundary fallback={
                        <div className="p-4 bg-danger/10 border border-danger/30 rounded-lg space-y-2 text-xs text-danger">
                          <div className="flex items-center gap-2 font-bold uppercase tracking-wider">
                            <ShieldAlert size={14} />
                            <span>Decision Gate Component Failure</span>
                          </div>
                          <p className="opacity-90">An error occurred while loading the Decision Gate. Please try refreshing.</p>
                        </div>
                      }>
                        <HITLApprovalGate key={runId || undefined} runId={runId!} onDecisionSubmitted={handleDecisionSubmitted} />
                      </ErrorBoundary>
                    )}

                    {/* 3. STATE STEP B: RUNTIME SYNCING SPINNER SUB-VIEW */}
                    {pipelineStatus === PIPELINE_STATUS.EXPORTING && (
                      <div className="space-y-4 animate-pulse py-2">
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          Please wait. EM Copilot is writing the decision log to your Google Sheets dashboard, indexing plan chunks into your Pinecone vector database, and creating the Jira Epic + Task structure.
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[10px] font-bold text-muted-foreground">
                          <div className="flex items-center gap-2 p-2.5 bg-secondary/10 border border-border rounded-lg">
                            <span className="text-success">✓</span>
                            <span>Google Sheets Log</span>
                          </div>
                          <div className="flex items-center gap-2 p-2.5 bg-secondary/10 border border-border rounded-lg">
                            <Loader2 className="animate-spin text-primary shrink-0" size={11} />
                            <span>Creating Jira Epic</span>
                          </div>
                          <div className="flex items-center gap-2 p-2.5 bg-secondary/10 border border-border rounded-lg">
                            <Loader2 className="animate-spin text-primary shrink-0" size={11} />
                            <span>Pinecone Indexing</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* 4. STATE STEP C: TERMINAL AUDIT CARDS SUB-VIEW */}
                    {(([PIPELINE_STATUS.EXPORTED, PIPELINE_STATUS.EXPORT_FAILED, PIPELINE_STATUS.REJECTED] as string[]).includes(pipelineStatus)) && (
                      <div className="space-y-4 animate-fade-in">
                        {pipelineStatus === PIPELINE_STATUS.REJECTED && (
                          <p className="text-xs text-danger font-semibold bg-danger/5 border border-danger/20 p-3 rounded-lg leading-relaxed">
                            Export skipped. The engineering plan was rejected at the decision gate. Audit logs and decision notes have been preserved below.
                          </p>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-stretch">
                          {/* Google Sheets Integration Card */}
                          {approvalResult?.export_status === 'ok' && approvalResult?.sheet_url ? (
                            <div className={`p-4 rounded-lg flex flex-col justify-between gap-3 border ${
                              pipelineStatus === PIPELINE_STATUS.REJECTED ? 'bg-secondary/10 border-border' : 'bg-success/5 border-success/20'
                            }`}>
                              <div className="space-y-1.5">
                                <div className={`text-xs font-bold ${pipelineStatus === PIPELINE_STATUS.REJECTED ? 'text-muted-foreground' : 'text-success'}`}>
                                  {pipelineStatus === PIPELINE_STATUS.REJECTED ? 'Rejection recorded' : 'Approval recorded'}
                                </div>
                                <p className="text-[11px] text-muted-foreground leading-relaxed">
                                  {pipelineStatus === PIPELINE_STATUS.REJECTED
                                    ? "Wrote rejection decision, reviewer notes, and EM score to Google Sheets for audit trace."
                                    : (approvalResult?.export_detail || "Wrote Pipeline Run Summary to Google Sheets for audit purposes.")}
                                </p>
                                <div className="text-[10px] text-muted-foreground/80 bg-background/60 border border-border/40 p-2 rounded flex flex-col gap-0.5 font-mono">
                                  <span><b>Spreadsheet:</b> EM Copilot Runs Log</span>
                                  <span><b>Data Type:</b> Run metrics, EM score, notes</span>
                                </div>
                              </div>
                              <a
                                href={approvalResult.sheet_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={`flex items-center justify-center w-fit px-3 py-1.5 border rounded-lg font-bold text-[11px] transition shadow-sm ${
                                  pipelineStatus === PIPELINE_STATUS.REJECTED
                                    ? 'border-border text-muted-foreground hover:bg-secondary/30'
                                    : 'border-primary text-primary hover:bg-primary/10'
                                }`}
                              >
                                Open Google Sheet
                              </a>
                            </div>
                          ) : approvalResult?.export_status === 'local_fallback' ? (
                            <div className="p-4 bg-warning/5 border border-warning/20 rounded-lg flex flex-col justify-between gap-1.5">
                              <div>
                                <div className="text-xs font-bold text-warning">Saved to Local Backup CSV</div>
                                <p className="text-[11px] text-muted-foreground leading-relaxed mt-1">
                                  {approvalResult?.export_detail || "Google Sheets integration not configured - backup CSV generated instead."}
                                </p>
                              </div>
                            </div>
                          ) : approvalResult?.export_status === 'failed' ? (
                            <div className="p-4 bg-danger/5 border border-danger/20 rounded-lg flex flex-col justify-between gap-1.5">
                              <div>
                                <div className="text-xs font-bold text-danger">Sheets Export Failed</div>
                                <p className="text-[11px] text-danger/90 leading-relaxed font-mono mt-1">
                                  {approvalResult?.export_detail || "Failed to push sheets record trace sync."}
                                </p>
                              </div>
                            </div>
                          ) : null}

                          {/* Jira Integration Card */}
                          {pipelineStatus !== PIPELINE_STATUS.REJECTED && (
                            approvalResult?.jira_status === 'jira' && approvalResult?.jira_url ? (
                              <div className="p-4 bg-success/5 border border-success/20 rounded-lg flex flex-col justify-between gap-3">
                                <div className="space-y-1.5">
                                  <div className="text-xs font-bold text-success flex items-center gap-1.5">
                                    <span>Pushed to Jira:</span>
                                    {approvalResult.jira_issue_key && (
                                      <code className="bg-background border border-border px-1.5 py-0.5 rounded font-mono text-[10px] text-success font-extrabold">{approvalResult.jira_issue_key}</code>
                                    )}
                                  </div>
                                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                                    {approvalResult?.jira_detail || `Created Jira Epic ${approvalResult.jira_issue_key} via Atlassian MCP.`}
                                  </p>
                                  <div className="text-[10px] text-muted-foreground/80 bg-background/60 border border-border/40 p-2 rounded flex flex-col gap-0.5 font-mono">
                                    <span><b>Epic Title:</b> {selectedFile ? selectedFile.name.replace(/\.[^/.]+$/, "") : 'BRD'} Integration Plan</span>
                                    <span><b>Scope:</b> Multi-agent deliverables & milestones</span>
                                  </div>
                                </div>
                                <a
                                  href={approvalResult.jira_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center justify-center w-fit px-3 py-1.5 border border-primary text-primary hover:bg-primary/10 rounded-lg font-bold text-[11px] transition shadow-sm"
                                >
                                  Open Jira Issue
                                </a>
                              </div>
                            ) : approvalResult?.jira_status === 'skipped' ? (
                              <div className="p-4 bg-card border border-border rounded-lg flex flex-col justify-between gap-1.5">
                                <div>
                                  <div className="text-xs font-bold text-muted-foreground">Jira Push Skipped</div>
                                  <p className="text-[11px] text-muted-foreground leading-relaxed mt-1">
                                    {approvalResult?.jira_detail || "Jira creation skipped for this run."}
                                  </p>
                                </div>
                              </div>
                            ) : approvalResult?.jira_status === 'failed' ? (
                              <div className="p-4 bg-danger/5 border border-danger/20 rounded-lg flex flex-col justify-between gap-1.5">
                                <div>
                                  <div className="text-xs font-bold text-danger">Jira Integration Failed</div>
                                  <p className="text-[11px] text-danger/90 leading-relaxed font-mono mt-1">
                                    {approvalResult?.jira_detail || "Check server API log configurations."}
                                  </p>
                                </div>
                              </div>
                            ) : (
                              <div className="h-full flex flex-col justify-between">
                                <IntegrationNotConfigured
                                  title="Jira integration inactive"
                                  envVars={["JIRA_API_TOKEN", "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_PROJECT_KEY"]}
                                  description="Jira environment configurations missing. Integration disabled."
                                  docsAnchor="#L59-L65"
                                />
                              </div>
                            )
                          )}
                        </div>

                        {/* DYNAMIC FORWARD PROGRESS CALL-TO-ACTION BUTTON */}
                        <div className="border-t border-border pt-3.5 flex justify-end">
                          <button
                            onClick={handleReset}
                            className="flex items-center gap-1.5 px-4 py-2 bg-primary hover:bg-primary/90 rounded-lg text-xs font-bold text-white uppercase tracking-wider transition shadow-sm hover:shadow-primary/20 cursor-pointer"
                          >
                            <Plus size={13} />
                            Start New Plan
                          </button>
                        </div>
                      </div>
                    )}

                  </div>
                </div>
              )}


              {/* Tavily fallback hint - surfaces when the pipeline tried Tavily web grounding */}
              {(() => {
                const tavilyMissing = logs.some(
                  (l) =>
                    l.type === 'tool_call_degraded' &&
                    (((l as unknown) as Record<string, unknown>).tool === 'tavily' ||
                      ((l.payload as Record<string, unknown> | undefined)?.tool === 'tavily')) &&
                    (((l as unknown) as Record<string, unknown>).reason === 'api_key_missing' ||
                      ((l.payload as Record<string, unknown> | undefined)?.reason === 'api_key_missing')),
                );
                return tavilyMissing ? (
                  <div className="mt-4">
                    <IntegrationNotConfigured
                      title="Web grounding fallback unavailable"
                      envVars={['TAVILY_API_KEY']}
                      description="The Architect or Tech Stack agent hit a RAG miss and would have used Tavily for live web grounding, but Tavily is not configured on this deployment. The pipeline continued with RAG-only context."
                      docsAnchor="#L74-L78"
                    />
                  </div>
                ) : null;
              })()}

              {/* Critic findings - consistency issues + hallucination flags */}
              <div className="mt-4">
                <CriticFindings criticDetail={artifacts?.critic_output} />
              </div>

              {/* Live Log Console - Tightened Spacing Alignment */}
              <div className="border-t border-border pt-4 mt-5">
                <LogConsole logs={logs} />
              </div>
            </>
          )}
        </div>

        {/* Persistent footer disclaimer - sits outside the scrollable body so
            it stays visible at all times (matches Claude.ai / ChatGPT pattern).
            Moved here from the header subtitle, where it was undermining the
            product's perceived reliability by appearing alongside the title. */}
        <footer className="px-8 py-2 border-t border-border bg-card text-[10px] text-[#666] dark:text-[#a3a3a3] font-medium shrink-0 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span><b>Disclaimer</b>: AI generated plans are starting points. Professional review and validation required before implementation.</span>
          <div className="flex items-center gap-3 shrink-0">
            <a href="#/privacy" className="hover:text-primary transition font-semibold">Privacy Policy</a>
            <span>•</span>
            <a href="#/terms" className="hover:text-primary transition font-semibold">Terms of Service</a>
          </div>
        </footer>
      </main>

      <FeedbackModal
        isOpen={isFeedbackOpen}
        onClose={() => setIsFeedbackOpen(false)}
        runId={runId}
        apiBaseUrl={apiBaseUrl}
      />

      <ConsentModal
        isOpen={isConsentModalOpen}
        onClose={() => setIsConsentModalOpen(false)}
        onAccept={() => {
          setIsConsentModalOpen(false);
          sessionStorage.setItem("em_copilot_consent_accepted", "true");
          triggerPipeline(true);
        }}
      />
    </div>
  );
};
