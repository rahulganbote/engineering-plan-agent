import React, { useState } from 'react';
import { ShieldCheck, Cpu, GitPullRequest, Milestone, Sparkles } from 'lucide-react';

interface IngestionLandingProps {
  selectedFile: File | null;
  onFileSelect: (file: File) => void;
  onRemoveFile: () => void;
  onTrigger: () => void;
  isLoading: boolean;
  isAuthenticated: boolean;
  onLogin: () => void;
}

export const IngestionLanding: React.FC<IngestionLandingProps> = () => {
  const [activeNode, setActiveNode] = useState<string | null>(null);

  // Node details for interactive flowchart
  const pipelineNodes = [
    {
      id: 'security',
      label: 'Security Validator',
      desc: 'Performs file size scans, prompt injection assessment, and filters/redacts PII patterns.',
      icon: <ShieldCheck size={20} className="text-emerald-400" />,
      color: 'border-emerald-500/30 text-emerald-400 bg-emerald-950/20',
      activeColor: 'ring-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.3)]',
    },
    {
      id: 'orchestrator',
      label: 'Orchestrator',
      desc: 'Parses the BRD sections, evaluates structure completeness, and splits tasks for specialists.',
      icon: <Cpu size={20} className="text-blue-400" />,
      color: 'border-blue-500/30 text-blue-400 bg-blue-950/20',
      activeColor: 'ring-blue-500/50 shadow-[0_0_15px_rgba(59,130,246,0.3)]',
    },
    {
      id: 'specialists',
      label: '5 Specialists (AI Agent)',
      desc: 'Parallel agents: Plan Generator, Schedule Estimator, Solution Architect, PoC Engineer, and Tech Stack Matcher.',
      icon: <Sparkles size={20} className="text-indigo-400" />,
      color: 'border-indigo-500/30 text-indigo-400 bg-indigo-950/20',
      activeColor: 'ring-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.3)]',
    },
    {
      id: 'critic',
      label: 'Critic Reviewer',
      desc: 'Grades the outputs on a 4-dimension quality rubric (1.0 - 5.0 score) and initiates revision loops if needed.',
      icon: <GitPullRequest size={20} className="text-amber-400" />,
      color: 'border-amber-500/30 text-amber-400 bg-amber-950/20',
      activeColor: 'ring-amber-500/50 shadow-[0_0_15px_rgba(245,158,11,0.3)]',
    },
    {
      id: 'manager',
      label: 'Manager (HITL) Gate',
      desc: 'Pauses execution to obtain engineering manager approval before exporting to Google Sheets and Jira.',
      icon: <Milestone size={20} className="text-rose-400" />,
      color: 'border-rose-500/30 text-rose-400 bg-rose-950/20',
      activeColor: 'ring-rose-500/50 shadow-[0_0_15px_rgba(244,63,94,0.3)]',
    },
  ];



  return (
    <div className="space-y-8 max-w-6xl mx-auto py-4">
      {/* Welcome & Subtitle Section */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-slate-300">
          Transform BRDs into Implementation Plans in Minutes
        </h2>
        <p className="text-sm text-slate-400 max-w-3xl leading-relaxed">
          EM Copilot is a Multi-Agent AI system that transforms raw Business Requirements Documents (BRDs) into an audit-ready engineering plan package, and presented to you for review. Upon approval, it pushes the Artifacts into Jira.
        </p>
        {/* Runtime hint — formerly inside the File Ingestion Guide box */}
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="inline-flex h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
          <span>Anticipate <strong className="text-slate-300">60s &ndash; 180s</strong> total run time per BRD.</span>
        </div>
      </div>

      {/* System Architecture Diagram — full width, compact above-the-fold layout */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4 shadow-md">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-bold text-slate-200">System Architecture Diagram</h3>
          <p className="text-[11px] text-slate-500 italic">Hover each step for execution details</p>
        </div>

        {/* Interactive Flow Visualizer — compact (tooltip replaces the old 96px detail box) */}
        <div className="flex flex-col md:flex-row gap-4 items-center justify-center py-2 bg-slate-950/80 rounded-xl px-3 border border-slate-900 relative">
          {/* Spoke layout — left column */}
          <div className="flex flex-col gap-2.5 w-full md:w-5/12 z-10">
            {pipelineNodes.slice(0, 3).map((node) => (
              <div
                key={node.id}
                className="relative group"
                onMouseEnter={() => setActiveNode(node.id)}
                onMouseLeave={() => setActiveNode(null)}
              >
                <div
                  className={`p-2.5 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-slate-600'}`}
                >
                  <div className="flex items-center gap-2">
                    {node.icon}
                    <span className="text-xs font-bold">{node.label}</span>
                  </div>
                </div>

                {/* Hover tooltip — anchored above the card, fades in */}
                {activeNode === node.id && (
                  <div
                    role="tooltip"
                    className="absolute z-30 left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 p-3
                               bg-slate-950 border border-slate-700 rounded-lg shadow-2xl
                               pointer-events-none animate-in fade-in zoom-in-95 duration-150"
                  >
                    <div className="flex items-center gap-2 mb-1.5 pb-1.5 border-b border-slate-800">
                      {node.icon}
                      <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wide">{node.label}</h4>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{node.desc}</p>
                    {/* Tooltip arrow */}
                    <span className="absolute top-full left-1/2 -translate-x-1/2 w-3 h-3 -mt-1.5 rotate-45 bg-slate-950 border-r border-b border-slate-700" />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Central "State Loop" pill */}
          <div className="flex flex-row md:flex-col items-center justify-center gap-2 shrink-0">
            <div className="h-5 w-0.5 bg-gradient-to-b from-indigo-500 to-amber-500 hidden md:block animate-pulse" />
            <span className="text-[11px] font-semibold px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-full text-slate-400 text-center select-none font-mono">
              State Loop
            </span>
            <div className="h-5 w-0.5 bg-gradient-to-b from-amber-500 to-rose-500 hidden md:block animate-pulse" />
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-2.5 w-full md:w-5/12 z-10">
            {pipelineNodes.slice(3).map((node) => (
              <div
                key={node.id}
                className="relative group"
                onMouseEnter={() => setActiveNode(node.id)}
                onMouseLeave={() => setActiveNode(null)}
              >
                <div
                  className={`p-2.5 rounded-lg border text-left cursor-help transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-slate-600'}`}
                >
                  <div className="flex items-center gap-2">
                    {node.icon}
                    <span className="text-xs font-bold">{node.label}</span>
                  </div>
                </div>

                {activeNode === node.id && (
                  <div
                    role="tooltip"
                    className="absolute z-30 left-1/2 -translate-x-1/2 bottom-full mb-2 w-72 p-3
                               bg-slate-950 border border-slate-700 rounded-lg shadow-2xl
                               pointer-events-none animate-in fade-in zoom-in-95 duration-150"
                  >
                    <div className="flex items-center gap-2 mb-1.5 pb-1.5 border-b border-slate-800">
                      {node.icon}
                      <h4 className="text-xs font-bold text-slate-100 uppercase tracking-wide">{node.label}</h4>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{node.desc}</p>
                    <span className="absolute top-full left-1/2 -translate-x-1/2 w-3 h-3 -mt-1.5 rotate-45 bg-slate-950 border-r border-b border-slate-700" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
