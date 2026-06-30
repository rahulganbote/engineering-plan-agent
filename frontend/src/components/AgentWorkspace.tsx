import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useWorkspace } from '../context/WorkspaceContext';
import { useAuth } from '../context/AuthContext';
import { PlanSkeleton } from './PlanSkeleton';
import { ErrorBoundary } from './ErrorBoundary';
import { HITLApprovalGate, type ApprovalResponse } from './HITLApprovalGate';
import { apiFetch } from '../lib/apiClient';
import { IngestionLanding } from './IngestionLanding';
import { TimelineStepper } from './TimelineStepper';
import { LogConsole } from './LogConsole';
import { CriticFindings } from './CriticFindings';
import { PlanTab } from './PlanTab';
import { ScheduleTab } from './ScheduleTab';
import { ArchitectureTab } from './ArchitectureTab';
import { PoCTab } from './PoCTab';
import { TechStackTab } from './TechStackTab';
import { X, LogOut, Upload, ShieldAlert, ChevronDown, ChevronUp, Download, Copy, Check, Loader2, Plus } from 'lucide-react';
import { generateVoiceBrief } from '../lib/voiceBrief';
import { VoiceWidgetFAB } from './VoiceWidgetFAB';
import { ThemePicker } from './ThemePicker';
import { IntegrationNotConfigured } from './IntegrationNotConfigured';
import FeedbackModal from './FeedbackModal';

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



export const AgentWorkspace: React.FC = () => {
  const { user, loading, login, logout, isAuthenticated } = useAuth();
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [runIdCopied, setRunIdCopied] = useState(false);
  const [isStartingPipeline, setIsStartingPipeline] = useState(false);
  const [modelFamily, setModelFamily] = useState('openai');
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);

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
    fallbackActive,
    elevenlabsAgentId,
  } = useWorkspace();

  const [startupError, setStartupError] = useState<string | null>(null);

  // ── Issue 2 fix: Sonner toast when a provider fallback kicks in ──────────
  // The inline banner (further down in JSX) persists for the rest of the run,
  // which is good for context. But the EM might be scrolling through artifacts
  // when the swap happens - a toast adds an attention-grabbing notification
  // for the moment of the swap so they see it immediately.
  // Auto-dismisses after 6s; the banner stays as durable context.
  useEffect(() => {
    if (!fallbackActive) return;
    const fromName = fallbackActive.from.charAt(0).toUpperCase() + fallbackActive.from.slice(1);
    const toName = fallbackActive.to.charAt(0).toUpperCase() + fallbackActive.to.slice(1);
    toast.warning(
      `${fromName} quota exceeded - using ${toName} for this run.`,
      {
        duration: 6000,
        description: 'Cost is computed against the active provider. See the banner above for full details.',
      }
    );
  }, [fallbackActive]);

  const handleDecisionSubmitted = (data: ApprovalResponse) => {
    setPipelineStatus(data.pipeline_status);
    setApprovalResult({
      decision: data.decision,
      sheet_url: data.sheet_url || undefined,
      jira_url: data.jira_url || undefined,
      rejection_count: data.rejection_count,
    });
    fetchArtifacts();
  };

  const [activeTab, setActiveTab] = useState<'plan' | 'schedule' | 'arch' | 'poc' | 'stack'>('plan');



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

  const triggerPipeline = async () => {
    if (!selectedFile) return;
    setIsStartingPipeline(true);
    setStartupError(null);
    const form = new FormData();
    form.append("file", selectedFile);
    form.append("model_family", modelFamily);
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
            <div className="bg-background p-4 rounded-lg border border-border shadow-sm space-y-3 text-center">
              <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Authentication</div>
              <p className="text-xs text-muted-foreground">Please <strong className="text-foreground font-semibold">sign in with Google</strong> to launch your live demo of EM Copilot. Signing in keeps your workspace private, ensures seamless performance, and helps us maintain a free, high-quality experience for everyone. Your email is only used to identify your sessions.</p>
              <button
                onClick={login}
                className="w-full py-2 bg-primary hover:bg-primary/90 text-white rounded font-bold text-xs transition duration-155"
              >
                Sign in with Google
              </button>
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
                    { key: 'openai', label: 'OpenAI (Default: gpt-4o)' },
                    { key: 'anthropic', label: 'Anthropic (Default: Claude 4.5 Sonnet)' },
                    { key: 'llama', label: 'Llama' },
                    { key: 'mistral', label: 'Mistral' },
                  ].map(({ key, label }) => {
                    // Default to "available" if we haven't received the providers
                    // payload yet - keeps the dropdown usable on first paint.
                    const p = providers[key];
                    const isAvailable = p?.available ?? (key === 'openai');
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
              <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Upload BRD</h3>
              <p className="text-xs text-muted-foreground">Drop a PDF, DOCX, or TXT BRD</p>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                className="border-2 border-dashed border-border rounded-lg p-6 bg-background hover:bg-card/60 hover:border-primary/50 transition cursor-pointer text-center relative"
              >
                <input
                  type="file"
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.txt"
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <Upload className="mx-auto text-primary mb-2" size={24} />
                <p className="text-xs font-semibold text-primary">Drag and drop file here</p>
                <p className="text-[10px] text-muted-foreground mt-1">Limit 5MB per file • PDF, DOCX, TXT</p>
                <button className="mt-3 px-3 py-1.5 bg-primary/10 text-primary border border-primary/30 rounded hover:bg-primary/20 hover:border-primary/50 text-xs font-semibold transition-colors">
                  Browse files
                </button>
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
              <div className="relative group/btn w-full">
                <button
                  onClick={triggerPipeline}
                  disabled={!selectedFile || !!runId || isStartingPipeline}
                  className={`w-full py-2.5 rounded-lg font-bold text-sm transition-all duration-150 flex items-center justify-center gap-2 transform ${runId || isStartingPipeline
                    ? 'bg-secondary/40 text-muted-foreground/60 border border-border/50 cursor-not-allowed shadow-none'
                    : selectedFile
                      ? 'bg-primary hover:bg-primary/95 text-primary-foreground shadow-[0_4px_14px_rgba(79,70,229,0.25)] hover:shadow-[0_4px_20px_rgba(79,70,229,0.4)] cursor-pointer hover:-translate-y-0.5 active:translate-y-0'
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
                <div className="mt-2 flex items-start gap-2 text-[11px] text-muted-foreground">
                  <span className="inline-flex h-1.5 w-1.5 rounded-full bg-primary animate-pulse shrink-0 mt-1" />
                  <span>Anticipate <strong className="text-foreground">60s &ndash; 120s</strong> total run time per BRD. Runtime varies based on the size and complexity of the BRD.</span>
                </div>
              )}
            </div>
          )}

          {/* Current Run Panel */}
          {runId && (
            <div className="border-t border-border pt-4 space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Current Run</h4>
              <div className="flex items-center gap-1.5">
                <div className="flex-1 bg-background p-2 rounded font-mono text-[10px] text-foreground border border-border break-all select-all">
                  {runId}
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
                Status: <span className="font-semibold text-success capitalize">{pipelineStatus === 'awaiting_hitl' ? 'awaiting decision' : pipelineStatus === 'critic_review' ? 'critic evaluation' : (pipelineStatus ? pipelineStatus.replace(/_/g, ' ') : "Starting...")}</span>
              </div>
              <button
                onClick={() => {
                  setSelectedFile(null);
                  clearRun();
                  setRunId(null);
                  setStartupError(null);
                }}
                className="w-full py-1.5 border border-destructive bg-destructive/10 hover:bg-destructive/40 rounded text-xs font-semibold text-destructive hover:text-destructive transition shadow-[0_0_10px_rgba(244,63,94,0.05)]"
              >
                Clear Plan & Reset
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
        <header className="min-h-16 border-b border-border px-4 md:px-8 py-3 gap-4 flex flex-col sm:flex-row sm:items-start justify-between bg-card shrink-0 shadow-sm relative">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight leading-tight">
              <span className="text-primary">EM Copilot</span>
              <span className="text-foreground">: BRD → Engineering Plan</span>
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">Multi-Agent AI Software Engineering Planning System</p>
          </div>
          {elevenlabsAgentId && runId && pipelineStatus === 'awaiting_hitl' && (
            <VoiceWidgetFAB
              agentId={elevenlabsAgentId}
              runId={runId}
              voiceBrief={generateVoiceBrief(artifacts, criticOutput, runId)}
              apiBaseUrl={apiBaseUrl}
            />
          )}
          <div className="flex items-center gap-3 self-end sm:self-auto shrink-0">
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
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-8">
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
                isLoading={pipelineStatus === 'initializing'}
                isAuthenticated={isAuthenticated}
                onLogin={login}
              />
            </div>
          ) : (
            <>
              {/* Fallback Active Alert Banner */}
              {fallbackActive && (
                <div className="bg-warning/20 border-l-4 border-warning p-4 rounded shadow-sm text-xs text-warning flex items-center justify-between animate-fade-in">
                  <div className="flex items-center gap-3">
                    <span className="text-lg">⚠️</span>
                    <div>
                      <h4 className="font-bold text-warning">Automatic LLM Provider Fallback Triggered</h4>
                      <p className="text-warning/80">
                        The primary <strong>{fallbackActive.from.toUpperCase()}</strong> provider limits were reached or key expired. Switched to <strong>{fallbackActive.to.toUpperCase()}</strong> successfully to complete execution.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Pipeline Error Alert Banner */}
              {pipelineStatus === "error" && (
                <div className="bg-danger/30 border border-danger/50 p-5 rounded-xl shadow-lg flex flex-col gap-2 animate-fade-in">
                  <h4 className="text-sm font-bold text-danger flex items-center gap-2">
                    <span>❌</span> Pipeline Execution Failed
                  </h4>
                  <p className="text-xs text-danger/90 leading-relaxed font-semibold">
                    {errorMessage || "An unexpected error occurred during execution. Please check the logs."}
                  </p>
                </div>
              )}

              {/* HITL Awaiting Alert Banner */}
              {pipelineStatus === "awaiting_hitl" && !approvalResult && (
                <div className="bg-warning/20 border-l-4 border-warning p-4 rounded shadow-sm flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">⏸️</span>
                    <div>
                      <h4 className="text-sm font-bold text-warning">Action Required: Review the Artifacts. Approval needed to push plan into Jira.</h4>
                    </div>
                  </div>
                  <a
                    href="#decision-gate"
                    className="px-4 py-2 bg-warning hover:bg-warning text-white font-semibold text-xs rounded transition shadow-sm shrink-0"
                  >
                    👇 Scroll to Decision Gate
                  </a>
                </div>
              )}

              {/* Stepper Timeline Progress Nodes */}
              <TimelineStepper
                pipelineStatus={pipelineStatus}
                completedAgents={completedAgents}
                artifacts={artifacts}
                criticOutput={criticOutput}
                approvalResult={approvalResult}
                logs={logs}
              />


              {/* Performance Metrics Summary */}
              <div className="flex flex-wrap justify-between items-center gap-4 text-xs text-muted-foreground bg-card p-4 rounded-lg border border-border">
                <div>
                  <strong>Current Status:</strong> <span className="text-foreground capitalize font-medium">{pipelineStatus === 'awaiting_hitl' ? 'awaiting decision' : pipelineStatus === 'critic_review' ? 'critic evaluation' : (pipelineStatus ? pipelineStatus.replace(/_/g, ' ') : "-")}</span>
                </div>
                <div>
                  <strong>Total Processing Time:</strong> <code className="bg-background border border-border px-2.5 py-1 rounded font-mono text-foreground">{elapsedSeconds ? `${elapsedSeconds}s` : '-'}</code>
                </div>
                <div>
                  <strong>Tokens used:</strong> <code className="bg-background border border-border px-2.5 py-1 rounded font-mono text-foreground">{tokenUsage ? `${tokenUsage.input.toLocaleString()} in / ${tokenUsage.output.toLocaleString()} out` : '-'}</code>
                </div>
                <div>
                  <strong>Cost Spent:</strong> <code className="bg-background border border-border px-2.5 py-1 rounded font-mono text-success font-bold">{costUsd != null ? `$${costUsd.toFixed(4)}` : '-'}</code>
                </div>
              </div>

              {/* Critic Scoring Cards */}
              {criticOutput && (
                <ErrorBoundary fallback={
                  <div className="p-6 bg-danger/20 border border-danger/40 rounded-xl space-y-3">
                    <div className="flex items-center gap-2 text-danger font-bold text-sm uppercase tracking-wider">
                      <ShieldAlert size={16} />
                      <span>Critic Component Failure</span>
                    </div>
                    <p className="text-xs text-danger/80 leading-relaxed">
                      An error occurred while rendering the Critic scorecards. The rest of the workspace remains active.
                    </p>
                  </div>
                }>
                  <div className="space-y-4 border border-border rounded-xl p-6 bg-card shadow-lg">
                    <div className="flex items-center justify-between border-b border-border/60 pb-4">
                      <div className="space-y-1">
                        <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">Critic - Quality Assessment</h3>
                        <div className="text-xs text-muted-foreground">
                          Revision {criticOutput.revisionNumber} · Overall <strong className="text-foreground">{criticOutput.overallScore.toFixed(2)} / 5.0</strong>
                        </div>
                      </div>
                      <span className={`px-4 py-1.5 rounded-full text-xs font-extrabold uppercase tracking-wider ${criticOutput.badge === 'green'
                        ? 'bg-success/20 text-success border border-success/40'
                        : criticOutput.badge === 'amber'
                          ? 'bg-warning/50 text-warning border border-warning/50'
                          : 'bg-danger/50 text-danger border border-danger/50'
                        }`}>
                        {criticOutput.badge === 'green' ? '🟢 GREEN' : criticOutput.badge === 'amber' ? '🟡 AMBER' : '🔴 RED'}
                      </span>
                    </div>

                    {/* Metrics row */}
                    <div className="flex flex-wrap md:flex-nowrap gap-x-4 gap-y-2 items-center justify-between text-xs text-muted-foreground pt-2">
                      {(['groundedness', 'completeness', 'consistency', 'actionability'] as const).map((metric) => {
                        const data = criticOutput.dimensions[metric];
                        if (!data) return null;
                        return (
                          <div key={metric} className="flex items-center gap-1.5 whitespace-nowrap">
                            <strong className="capitalize">{metric}:</strong>
                            <code className="bg-background border border-border px-1.5 py-0.5 rounded font-mono text-foreground font-semibold text-[11px]">
                              {data.score.toFixed(2)}
                            </code>
                            <span className={`text-[11px] font-semibold ${data.passed ? 'text-success' : 'text-danger'}`}>
                              {data.passed ? `✓ (≥${data.threshold})` : `✗ (≥${data.threshold})`}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </ErrorBoundary>
              )}

              {/* Tabbed Viewport for Artifacts */}
              {artifacts && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-border pb-2">
                    <h3 className="text-base font-bold text-foreground">Artifacts</h3>
                    <button
                      onClick={handleDownloadPDF}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-card hover:bg-secondary text-foreground border border-border rounded text-xs font-bold transition shadow-sm"
                    >
                      <Download size={14} /> Download PDF
                    </button>
                  </div>

                  {/* Disclaimer notice banner */}
                  <div className="bg-background border border-border p-4 rounded-lg text-xs leading-relaxed text-muted-foreground">
                    <span className="font-bold text-foreground uppercase">⚠️ Disclaimer:</span> It is a engineering planning assistant AI tool. Mandatory professional review and validation required before implementation.
                  </div>

                  {/* Tabs list */}
                  <div className="flex bg-background p-1 rounded-lg border border-border w-full md:w-fit overflow-x-auto scrollbar-none whitespace-nowrap">
                    {(['plan', 'schedule', 'arch', 'poc', 'stack'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2 rounded-md text-xs font-bold capitalize transition-all ${activeTab === tab
                          ? 'bg-card text-foreground shadow-sm border border-border'
                          : 'text-muted-foreground hover:text-muted-foreground'
                          }`}
                      >
                        {tab === 'arch' ? 'Architecture' : tab === 'stack' ? 'Tech Stack' : tab}
                      </button>
                    ))}
                  </div>

                  {/* Tab Display Area */}
                  <div className="border border-border rounded-xl p-6 bg-card shadow-lg min-h-[250px]">
                    <ErrorBoundary fallback={<div className="p-4 bg-danger/20 border border-danger/40 text-danger rounded-lg text-sm">Failed to render artifact.</div>}>
                      {pipelineStatus === 'dispatching' ? (
                        <PlanSkeleton />
                      ) : (
                        <div>
                          {activeTab === 'plan' && (
                            <PlanTab planData={artifacts.plan_output} />
                          )}
                          {activeTab === 'schedule' && (
                            <ScheduleTab scheduleData={artifacts.schedule_output} />
                          )}
                          {activeTab === 'arch' && (
                            <ArchitectureTab architectureData={artifacts.arch_output} />
                          )}
                          {activeTab === 'poc' && (
                            <PoCTab pocData={artifacts.poc_output} />
                          )}
                          {activeTab === 'stack' && (
                            <TechStackTab techStackData={artifacts.stack_output} />
                          )}
                        </div>
                      )}
                    </ErrorBoundary>
                  </div>
                </div>
              )}

              {/* Decision Gate Section */}
              {pipelineStatus === "awaiting_hitl" && (
                <div className="border-t border-border pt-8">
                  <ErrorBoundary fallback={
                    <div className="p-6 bg-danger/20 border border-danger/40 rounded-xl space-y-3">
                      <div className="flex items-center gap-2 text-danger font-bold text-sm uppercase tracking-wider">
                        <ShieldAlert size={16} />
                        <span>Decision Gate Component Failure</span>
                      </div>
                      <p className="text-xs text-danger/80 leading-relaxed">
                        An error occurred while loading the Decision Gate. Please try refreshing or restarting the run.
                      </p>
                    </div>
                  }>
                    <HITLApprovalGate key={runId || undefined} runId={runId!} onDecisionSubmitted={handleDecisionSubmitted} />
                  </ErrorBoundary>
                </div>
              )}

              {/* Export Status / Final Decision Section */}
              {(pipelineStatus === "exported" || pipelineStatus === "export_failed" || pipelineStatus === "rejected") && (
                <div className="border-t border-border pt-8">
                  <div className="max-w-3xl mx-auto p-6 bg-card border border-border rounded-xl space-y-6 shadow-xl animate-fade-in">
                    <div className="flex items-center justify-between border-b border-border pb-3">
                      <h3 className="text-sm font-bold text-foreground uppercase tracking-wider">Export Results</h3>
                      <span className={`px-2.5 py-1 rounded text-[10px] font-extrabold uppercase tracking-wider ${pipelineStatus === 'exported'
                        ? 'bg-success/20 border border-success/40 text-success'
                        : pipelineStatus === 'rejected'
                          ? 'bg-danger/20 border border-danger/40 text-danger'
                          : 'bg-warning/20 border border-warning/40 text-warning'
                        }`}>
                        {pipelineStatus === 'exported' ? '✓ Exported Successfully' : pipelineStatus === 'rejected' ? '✗ Plan Rejected' : '⚠ Export Failed'}
                      </span>
                    </div>

                    {pipelineStatus === 'rejected' && (
                      <div className="p-4 bg-danger/10 border border-danger/30 text-danger rounded-lg space-y-1">
                        <div className="text-xs font-bold uppercase tracking-wider">Re-evaluation Required</div>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          This plan was rejected by the manager. Review the feedback logs and adjust details before starting a new run.
                        </p>
                      </div>
                    )}

                    <div className="space-y-4">
                      {/* Google Sheets Status Box */}
                      {approvalResult?.export_status === 'ok' && approvalResult?.sheet_url ? (
                        <div className="p-4 bg-success/15 border border-success/30 rounded-lg space-y-3 animate-fade-in">
                          <div className="text-xs font-bold text-success">
                            Artifacts exported to Google Sheets
                          </div>
                          <div className="text-[11px] text-muted-foreground leading-relaxed">
                            {approvalResult?.export_detail || "Wrote Pipeline Run Summary to Google Sheets for audit purposes."}
                          </div>
                          <a
                            href={approvalResult.sheet_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-block px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground rounded font-bold text-xs transition duration-150 shadow-sm"
                          >
                            Open Google Sheet
                          </a>
                        </div>
                      ) : approvalResult?.export_status === 'local_fallback' ? (
                        <div className="p-4 bg-warning/15 border border-warning/30 rounded-lg space-y-2 animate-fade-in">
                          <div className="text-xs font-bold text-warning">
                            Artifacts saved to local fallback CSV
                          </div>
                          <div className="text-[11px] text-muted-foreground leading-relaxed">
                            {approvalResult?.export_detail || "Google Sheets integration is not configured - local CSV backup exported instead."}
                          </div>
                        </div>
                      ) : approvalResult?.export_status === 'failed' ? (
                        <div className="p-4 bg-danger/15 border border-danger/30 rounded-lg space-y-2 animate-fade-in">
                          <div className="text-xs font-bold text-danger">
                            Google Sheets export failed
                          </div>
                          <div className="text-[11px] text-danger leading-relaxed font-mono">
                            {approvalResult?.export_detail || "Failed to push decision. Google Sheets export failed."}
                          </div>
                        </div>
                      ) : null}

                      {/* Jira Status Box */}
                      {pipelineStatus !== "rejected" && (
                        approvalResult?.jira_status === 'jira' && approvalResult?.jira_url ? (
                          <div className="p-4 bg-success/15 border border-success/30 rounded-lg space-y-3 animate-fade-in">
                            <div className="text-xs font-bold text-success">
                              Pushed to Jira: {approvalResult.jira_issue_key}
                            </div>
                            <div className="text-[11px] text-muted-foreground leading-relaxed">
                              {approvalResult?.jira_detail || `Created Jira Epic ${approvalResult.jira_issue_key} via MCP (mcp-atlassian server)`}
                            </div>
                            <a
                              href={approvalResult.jira_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-block px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground rounded font-bold text-xs transition duration-150 shadow-sm"
                            >
                              Open Jira issue {approvalResult.jira_issue_key}
                            </a>
                          </div>
                        ) : approvalResult?.jira_status === 'skipped' ? (
                          <div className="p-4 bg-card border border-border rounded-lg space-y-1 animate-fade-in">
                            <div className="text-xs font-bold text-muted-foreground">
                              Jira push skipped
                            </div>
                            <div className="text-[11px] text-muted-foreground leading-relaxed">
                              {approvalResult?.jira_detail || "Jira push was skipped for this pipeline run."}
                            </div>
                          </div>
                        ) : approvalResult?.jira_status === 'failed' ? (
                          <div className="p-4 bg-danger/15 border border-danger/30 rounded-lg space-y-2 animate-fade-in">
                            <div className="text-xs font-bold text-danger">
                              Jira push failed
                            </div>
                            <div className="text-[11px] text-danger leading-relaxed font-mono">
                              {approvalResult?.jira_detail || "Jira push failed. Check configuration and service settings."}
                            </div>
                          </div>
                        ) : (
                          /* Fallback when backend didn't include any jira_status
                             (e.g. Jira credentials not configured on this deploy). */
                          <IntegrationNotConfigured
                            title="Jira push not available"
                            envVars={["JIRA_API_TOKEN", "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_PROJECT_KEY"]}
                            description="Jira integration is not configured on this deployment, so the engineering plan was not pushed as a Jira Epic."
                            docsAnchor="#L59-L65"
                          />
                        )
                      )}
                    </div>

                    {/* Primary CTA - natural "what now?" path after terminal state.
                        Same effect as the sidebar's destructive "Clear Plan & Reset"
                        but framed as a forward action (indigo, not red) since the
                        user has just finished a run, not aborting one mid-flight. */}
                    <div className="border-t border-border pt-5 flex justify-end">
                      <button
                        onClick={() => {
                          setSelectedFile(null);
                          clearRun();
                          setRunId(null);
                        }}
                        className="flex items-center gap-2 px-5 py-2.5 bg-primary hover:bg-primary/90 rounded text-xs font-bold text-white uppercase tracking-wider transition shadow-md hover:shadow-primary/30"
                      >
                        <Plus size={14} />
                        Start New Plan
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Tavily fallback hint - surfaces when the pipeline tried Tavily web
                  grounding but the API key isn't configured on this deployment.
                  The backend emits tool_call_degraded events into the SSE stream;
                  useSSE pushes them into `logs`. We scan for a Tavily api_key_missing
                  reason - if found, render the hint above Critic findings. */}
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
                  <IntegrationNotConfigured
                    title="Web grounding fallback unavailable"
                    envVars={['TAVILY_API_KEY']}
                    description="The Architect or Tech Stack agent hit a RAG miss and would have used Tavily for live web grounding, but Tavily is not configured on this deployment. The pipeline continued with RAG-only context."
                    docsAnchor="#L74-L78"
                  />
                ) : null;
              })()}

              {/* Critic findings - consistency issues + hallucination flags */}
              <CriticFindings criticDetail={artifacts?.critic_output} />

              {/* Live Log Console */}
              <div className="border-t border-border pt-8">
                <LogConsole logs={logs} />
              </div>
            </>
          )}
        </div>

        {/* Persistent footer disclaimer - sits outside the scrollable body so
            it stays visible at all times (matches Claude.ai / ChatGPT pattern).
            Moved here from the header subtitle, where it was undermining the
            product's perceived reliability by appearing alongside the title. */}
        <footer className="px-8 py-2 border-t border-border bg-card text-center text-[10px] text-foreground/65 shrink-0">
          Disclaimer: AI generated plans are starting points. Professional review and validation required before implementation.
        </footer>
      </main>

      <FeedbackModal
        isOpen={isFeedbackOpen}
        onClose={() => setIsFeedbackOpen(false)}
        runId={runId}
        apiBaseUrl={apiBaseUrl}
      />
    </div>
  );
};
