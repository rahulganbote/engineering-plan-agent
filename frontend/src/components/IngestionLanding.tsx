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
      label: '5 Specialists',
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

  const mermaidCode = `graph TD
    Security[1. Security Validation] --> Orchestrator[2. Orchestrator Parser]
    Orchestrator --> Specialists[3. 5 Specialist Agents]
    subgraph Specialists [Specialists Spoke]
        Plan[Plan Generator]
        Schedule[Schedule Estimator]
        Arch[Solution Architect]
        PoC[PoC Scope]
        Stack[Tech Stack Matcher]
    end
    Specialists --> Critic[4. Critic Rubric Grade]
    Critic -->|Below Threshold| Specialists
    Critic -->|Passed| HITL[5. EM HITL Approval Gate]
    HITL -->|Approved| Export[6. Google Sheets & Jira Export]`;

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
          <span>Anticipate <strong className="text-slate-300">45s &ndash; 90s</strong> total run time per BRD.</span>
        </div>
      </div>

      {/* System Architecture Diagram — full width (File Ingestion Guide removed per UX request) */}
      <div>
        <div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-6 shadow-md">
            <div>
              <h3 className="text-sm font-bold text-slate-200">System Architecture Diagram</h3>
              <p className="text-xs text-slate-500 mt-1">
                Hover or click on the orchestration nodes to study the specific agent roles.
              </p>
            </div>

            {/* Interactive Flow Visualizer */}
            <div className="flex flex-col md:flex-row gap-6 items-center justify-center py-4 bg-slate-950/80 rounded-xl p-4 border border-slate-900 relative min-h-[300px]">
              {/* Spoke layout */}
              <div className="flex flex-col gap-3 w-full md:w-5/12 z-10">
                {pipelineNodes.slice(0, 3).map((node) => (
                  <div
                    key={node.id}
                    className={`p-3 rounded-lg border text-left cursor-pointer transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-slate-600 hover:bg-slate-900'
                      }`}
                    onMouseEnter={() => setActiveNode(node.id)}
                    onMouseLeave={() => setActiveNode(null)}
                  >
                    <div className="flex items-center gap-2">
                      {node.icon}
                      <span className="text-xs font-bold">{node.label}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Central Arrow/Pulsing Visual Indicator */}
              <div className="flex flex-row md:flex-col items-center justify-center gap-2 shrink-0">
                <div className="h-6 w-0.5 bg-gradient-to-b from-indigo-500 to-amber-500 hidden md:block animate-pulse" />
                <span className="text-xs font-semibold px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-full text-slate-400 text-center select-none font-mono">
                  State Loop
                </span>
                <div className="h-6 w-0.5 bg-gradient-to-b from-amber-500 to-rose-500 hidden md:block animate-pulse" />
              </div>

              {/* Second column of nodes */}
              <div className="flex flex-col gap-3 w-full md:w-5/12 z-10">
                {pipelineNodes.slice(3).map((node) => (
                  <div
                    key={node.id}
                    className={`p-3 rounded-lg border text-left cursor-pointer transition-all duration-200 ${node.color} ${activeNode === node.id ? node.activeColor : 'hover:border-slate-600 hover:bg-slate-900'
                      }`}
                    onMouseEnter={() => setActiveNode(node.id)}
                    onMouseLeave={() => setActiveNode(null)}
                  >
                    <div className="flex items-center gap-2">
                      {node.icon}
                      <span className="text-xs font-bold">{node.label}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Dynamic Node Detail View */}
            <div className="h-24 bg-slate-950 p-4 rounded-lg border border-slate-900 flex flex-col justify-center">
              {activeNode ? (
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wide">
                    {pipelineNodes.find((n) => n.id === activeNode)?.label}
                  </h4>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {pipelineNodes.find((n) => n.id === activeNode)?.desc}
                  </p>
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic text-center">
                  Hover over any agent box in the layout flow above to view execution details.
                </p>
              )}
            </div>

            {/* Mermaid Syntax Accordion Panel */}
            <details className="group border border-slate-900 rounded-lg overflow-hidden bg-slate-950">
              <summary className="px-4 py-2.5 bg-slate-950 hover:bg-slate-900/50 cursor-pointer flex justify-between items-center text-xs font-bold text-slate-400 select-none">
                <span>📋 View Mermaid Diagram Source</span>
                <span className="text-[10px] group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="p-4 border-t border-slate-900 font-mono text-[10px] text-slate-400 overflow-x-auto whitespace-pre bg-slate-950 leading-relaxed">
                {mermaidCode}
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
};
