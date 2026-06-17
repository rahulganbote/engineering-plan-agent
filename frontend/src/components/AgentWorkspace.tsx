import React, { useState } from 'react';
import { useWorkspace } from '../context/WorkspaceContext';
import { useAuth } from '../context/AuthContext';
import { PlanSkeleton } from './PlanSkeleton';
import { ErrorBoundary } from './ErrorBoundary';
import { HITLApprovalGate, type ApprovalResponse } from './HITLApprovalGate';
import { IngestionLanding } from './IngestionLanding';
import { TimelineStepper } from './TimelineStepper';
import { LogConsole } from './LogConsole';
import { X, LogOut, Upload, ShieldAlert, ChevronDown, ChevronUp, Download, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

// Sprint 3 stopgap: backend artifacts are structured objects (EngineeringPlanOutput,
// ScheduleOutput, etc.). React can't render an object as a child — it throws and
// the ErrorBoundary catches it. JSON.stringify gives us a readable view until Sprint 4
// builds proper structured renderers.
function renderArtifact(value: unknown, fallback: string): string {
  if (value == null) return fallback;
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export const AgentWorkspace: React.FC = () => {
  const { user, loading, login, logout, isAuthenticated } = useAuth();
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [runIdCopied, setRunIdCopied] = useState(false);

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
    criticOutput,
    approvalResult,
    clearRun,
    fetchArtifacts,
    setPipelineStatus,
    setApprovalResult,
  } = useWorkspace();

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
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const triggerPipeline = async () => {
    if (!selectedFile) return;
    const form = new FormData();
    form.append("file", selectedFile);
    try {
      const response = await fetch(`${apiBaseUrl}/run-pipeline`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setRunId(data.run_id);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : String(e);
      toast.error(`Failed to start pipeline: ${errMsg}`);
    }
  };

  const handleDownloadPDF = () => {
    if (!runId) return;
    window.location.href = `${apiBaseUrl}/download/${runId}`;
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Left Sidebar Control Panel */}
      <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col justify-between overflow-y-auto shadow-xl">
        <div className="p-6 space-y-6">
          {/* User Sign-In/Sign-Out Container */}
          {loading ? (
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 text-center text-xs text-slate-500">
              Loading session...
            </div>
          ) : isAuthenticated ? (
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 font-medium">Signed in:</span>
                <button 
                  onClick={logout}
                  className="text-xs text-indigo-400 hover:text-indigo-300 hover:underline flex items-center gap-1 font-semibold"
                >
                  Sign out <LogOut size={12} />
                </button>
              </div>
              <div className="text-sm font-semibold text-slate-200 truncate">{user?.name || user?.email}</div>
            </div>
          ) : (
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 shadow-sm space-y-3 text-center">
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Authentication</div>
              <p className="text-xs text-slate-500">Sign in to unlock BRD processing pipeline.</p>
              <button
                onClick={login}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-bold text-xs transition duration-155"
              >
                Sign in with Google
              </button>
            </div>
          )}

          {/* Upload BRD Section */}
          {isAuthenticated && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Upload BRD</h3>
              <p className="text-xs text-slate-500">Drop a PDF, DOCX, or TXT BRD</p>
              
              <div 
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                className="border-2 border-dashed border-slate-800 rounded-lg p-6 bg-slate-950 hover:bg-slate-900/60 hover:border-indigo-500/50 transition cursor-pointer text-center relative"
              >
                <input 
                  type="file" 
                  onChange={handleFileChange} 
                  accept=".pdf,.docx,.txt" 
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <Upload className="mx-auto text-slate-600 mb-2" size={24} />
                <p className="text-xs font-semibold text-slate-400">Drag and drop file here</p>
                <p className="text-[10px] text-slate-600 mt-1">Limit 25MB per file • PDF, DOCX, TXT</p>
                <button className="mt-3 px-3 py-1.5 bg-slate-900 text-slate-300 border border-slate-800 rounded hover:bg-slate-800 text-xs font-medium">
                  Browse files
                </button>
              </div>

              {selectedFile && (
                <div className="flex items-center justify-between p-2 bg-slate-950 rounded border border-slate-800 text-xs">
                  <span className="truncate max-w-[180px] font-medium text-slate-300">{selectedFile.name}</span>
                  <span className="text-slate-500 text-[10px] ml-2">{(selectedFile.size / 1024).toFixed(1)}KB</span>
                  <button
                    onClick={() => setSelectedFile(null)}
                    className="text-slate-500 hover:text-red-400 ml-2"
                    aria-label="Remove selected file"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Demo Warning Banner */}
          {isAuthenticated && (
            <div className="bg-indigo-950/20 border border-indigo-900/30 p-4 rounded-lg flex gap-2">
              <ShieldAlert className="text-indigo-400 shrink-0" size={16} />
              <p className="text-[11px] leading-relaxed text-indigo-300">
                <strong>Demo Purpose Only:</strong> This application is for demo purposes only. The AI can make mistakes. Validate outputs.
              </p>
            </div>
          )}

          {/* Trigger Button */}
          {isAuthenticated && (
            <button
              onClick={triggerPipeline}
              disabled={!selectedFile || !!runId}
              className={`w-full py-2.5 rounded-lg font-semibold text-sm transition flex items-center justify-center gap-2 ${
                runId 
                  ? 'bg-slate-850 text-slate-600 border border-slate-800 cursor-not-allowed'
                  : selectedFile 
                    ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md' 
                    : 'bg-slate-850 text-slate-600 border border-slate-800 cursor-not-allowed'
              }`}
            >
              Generate Engineering Plan
            </button>
          )}

          {/* Current Run Panel */}
          {runId && (
            <div className="border-t border-slate-800 pt-4 space-y-2">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Current Run</h4>
              <div className="flex items-center gap-1.5">
                <div className="flex-1 bg-slate-950 p-2 rounded font-mono text-[10px] text-slate-300 border border-slate-850 break-all select-all">
                  {runId}
                </div>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(runId);
                    setRunIdCopied(true);
                    setTimeout(() => setRunIdCopied(false), 2000);
                  }}
                  className="p-1.5 bg-slate-950 border border-slate-850 rounded hover:bg-slate-800 hover:text-white transition text-slate-450 shrink-0"
                  title="Copy Run ID"
                >
                  {runIdCopied ? (
                    <Check size={12} className="text-emerald-400 animate-scale-in" />
                  ) : (
                    <Copy size={12} />
                  )}
                </button>
              </div>
              <div className="text-xs text-slate-400">
                Status: <span className="font-semibold text-green-400">{pipelineStatus || "Starting..."}</span>
              </div>
              <button
                onClick={() => {
                  setSelectedFile(null);
                  clearRun();
                  setRunId(null);
                }}
                className="w-full py-1.5 border border-slate-800 hover:bg-slate-850 rounded text-xs font-medium text-slate-300 transition"
              >
                Clear Plan & Reset
              </button>
            </div>
          )}
        </div>

        {/* Collapsible Advanced Settings Accordion */}
        <div className="border-t border-slate-800 bg-slate-900/40">
          <button 
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="w-full px-6 py-4 flex items-center justify-between text-xs font-bold text-slate-400 hover:bg-slate-850/40 transition uppercase tracking-wider"
          >
            <span>⚙️ Advanced settings</span>
            {isAdvancedOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {isAdvancedOpen && (
            <div className="px-6 pb-6 pt-2 space-y-3">
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1">API Base URL</label>
                <input 
                  type="text" 
                  value={apiBaseUrl} 
                  onChange={(e) => setApiBaseUrl(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-slate-200 font-mono"
                />
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main Workstation Panel */}
      <main className="flex-1 flex flex-col overflow-hidden bg-slate-950">
        {/* Main Header */}
        <header className="h-16 border-b border-slate-800 px-8 flex items-center justify-between bg-slate-900 shrink-0 shadow-sm">
          <div>
            <h1 className="text-lg font-bold text-slate-100">BRD → Engineering Plan</h1>
            <p className="text-xs text-slate-500">EM Copilot | Multi-Agent BRD-to-Engineering Plan System with HITL</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${runId ? 'bg-green-500 animate-pulse' : 'bg-slate-650'}`} />
            <span className="text-xs font-semibold text-slate-400">
              {runId ? "API connected" : "API Offline"}
            </span>
          </div>
        </header>
        {/* Scrollable Workstation Body */}
        <div className="flex-1 overflow-y-auto p-8 space-y-8">
          {!runId ? (
            <IngestionLanding
              selectedFile={selectedFile}
              onFileSelect={setSelectedFile}
              onRemoveFile={() => setSelectedFile(null)}
              onTrigger={triggerPipeline}
              isLoading={pipelineStatus === 'initializing'}
              isAuthenticated={isAuthenticated}
              onLogin={login}
            />
          ) : (
            <>
              {/* HITL Awaiting Alert Banner */}
              {pipelineStatus === "awaiting_hitl" && !approvalResult && (
                <div className="bg-amber-950/20 border-l-4 border-amber-600 p-4 rounded shadow-sm flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">⏸️</span>
                    <div>
                      <h4 className="text-sm font-bold text-amber-400">Action Required: Approval Needed</h4>
                      <p className="text-xs text-amber-300/80">The multi-agent pipeline is paused. Please review the generated plans and approve below.</p>
                    </div>
                  </div>
                  <a 
                    href="#decision-gate" 
                    className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs rounded transition shadow-sm shrink-0"
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
              />

              {/* Critic Rubric Scoring Cards */}
              {criticOutput && (
                <div className="space-y-4 border border-slate-800 rounded-xl p-6 bg-slate-900 shadow-lg">
                  <div className="flex items-center justify-between border-b border-slate-800/60 pb-4">
                    <div className="space-y-1">
                      <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">Critic — Quality Assessment</h3>
                      <div className="text-xs text-slate-500">
                        Revision {criticOutput.revisionNumber} · Overall <strong className="text-slate-200">{criticOutput.overallScore.toFixed(2)} / 5.0</strong>
                      </div>
                    </div>
                    <span className={`px-4 py-1.5 rounded-full text-xs font-extrabold uppercase tracking-wider ${
                      criticOutput.badge === 'green'
                        ? 'bg-green-950/50 text-green-400 border border-green-800/50' 
                        : criticOutput.badge === 'amber'
                          ? 'bg-amber-950/50 text-amber-400 border border-amber-800/50'
                          : 'bg-red-950/50 text-red-400 border border-red-800/50'
                    }`}>
                      {criticOutput.badge === 'green' ? '🟢 GREEN' : criticOutput.badge === 'amber' ? '🟡 AMBER' : '🔴 RED'}
                    </span>
                  </div>

                  {/* Metrics block */}
                  <div className="grid grid-cols-4 gap-4 pt-2">
                    {(['groundedness', 'completeness', 'consistency', 'actionability'] as const).map((metric) => {
                      const data = criticOutput.dimensions[metric];
                      if (!data) return null;
                      return (
                        <div key={metric} className="p-4 bg-slate-950 rounded-lg border border-slate-800 text-center">
                          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider capitalize">{metric}</div>
                          <div className="text-2xl font-extrabold text-slate-200 my-1">{data.score.toFixed(2)}</div>
                          <div className={`text-xs font-semibold ${data.passed ? 'text-green-400' : 'text-red-400'}`}>
                            {data.passed ? `✓ Passed (≥ ${data.threshold})` : `✗ Failed (≥ ${data.threshold})`}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Performance Metrics Summary */}
              <div className="flex justify-between items-center text-xs text-slate-400 bg-slate-900 p-4 rounded-lg border border-slate-800">
                <div>
                  <strong>Current Status:</strong> <span className="text-slate-200 capitalize font-medium">{pipelineStatus || "—"}</span>
                </div>
                <div>
                  <strong>Total Processing Time:</strong> <code className="bg-slate-950 border border-slate-800 px-2.5 py-1 rounded font-mono text-slate-200">{elapsedSeconds ? `${elapsedSeconds}s` : '—'}</code>
                </div>
                <div>
                  <strong>Tokens used:</strong> <code className="bg-slate-950 border border-slate-800 px-2.5 py-1 rounded font-mono text-slate-200">{tokenUsage ? `${tokenUsage.input.toLocaleString()} in / ${tokenUsage.output.toLocaleString()} out` : '—'}</code>
                </div>
              </div>

              {/* Live Log Console */}
              <LogConsole logs={logs} />

              {/* Tabbed Viewport for Artifacts */}
              {artifacts && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <h3 className="text-base font-bold text-slate-100">Artifacts</h3>
                    <button
                      onClick={handleDownloadPDF}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-800 rounded text-xs font-bold transition shadow-sm"
                    >
                      <Download size={14} /> Download PDF
                    </button>
                  </div>

                  {/* Disclaimer notice banner */}
                  <div className="bg-slate-950 border border-slate-850 p-4 rounded-lg text-xs leading-relaxed text-slate-400">
                    <span className="font-bold text-slate-200 uppercase">Disclaimer:</span> This is a capstone demo. Outputs may contain errors. Validate before acting on them.
                  </div>

                  {/* Tabs list */}
                  <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 w-fit">
                    {(['plan', 'schedule', 'arch', 'poc', 'stack'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2 rounded-md text-xs font-bold capitalize transition-all ${
                          activeTab === tab 
                            ? 'bg-slate-900 text-slate-100 shadow-sm border border-slate-800' 
                            : 'text-slate-500 hover:text-slate-350'
                        }`}
                      >
                        {tab === 'arch' ? 'Architecture' : tab === 'stack' ? 'Tech Stack' : tab}
                      </button>
                    ))}
                  </div>

                  {/* Tab Display Area */}
                  <div className="border border-slate-800 rounded-xl p-6 bg-slate-900 shadow-lg min-h-[250px]">
                    <ErrorBoundary fallback={<div className="p-4 bg-red-950/20 border border-red-800/40 text-red-400 rounded-lg text-sm">Failed to render artifact.</div>}>
                      {pipelineStatus === 'dispatching' ? (
                        <PlanSkeleton />
                      ) : (
                        <div>
                          {activeTab === 'plan' && (
                            <div className="text-slate-350 text-sm">
                              <h4 className="text-sm font-bold text-slate-200 mb-2 uppercase tracking-wide">Engineering Plan</h4>
                              <pre className="p-4 bg-slate-950 rounded border border-slate-850 font-mono text-xs overflow-x-auto whitespace-pre-wrap text-slate-300">
                                {renderArtifact(artifacts.plan_output, "Plan content is loading or not generated.")}
                              </pre>
                            </div>
                          )}
                          {activeTab === 'schedule' && (
                            <div className="text-slate-355 text-sm">
                              <h4 className="text-sm font-bold text-slate-200 mb-2 uppercase tracking-wide">Timeline & Milestones</h4>
                              <pre className="p-4 bg-slate-950 rounded border border-slate-850 font-mono text-xs overflow-x-auto whitespace-pre-wrap text-slate-300">
                                {renderArtifact(artifacts.schedule_output, "Timeline schedule is loading or not generated.")}
                              </pre>
                            </div>
                          )}
                          {activeTab === 'arch' && (
                            <div className="text-slate-355 text-sm">
                              <h4 className="text-sm font-bold text-slate-200 mb-2 uppercase tracking-wide">Architecture Spec</h4>
                              <pre className="p-4 bg-slate-950 rounded border border-slate-850 font-mono text-xs overflow-x-auto whitespace-pre-wrap text-slate-300">
                                {renderArtifact(artifacts.arch_output, "Architecture diagram source is loading or not generated.")}
                              </pre>
                            </div>
                          )}
                          {activeTab === 'poc' && (
                            <div className="text-slate-355 text-sm">
                              <h4 className="text-sm font-bold text-slate-200 mb-2 uppercase tracking-wide">PoC Code Scope</h4>
                              <pre className="p-4 bg-slate-950 rounded border border-slate-850 font-mono text-xs overflow-x-auto whitespace-pre-wrap text-slate-300">
                                {renderArtifact(artifacts.poc_output, "PoC code is loading or not generated.")}
                              </pre>
                            </div>
                          )}
                          {activeTab === 'stack' && (
                            <div className="text-slate-355 text-sm">
                              <h4 className="text-sm font-bold text-slate-200 mb-2 uppercase tracking-wide">Tech Stack Matrix</h4>
                              <pre className="p-4 bg-slate-950 rounded border border-slate-850 font-mono text-xs overflow-x-auto whitespace-pre-wrap text-slate-300">
                                {renderArtifact(artifacts.stack_output, "Tech stack information is loading or not generated.")}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </ErrorBoundary>
                  </div>
                </div>
              )}

              {/* Decision Gate Section */}
              {pipelineStatus === "awaiting_hitl" && (
                <div className="border-t border-slate-800 pt-8">
                  <HITLApprovalGate runId={runId!} onDecisionSubmitted={handleDecisionSubmitted} />
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
};
