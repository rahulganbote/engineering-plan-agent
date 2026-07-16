import React, { useState } from 'react';
import { 
  Shield, Cpu, UserCheck, Check, Loader2, X, 
  Database, Sparkles, Wrench, GitPullRequest, BookOpen, 
  ChevronDown, ChevronUp, FileText, MessageSquare 
} from 'lucide-react';
import { type ArtifactsState, type CriticOutput, type LogEvent } from '../hooks/useSSE';
import { type PipelineStatus, PIPELINE_STATUS } from '../lib/pipelineStatus';

interface TimelineStepperProps {
  pipelineStatus: PipelineStatus;
  completedAgents: Set<string>;
  artifacts: ArtifactsState | null;
  criticOutput: CriticOutput | null;
  logs: LogEvent[];
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const TimelineStepper: React.FC<TimelineStepperProps> = ({
  pipelineStatus,
  completedAgents,
  artifacts: _artifacts,
  criticOutput,
  logs,
  isCollapsed = false,
  onToggleCollapse,
}) => {
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null);

  // Helper to determine status of individual specialists in Pass 1 vs Pass 2
  const getDetailedStatus = (agentKey: string): 'pending' | 'running' | 'completed' | 'failed' => {
    if (pipelineStatus === PIPELINE_STATUS.IDLE) return 'pending';

    // During active drafting, refer to Pass 1 logs
    if (pipelineStatus === PIPELINE_STATUS.DRAFTING) {
      if (completedAgents.has(agentKey)) return 'completed';
      const hasStarted = logs.some(l => l.type === 'agent_start' && (l.agent === agentKey || l.payload?.agent === agentKey));
      return hasStarted ? 'running' : 'pending';
    }

    // During alignment/arbitration, check Pass 2 logs
    if (pipelineStatus === PIPELINE_STATUS.ARBITRATING || pipelineStatus === PIPELINE_STATUS.ALIGNING) {
      const reconciledIdx = logs.findIndex(l => l.type === 'orchestrator_reconciled');
      if (reconciledIdx === -1) return 'completed'; // completed Pass 1, waiting on arbitration
      const pass2Logs = logs.slice(reconciledIdx + 1);
      const hasCompleted = pass2Logs.some(l => l.type === 'agent_complete' && (l.agent === agentKey || l.payload?.agent === agentKey));
      if (hasCompleted) return 'completed';
      const hasStarted = pass2Logs.some(l => l.type === 'agent_start' && (l.agent === agentKey || l.payload?.agent === agentKey));
      return hasStarted ? 'running' : 'pending';
    }

    // Failures
    const hasFailed = logs.some(l => l.type === 'agent_failed' && (l.agent === agentKey || l.payload?.agent === agentKey));
    if (hasFailed) return 'failed';

    // Terminal or post-alignment states are all completed
    return 'completed';
  };

  // Node state descriptors
  const nodes = {
    security: {
      label: 'Security Validator',
      desc: 'Performs file size validation, prompt injection checks, and redacts PII patterns.',
      isActive: pipelineStatus === PIPELINE_STATUS.SECURITY_CHECK || pipelineStatus === PIPELINE_STATUS.INITIALIZING || pipelineStatus === PIPELINE_STATUS.STARTED,
      isCompleted: pipelineStatus !== PIPELINE_STATUS.IDLE && pipelineStatus !== PIPELINE_STATUS.SECURITY_CHECK && pipelineStatus !== PIPELINE_STATUS.INITIALIZING && pipelineStatus !== PIPELINE_STATUS.STARTED,
      isFailed: pipelineStatus === PIPELINE_STATUS.ERROR && !logs.some(l => l.type === 'security_complete'),
    },
    orchestrator: {
      label: 'Orchestrator Agent',
      desc: 'Parses BRD structure, distributes tasks to specialists, and aligns plans in the 2nd pass.',
      isActive: pipelineStatus === PIPELINE_STATUS.RUNNING || pipelineStatus === PIPELINE_STATUS.ORCHESTRATOR_PARSING || pipelineStatus === PIPELINE_STATUS.ARBITRATING,
      isCompleted: ([PIPELINE_STATUS.DRAFTING, PIPELINE_STATUS.ALIGNING, PIPELINE_STATUS.EVALUATING, PIPELINE_STATUS.REVISING, PIPELINE_STATUS.AWAITING_HITL, PIPELINE_STATUS.EXPORTING, PIPELINE_STATUS.EXPORTED, PIPELINE_STATUS.REJECTED] as string[]).includes(pipelineStatus),
      isFailed: pipelineStatus === PIPELINE_STATUS.ERROR && !logs.some(l => l.type === 'agent_complete' && l.agent === 'orchestrator'),
    },
    critic: {
      label: 'Critic Agent',
      desc: 'Evaluates plan quality against organizational dimensions (groundedness, completeness).',
      isActive: pipelineStatus === PIPELINE_STATUS.EVALUATING || pipelineStatus === PIPELINE_STATUS.REVISING,
      isCompleted: ([PIPELINE_STATUS.AWAITING_HITL, PIPELINE_STATUS.EXPORTING, PIPELINE_STATUS.EXPORTED, PIPELINE_STATUS.REJECTED] as string[]).includes(pipelineStatus),
      isFailed: pipelineStatus === PIPELINE_STATUS.ERROR && !logs.some(l => l.type === 'agent_complete' && l.agent === 'critic') && ([PIPELINE_STATUS.EVALUATING, PIPELINE_STATUS.REVISING] as string[]).includes(pipelineStatus),
    },
    hitl: {
      label: 'HITL Decision Gate',
      desc: 'Halts execution for manager review, allowing approval or revision loop feedback.',
      isActive: pipelineStatus === PIPELINE_STATUS.AWAITING_HITL,
      isCompleted: ([PIPELINE_STATUS.EXPORTING, PIPELINE_STATUS.EXPORTED] as string[]).includes(pipelineStatus),
      isFailed: pipelineStatus === PIPELINE_STATUS.REJECTED,
    },
    export: {
      label: 'Finalize & Export',
      desc: 'Indexes the final plan in Pinecone and triggers Sheets + Jira integrations.',
      isActive: pipelineStatus === PIPELINE_STATUS.EXPORTING,
      isCompleted: pipelineStatus === PIPELINE_STATUS.EXPORTED,
      isFailed: pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED,
    }
  };

  const getStyleClasses = (nodeState: { isActive: boolean; isCompleted: boolean; isFailed: boolean }, shape: 'circle' | 'diamond' | 'rect' = 'circle') => {
    let base = "transition-all duration-300 border-2 flex items-center justify-center text-xs font-bold shadow-md cursor-help ";
    if (shape === 'circle') base += "rounded-full w-12 h-12 ";
    else if (shape === 'rect') base += "rounded-lg w-28 h-12 ";
    else base += "w-11 h-11 "; // Diamond handled via rotated divs

    if (nodeState.isCompleted) {
      return base + "bg-success border-success text-white shadow-success/20";
    }
    if (nodeState.isFailed) {
      return base + "bg-danger border-danger text-white shadow-danger/20";
    }
    if (nodeState.isActive) {
      return base + "bg-card border-primary text-primary ring-4 ring-primary/20 animate-pulse shadow-primary/20";
    }
    return base + "bg-card border-border text-muted-foreground";
  };

  const showRagLines = pipelineStatus === PIPELINE_STATUS.DRAFTING || pipelineStatus === PIPELINE_STATUS.ALIGNING;
  const isSyncing = pipelineStatus === PIPELINE_STATUS.EXPORTING || pipelineStatus === PIPELINE_STATUS.EXPORTED;

  // Condensed / Collapsed mode layout
  if (isCollapsed) {
    let summaryText = 'System Idle';
    let statusColor = 'text-muted-foreground';

    if (pipelineStatus === PIPELINE_STATUS.AWAITING_HITL) {
      summaryText = 'Awaiting Engineering Manager Decision';
      statusColor = 'text-warning font-extrabold animate-pulse';
    } else if (pipelineStatus === PIPELINE_STATUS.EXPORTING) {
      summaryText = 'Syncing to Jira & Sheets...';
      statusColor = 'text-primary font-bold';
    } else if (pipelineStatus === PIPELINE_STATUS.EXPORTED) {
      summaryText = 'Successfully Exported to Jira & Google Sheets';
      statusColor = 'text-success font-extrabold';
    } else if (pipelineStatus === PIPELINE_STATUS.REJECTED) {
      summaryText = 'Plan Rejected (Revision Loop Triggered)';
      statusColor = 'text-danger font-bold';
    } else if (pipelineStatus === PIPELINE_STATUS.ERROR) {
      summaryText = 'Pipeline Error Encountered';
      statusColor = 'text-danger font-bold';
    } else if (pipelineStatus !== PIPELINE_STATUS.IDLE) {
      summaryText = `Executing: ${pipelineStatus.replace(/_/g, ' ')}`;
      statusColor = 'text-primary font-bold';
    }

    return (
      <div className="w-full bg-card border border-border rounded-xl px-4 py-2.5 shadow-md flex items-center justify-between text-xs transition-all duration-300">
        <div className="flex items-center gap-3">
          <span className="flex h-2 w-2 relative">
            {pipelineStatus !== PIPELINE_STATUS.IDLE && pipelineStatus !== PIPELINE_STATUS.EXPORTED && pipelineStatus !== PIPELINE_STATUS.REJECTED && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${
              pipelineStatus === PIPELINE_STATUS.EXPORTED ? 'bg-success' :
              pipelineStatus === PIPELINE_STATUS.REJECTED || pipelineStatus === PIPELINE_STATUS.ERROR ? 'bg-danger' :
              pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ? 'bg-warning' : 'bg-primary'
            }`}></span>
          </span>
          <span className="font-semibold text-foreground">
            Workflow: <span className={statusColor}>{summaryText}</span>
          </span>
          {criticOutput && (
            <span className="hidden md:inline-block bg-[#f0f7ff] dark:bg-sky-950/20 text-sky-800 dark:text-sky-300 border border-sky-200 dark:border-sky-800/40 px-2 py-0.5 rounded text-[10px] font-mono">
              Critic Score: {criticOutput.overallScore.toFixed(1)}/5.0
            </span>
          )}
        </div>
        <button
          onClick={onToggleCollapse}
          className="flex items-center gap-1 text-[11px] font-bold text-primary hover:text-primary-hover px-2 py-1 rounded hover:bg-secondary/40 transition-colors"
        >
          Show Workflow Map <ChevronDown size={14} />
        </button>
      </div>
    );
  }

  // Extended Mode Layout
  return (
    <div className="w-full bg-card border border-border rounded-xl p-5 shadow-lg relative transition-all duration-300">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-extrabold text-primary uppercase tracking-wider">Agentic Workflow Progress</h3>
        <div className="flex items-center gap-2">
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="flex items-center gap-1 text-[11px] font-bold text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-secondary/40 transition-colors"
            >
              Minimize <ChevronUp size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Main Flowchart Outer Container (Scrollable viewport on smaller screens) */}
      <div className="w-full overflow-x-auto py-4">
        <div className="relative w-[960px] h-[280px] mx-auto select-none">
          
          {/* Background Connector Lines Canvas */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-0" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <marker id="arrow-success" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10B981" />
              </marker>
              <marker id="arrow-danger" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#EF4444" />
              </marker>
              <marker id="arrow-primary" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#6366F1" />
              </marker>
              <marker id="arrow-gray" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#94A3B8" />
              </marker>
            </defs>

            {/* 1. Security -> Orchestrator Line */}
            <path 
              d="M 125,140 L 292,140" 
              fill="none" 
              stroke={nodes.security.isCompleted ? "#10B981" : (nodes.orchestrator.isActive ? "#6366F1" : "#94A3B8")} 
              strokeWidth="2" 
              markerEnd={`url(#${nodes.security.isCompleted ? 'arrow-success' : (nodes.orchestrator.isActive ? 'arrow-primary' : 'arrow-gray')})`}
            />

            {/* 2. Orchestrator -> Satellite Specialists Spoke Lines */}
            {[
              { id: 'plan', x: 230, y: 50 },
              { id: 'schedule', x: 470, y: 50 },
              { id: 'poc', x: 230, y: 230 },
              { id: 'stack', x: 470, y: 230 },
              { id: 'arch', x: 350, y: 240 }
            ].map(spoke => {
              const specStatus = spoke.id === 'plan' ? getDetailedStatus('engineering_plan_generator') :
                                 spoke.id === 'schedule' ? getDetailedStatus('schedule_estimator') :
                                 spoke.id === 'poc' ? getDetailedStatus('poc_planner') :
                                 spoke.id === 'stack' ? getDetailedStatus('tech_stack_recommender') :
                                 getDetailedStatus('solution_architect');
              
              const isComp = specStatus === 'completed' || nodes.critic.isCompleted;
              const isActive = specStatus === 'running';
              const isFail = specStatus === 'failed';

              return (
                <line 
                  key={spoke.id}
                  x1="350" y1="140" 
                  x2={spoke.x} y2={spoke.y}
                  stroke={isComp ? "#10B981" : (isFail ? "#EF4444" : (isActive ? "#6366F1" : "#94A3B8"))}
                  strokeWidth="1.5"
                  strokeDasharray={isActive ? "4, 2" : "none"}
                  className={isActive ? "animate-[dash_1s_linear_infinite]" : ""}
                />
              );
            })}

            {/* 3. Orchestrator -> Critic Line */}
            <path 
              d="M 400,140 L 582,140" 
              fill="none" 
              stroke={nodes.orchestrator.isCompleted ? "#10B981" : (nodes.critic.isActive ? "#6366F1" : "#94A3B8")} 
              strokeWidth="2" 
              markerEnd={`url(#${nodes.orchestrator.isCompleted ? 'arrow-success' : (nodes.critic.isActive ? 'arrow-primary' : 'arrow-gray')})`}
            />

            {/* 4. Critic -> HITL Line */}
            <path 
              d="M 690,140 L 752,140" 
              fill="none" 
              stroke={nodes.critic.isCompleted ? "#10B981" : (nodes.hitl.isActive ? "#6366F1" : "#94A3B8")} 
              strokeWidth="2" 
              markerEnd={`url(#${nodes.critic.isCompleted ? 'arrow-success' : (nodes.hitl.isActive ? 'arrow-primary' : 'arrow-gray')})`}
            />

            {/* 5. HITL -> Export Line */}
            <path 
              d="M 820,140 L 862,140" 
              fill="none" 
              stroke={nodes.hitl.isCompleted ? "#10B981" : (nodes.hitl.isFailed ? "#EF4444" : (nodes.export.isActive ? "#6366F1" : "#94A3B8"))} 
              strokeWidth="2" 
              markerEnd={`url(#${nodes.hitl.isCompleted ? 'arrow-success' : (nodes.hitl.isFailed ? 'arrow-danger' : 'arrow-gray')})`}
            />

            {/* 6. Pinecone RAG dashed queries (Orange) */}
            {showRagLines && (
              <>
                <path d="M 350,25 L 230,50" stroke="#F59E0B" strokeWidth="1" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
                <path d="M 350,25 L 470,50" stroke="#F59E0B" strokeWidth="1" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
                <path d="M 350,25 L 230,230" stroke="#F59E0B" strokeWidth="1" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
                <path d="M 350,25 L 470,230" stroke="#F59E0B" strokeWidth="1" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
                <path d="M 350,25 L 350,240" stroke="#F59E0B" strokeWidth="1" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
              </>
            )}

            {/* 7. Tool syncing lines (Green) */}
            {isSyncing && (
              <>
                <path d="M 910,170 L 825,210" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
                <path d="M 910,170 L 865,210" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
                <path d="M 910,170 L 905,210" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
                <path d="M 910,170 L 945,210" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3, 3" className="animate-[dash_1.5s_linear_infinite]" />
              </>
            )}
          </svg>

          {/* SECURITY VALIDATOR */}
          <div 
            className="absolute left-[15px] top-[110px] w-[110px] h-[60px] flex items-center justify-center z-10"
            onMouseEnter={() => setActiveTooltip('security')}
            onMouseLeave={() => setActiveTooltip(null)}
          >
            <div className={getStyleClasses(nodes.security, 'rect')}>
              <Shield size={16} className="mr-1.5 shrink-0" />
              <div className="flex flex-col text-left">
                <span className="text-[10px] font-bold truncate leading-tight">Security</span>
                <span className="text-[8px] opacity-75 truncate leading-tight">PII & Prompt validation</span>
              </div>
            </div>
            {activeTooltip === 'security' && (
              <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                <p className="font-bold text-foreground mb-1">Security Validator</p>
                {nodes.security.desc}
              </div>
            )}
          </div>

          {/* ORCHESTRATOR HUB */}
          <div 
            className="absolute left-[300px] top-[105px] w-[100px] h-[70px] flex flex-col items-center justify-center z-20"
            onMouseEnter={() => setActiveTooltip('orchestrator')}
            onMouseLeave={() => setActiveTooltip(null)}
          >
            <div className={getStyleClasses(nodes.orchestrator, 'circle')}>
              {nodes.orchestrator.isActive ? (
                <Loader2 size={20} className="animate-spin" />
              ) : (
                <Cpu size={20} />
              )}
            </div>
            <span className={`text-[9px] font-extrabold mt-1 leading-none ${nodes.orchestrator.isActive ? 'text-primary' : 'text-muted-foreground'}`}>
              Orchestrator
            </span>
            {activeTooltip === 'orchestrator' && (
              <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                <p className="font-bold text-foreground mb-1">Orchestrator Agent</p>
                {nodes.orchestrator.desc}
              </div>
            )}
          </div>

          {/* RAG VECTOR DATABASE (Top Center) */}
          <div 
            className="absolute left-[335px] top-[5px] w-[30px] h-[30px] flex items-center justify-center z-10 cursor-help"
            onMouseEnter={() => setActiveTooltip('rag')}
            onMouseLeave={() => setActiveTooltip(null)}
          >
            <div className={`p-1.5 rounded bg-amber-500/10 border border-amber-500/40 text-amber-500 transition-colors ${showRagLines ? 'ring-2 ring-amber-500/30' : ''}`}>
              <BookOpen size={16} />
            </div>
            {activeTooltip === 'rag' && (
              <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                <p className="font-bold text-foreground mb-1">RAG (Pinecone DB)</p>
                Grounds plans dynamically in company engineering standards and approved frameworks.
              </div>
            )}
          </div>

          {/* SATELLITE SPECIALISTS */}
          {[
            { id: 'plan', key: 'engineering_plan_generator', label: 'Plan', left: '180px', top: '30px' },
            { id: 'schedule', key: 'schedule_estimator', label: 'Schedule', left: '420px', top: '30px' },
            { id: 'poc', key: 'poc_planner', label: 'PoC', left: '180px', top: '210px' },
            { id: 'stack', key: 'tech_stack_recommender', label: 'Tech Stack', left: '420px', top: '210px' },
            { id: 'arch', key: 'solution_architect', label: 'Architect', left: '300px', top: '220px' }
          ].map(spec => {
            const specStatus = getDetailedStatus(spec.key);
            const isComp = specStatus === 'completed' || nodes.critic.isCompleted;
            const isActive = specStatus === 'running';
            const isFail = specStatus === 'failed';

            let nodeClass = "px-2 py-1 rounded-full border text-[9px] font-bold shadow-sm transition-all duration-300 w-[100px] h-[34px] flex items-center justify-center ";
            if (isComp) nodeClass += "bg-success/15 border-success/35 text-success shadow-success/5";
            else if (isFail) nodeClass += "bg-danger/15 border-danger/35 text-danger shadow-danger/5";
            else if (isActive) nodeClass += "bg-primary/15 border-primary text-primary animate-pulse ring-2 ring-primary/20";
            else nodeClass += "bg-card border-border text-muted-foreground/80";

            return (
              <div 
                key={spec.id} 
                className="absolute flex flex-col items-center justify-center z-10 cursor-help"
                style={{ left: spec.left, top: spec.top }}
                onMouseEnter={() => setActiveTooltip(spec.id)}
                onMouseLeave={() => setActiveTooltip(null)}
              >
                <div className={nodeClass}>
                  <Sparkles size={11} className={`mr-1 shrink-0 ${isActive ? 'text-primary' : (isComp ? 'text-success' : 'text-muted-foreground')}`} />
                  <span className="truncate">{spec.label}</span>
                </div>
                {activeTooltip === spec.id && (
                  <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                    <p className="font-bold text-foreground mb-1">{spec.label} Specialist</p>
                    Autonomous drafting agent producing technical {spec.label.toLowerCase()} layouts.
                  </div>
                )}
              </div>
            );
          })}

          {/* REVISION LOOP INDICATOR (Middle connector line area) */}
          <div className="absolute left-[475px] top-[102px] w-[50px] h-[50px] flex items-center justify-center z-20">
            {pipelineStatus === PIPELINE_STATUS.REVISING ? (
              <div className="flex flex-col items-center gap-0.5 animate-pulse bg-warning/10 border border-warning/30 rounded px-1.5 py-0.5 text-[8px] font-mono text-warning font-bold">
                <Loader2 size={10} className="animate-spin text-warning" />
                <span>Looping</span>
              </div>
            ) : logs.filter(l => l.type === 'revision_start').length > 0 ? (
              <div className="bg-primary/10 border border-primary/20 rounded px-1.5 py-0.5 text-[8px] font-mono text-primary font-bold">
                Rev {logs.filter(l => l.type === 'revision_start').length}
              </div>
            ) : null}
          </div>

          {/* CRITIC EVALUATION NODE */}
          <div 
            className="absolute left-[580px] top-[105px] w-[100px] h-[70px] flex flex-col items-center justify-center z-20"
            onMouseEnter={() => setActiveTooltip('critic')}
            onMouseLeave={() => setActiveTooltip(null)}
          >
            <div className={getStyleClasses(nodes.critic, 'circle')}>
              {nodes.critic.isActive ? (
                <Loader2 size={20} className="animate-spin" />
              ) : (
                <GitPullRequest size={18} />
              )}
            </div>
            <span className={`text-[9px] font-extrabold mt-1 leading-none ${nodes.critic.isActive ? 'text-primary' : 'text-muted-foreground'}`}>
              Critic Agent
            </span>
            {activeTooltip === 'critic' && (
              <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                <p className="font-bold text-foreground mb-1">Critic Agent</p>
                {nodes.critic.desc}
              </div>
            )}
          </div>

          {/* HITL DECISION DIAMOND */}
          <div 
            className="absolute left-[745px] top-[105px] w-[70px] h-[70px] flex flex-col items-center justify-center z-20"
            onMouseEnter={() => setActiveTooltip('hitl')}
            onMouseLeave={() => setActiveTooltip(null)}
          >
            <div className="relative w-12 h-12 flex items-center justify-center">
              {/* Rotated outer shell */}
              <div className={`absolute inset-0 rotate-45 border-2 rounded transition-all duration-300 ${
                nodes.hitl.isCompleted ? 'bg-success border-success text-white shadow-success/15' :
                nodes.hitl.isFailed ? 'bg-danger border-danger text-white shadow-danger/15' :
                nodes.hitl.isActive ? 'bg-card border-warning ring-4 ring-warning/20 animate-pulse text-warning' :
                'bg-card border-border text-muted-foreground'
              }`} />
              {/* Unrotated core content */}
              <div className={`relative z-10 flex items-center justify-center ${
                nodes.hitl.isCompleted || nodes.hitl.isFailed ? 'text-white' : (nodes.hitl.isActive ? 'text-warning' : 'text-muted-foreground')
              }`}>
                {nodes.hitl.isCompleted ? <Check size={18} className="stroke-[3px]" /> :
                 nodes.hitl.isFailed ? <X size={18} className="stroke-[3px]" /> :
                 <UserCheck size={18} />}
              </div>
            </div>
            <span className={`text-[9px] font-extrabold mt-1.5 leading-none ${nodes.hitl.isActive ? 'text-warning' : 'text-muted-foreground'}`}>
              EM Decision
            </span>
            {activeTooltip === 'hitl' && (
              <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                <p className="font-bold text-foreground mb-1">Manager Decision Gate (HITL)</p>
                {nodes.hitl.desc}
              </div>
            )}
          </div>

          {/* EXPORTS TERMINAL NODE */}
          <div 
            className="absolute left-[850px] top-[110px] w-[100px] h-[60px] flex items-center justify-center z-10"
            onMouseEnter={() => setActiveTooltip('export')}
            onMouseLeave={() => setActiveTooltip(null)}
          >
            <div className={getStyleClasses(nodes.export, 'rect')}>
              <Wrench size={15} className="mr-1.5 shrink-0" />
              <div className="flex flex-col text-left">
                <span className="text-[10px] font-bold truncate leading-tight">Export</span>
                <span className="text-[8px] opacity-75 truncate leading-tight">
                  {pipelineStatus === PIPELINE_STATUS.EXPORTED ? 'Completed' : 'Sync outputs'}
                </span>
              </div>
            </div>
            {activeTooltip === 'export' && (
              <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                <p className="font-bold text-foreground mb-1">Finalize & Export Node</p>
                {nodes.export.desc}
              </div>
            )}
          </div>

          {/* TOOL LAYER DESTINATIONS (Bottom Right) */}
          {[
            { id: 'sheet', icon: <FileText size={14} />, left: '810px', top: '210px', label: 'Sheets', color: 'text-success border-success/40 bg-success/10' },
            { id: 'jira', icon: <Cpu size={14} />, left: '850px', top: '210px', label: 'Jira', color: 'text-sky-500 border-sky-500/40 bg-sky-500/10' },
            { id: 'slack', icon: <MessageSquare size={14} />, left: '890px', top: '210px', label: 'Slack', color: 'text-indigo-500 border-indigo-500/40 bg-indigo-500/10' },
            { id: 'db', icon: <Database size={14} />, left: '930px', top: '210px', label: 'Redis', color: 'text-purple-500 border-purple-500/40 bg-purple-500/10' }
          ].map(tool => {
            const active = pipelineStatus === PIPELINE_STATUS.EXPORTING;
            const complete = pipelineStatus === PIPELINE_STATUS.EXPORTED;

            let cardClass = `p-1.5 rounded border transition-all duration-300 cursor-help ${tool.color} `;
            if (complete) cardClass += "ring-2 ring-success/30 border-success shadow-success/10 bg-success/20";
            else if (active) cardClass += "animate-pulse ring-2 ring-primary/20";
            else cardClass += "grayscale-[40%] opacity-60";

            return (
              <div 
                key={tool.id} 
                className="absolute flex items-center justify-center z-10"
                style={{ left: tool.left, top: tool.top }}
                onMouseEnter={() => setActiveTooltip(tool.id)}
                onMouseLeave={() => setActiveTooltip(null)}
              >
                <div className={cardClass}>
                  {tool.icon}
                </div>
                {activeTooltip === tool.id && (
                  <div className="absolute z-40 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-background border border-border rounded-lg shadow-xl text-[10px] text-muted-foreground leading-normal">
                    <p className="font-bold text-foreground mb-1">{tool.label} Integration</p>
                    Pushes plan deliverables to organization-wide {tool.label} tools on HITL gate approval.
                  </div>
                )}
              </div>
            );
          })}

        </div>
      </div>
    </div>
  );
};
