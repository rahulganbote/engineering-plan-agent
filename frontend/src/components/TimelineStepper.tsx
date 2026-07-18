import React, { useState } from 'react';
import {
  Shield, Cpu, UserCheck, Check, Loader2, X,
  Wrench, GitPullRequest,
  ChevronDown, ChevronUp, Upload, Database
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
  title?: string;
}

export const TimelineStepper: React.FC<TimelineStepperProps> = ({
  pipelineStatus,
  completedAgents,
  artifacts: _artifacts,
  // Retained on props for API compatibility with AgentWorkspace; no longer rendered
  // in-banner after the Critic Score pill was replaced with the Scroll-to-Decision-Gate button.
  criticOutput: _criticOutput,
  logs,
  isCollapsed = false,
  onToggleCollapse,
  title,
}) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [tooltipState, setTooltipState] = useState<{
    id: string;
    x: number;
    y: number;
    title: string;
    desc: string;
  } | null>(null);

  const handleMouseEnter = (nodeId: string, title: string, desc: string, event: React.MouseEvent) => {
    if (!containerRef.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current.getBoundingClientRect();
    setTooltipState({
      id: nodeId,
      x: rect.left - containerRect.left + rect.width / 2,
      y: rect.top - containerRect.top - 8,
      title,
      desc
    });
  };

  const handleMouseLeave = () => {
    setTooltipState(null);
  };

  const getTooltipPosition = () => {
    if (!tooltipState || !containerRef.current) return { left: 0, top: 0 };
    const tooltipWidth = 256;
    const containerWidth = containerRef.current.getBoundingClientRect().width;
    const leftX = Math.max(
      12 + tooltipWidth / 2,
      Math.min(tooltipState.x, containerWidth - tooltipWidth / 2 - 12)
    );
    return {
      left: `${leftX}px`,
      top: `${tooltipState.y}px`
    };
  };

  const getDetailedStatus = (agentKey: string): 'pending' | 'running' | 'completed' | 'failed' => {
    if (pipelineStatus === PIPELINE_STATUS.IDLE) return 'pending';

    // Include all parallel compilation processing states
    const IS_PARALLEL_PHASE = [
      PIPELINE_STATUS.DRAFTING,
      PIPELINE_STATUS.ALIGNING,
      PIPELINE_STATUS.ARBITRATING,
      PIPELINE_STATUS.RUNNING
    ].includes(pipelineStatus as any);

    if (IS_PARALLEL_PHASE) {
      if (completedAgents.has(agentKey)) return 'completed';

      // Check if any failures occurred
      const hasFailed = logs.some(l => l.type === 'agent_failed' && (l.agent === agentKey || l.payload?.agent === agentKey));
      if (hasFailed) return 'failed';

      // Default to running during parallel steps so all 5 agents light up together
      return 'running';
    }

    // Post-parallel states — specialists have finished by the time we hit these.
    const PAST_PARALLEL: string[] = [
      PIPELINE_STATUS.EVALUATING,
      PIPELINE_STATUS.REVISING,
      PIPELINE_STATUS.AWAITING_HITL,
      PIPELINE_STATUS.EXPORTING,
      PIPELINE_STATUS.EXPORTED,
      PIPELINE_STATUS.REJECTED,
      PIPELINE_STATUS.EXPORT_FAILED,
    ];
    if (PAST_PARALLEL.includes(pipelineStatus)) return 'completed';

    // Pre-parallel states (INITIALIZING, STARTED, SECURITY_CHECK, ORCHESTRATOR_PARSING,
    // CANCELED, ERROR): specialists haven't started yet — do NOT mark them completed.
    return 'pending';
  };

  const nodes = {
    upload: {
      label: 'BRD Ingestion',
      desc: 'Ingests PDF, DOCX, or TXT Business Requirements Documents to initiate the planning pipeline.',
      // Active only while the file is actually being ingested (post-click transient states).
      // IDLE = user hasn't started yet, so BRD Ingestion is neither active nor complete.
      isActive: pipelineStatus === PIPELINE_STATUS.INITIALIZING || pipelineStatus === PIPELINE_STATUS.STARTED,
      isCompleted: pipelineStatus !== PIPELINE_STATUS.IDLE
        && pipelineStatus !== PIPELINE_STATUS.INITIALIZING
        && pipelineStatus !== PIPELINE_STATUS.STARTED,
      isFailed: false,
    },
    security: {
      label: 'Security Validator',
      desc: 'Performs file size check, BRD validity check, prompt injection assessment, and filters/redacts PII patterns.',
      // Only active during SECURITY_CHECK — BRD Ingestion owns INITIALIZING/STARTED now.
      isActive: pipelineStatus === PIPELINE_STATUS.SECURITY_CHECK,
      isCompleted: pipelineStatus !== PIPELINE_STATUS.IDLE
        && pipelineStatus !== PIPELINE_STATUS.INITIALIZING
        && pipelineStatus !== PIPELINE_STATUS.STARTED
        && pipelineStatus !== PIPELINE_STATUS.SECURITY_CHECK,
      isFailed: pipelineStatus === PIPELINE_STATUS.ERROR && !logs.some(l => l.type === 'security_complete'),
    },
    orchestrator: {
      label: 'Orchestrator Agent',
      desc: 'Parses the BRD sections, evaluates structure completeness, and distributes tasks to 5 specialists Agents.',
      isActive: pipelineStatus === PIPELINE_STATUS.RUNNING || pipelineStatus === PIPELINE_STATUS.ORCHESTRATOR_PARSING || pipelineStatus === PIPELINE_STATUS.ARBITRATING,
      isCompleted: ([PIPELINE_STATUS.DRAFTING, PIPELINE_STATUS.ALIGNING, PIPELINE_STATUS.EVALUATING, PIPELINE_STATUS.REVISING, PIPELINE_STATUS.AWAITING_HITL, PIPELINE_STATUS.EXPORTING, PIPELINE_STATUS.EXPORTED, PIPELINE_STATUS.REJECTED] as string[]).includes(pipelineStatus),
      isFailed: pipelineStatus === PIPELINE_STATUS.ERROR && !logs.some(l => l.type === 'agent_complete' && l.agent === 'orchestrator'),
    },
    critic: {
      label: 'Critic Agent (Evaluation)',
      desc: 'Five-method evaluation suite (BERTScore F1 >= 0.85). Grades outputs on 4 quality dimensions (1.0-5.0 score) and triggers revisions if needed. Green badge requires all dimensions passing, overall >= 4.0, and zero unresolved warnings (otherwise capped at Amber).',
      isActive: pipelineStatus === PIPELINE_STATUS.EVALUATING || pipelineStatus === PIPELINE_STATUS.REVISING,
      isCompleted: ([PIPELINE_STATUS.AWAITING_HITL, PIPELINE_STATUS.EXPORTING, PIPELINE_STATUS.EXPORTED, PIPELINE_STATUS.REJECTED] as string[]).includes(pipelineStatus),
      isFailed: pipelineStatus === PIPELINE_STATUS.ERROR && !logs.some(l => l.type === 'agent_complete' && l.agent === 'critic') && ([PIPELINE_STATUS.EVALUATING, PIPELINE_STATUS.REVISING] as string[]).includes(pipelineStatus),
    },
    hitl: {
      label: 'Manager (HITL) Decision Gate',
      desc: 'Pauses execution to obtain engineering manager approval before exporting to Google Sheets and Jira. Voice AI support (ElevenLabs) at Decision Gate.',
      isActive: pipelineStatus === PIPELINE_STATUS.AWAITING_HITL,
      isCompleted: ([PIPELINE_STATUS.EXPORTING, PIPELINE_STATUS.EXPORTED] as string[]).includes(pipelineStatus),
      isFailed: pipelineStatus === PIPELINE_STATUS.REJECTED,
    },
    export: {
      label: 'Finalize & Export Node',
      desc: 'Indexes the final plan in Pinecone and triggers Sheets + Jira integrations.',
      isActive: pipelineStatus === PIPELINE_STATUS.EXPORTING,
      isCompleted: pipelineStatus === PIPELINE_STATUS.EXPORTED,
      isFailed: pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED,
    }
  };

  const getStyleClasses = (nodeState: { isActive: boolean; isCompleted: boolean; isFailed: boolean }, shape: 'circle' | 'diamond' | 'rect' = 'circle') => { 
    let base = "transition-all duration-300 border-2 flex items-center justify-center text-xs font-bold shadow-md cursor-help "; 
    if (shape === 'circle') base += "rounded-full w-12 h-12 "; 
    else if (shape === 'rect') base += "rounded-full w-32 h-12 "; 
    else base += "w-11 h-11 "; 
    if (nodeState.isCompleted) { return base + "bg-success border-success text-white shadow-success/20"; } 
    if (nodeState.isFailed) { return base + "bg-danger border-danger text-white shadow-danger/20"; } 
    if (nodeState.isActive) { 
      // animate-pulse dips element opacity to 0.5 which revealed the SVG connector
      // lines behind the pill body — visual bug. The Loader2 spinner inside the pill
      // already signals "in progress"; the ring + indigo border + shadow do the rest. 
      return base + "bg-card border-primary text-primary ring-4 ring-primary/20 shadow-primary/20"; 
    } 
    return base + "bg-card border-border text-muted-foreground"; 
  }; 

  const showRagLines = pipelineStatus === PIPELINE_STATUS.DRAFTING || pipelineStatus === PIPELINE_STATUS.ALIGNING; 
  const isSyncing = pipelineStatus === PIPELINE_STATUS.EXPORTING || pipelineStatus === PIPELINE_STATUS.EXPORTED; 

  if (isCollapsed) { 
    let summaryText = 'System Idle'; 
    let statusColor = 'text-muted-foreground'; 
    if (pipelineStatus === PIPELINE_STATUS.AWAITING_HITL) { 
      summaryText = 'Awaiting your Decision'; 
      statusColor = 'text-warning-strong font-semibold animate-pulse'; 
    } else if (pipelineStatus === PIPELINE_STATUS.EXPORTING) { 
      summaryText = 'Syncing to Jira...'; 
      statusColor = 'text-primary font-bold'; 
    } else if (pipelineStatus === PIPELINE_STATUS.EXPORTED) { 
      summaryText = 'Successfully Exported to Jira'; 
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
          
          {/* Core Text Label Block */}
          <span className="text-xs font-black text-primary uppercase tracking-wider inline-flex items-center gap-2"> 
            Workflow: <span className={statusColor}>{summaryText}</span> 
            
            {/* Anchored Pulsing Dot - Now paired natively right next to the active status label */}
            {pipelineStatus !== PIPELINE_STATUS.IDLE && pipelineStatus !== PIPELINE_STATUS.EXPORTED && pipelineStatus !== PIPELINE_STATUS.REJECTED && ( 
              <span className="flex h-2 w-2 relative shrink-0"> 
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span> 
                <span className={`relative inline-flex rounded-full h-2 w-2 ${ 
                  pipelineStatus === PIPELINE_STATUS.ERROR ? 'bg-danger' : 
                  pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ? 'bg-warning' : 'bg-primary' 
                }`}></span>  
              </span> 
            )}
          </span> 

          {/* Core Layout Execution Button */}
          {pipelineStatus === PIPELINE_STATUS.AWAITING_HITL && ( 
            <button 
              type="button" 
              onClick={(e) => { 
                e.preventDefault(); 
                const el = document.getElementById('decision-gate'); 
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); 
              }} 
              className="px-2.5 py-1 bg-primary hover:bg-primary/90 text-primary-foreground text-[11px] font-semibold rounded transition shadow-sm hover:shadow-md shrink-0 cursor-pointer" 
            > 
              Scroll to Decision Gate 
            </button> 
          )} 
        </div> 

        {/* Since this whole parent block only mounts when isCollapsed is true, the string remains static */}
        <button 
          onClick={onToggleCollapse} 
          className="flex items-center gap-1 text-[11px] font-bold text-primary hover:text-primary-hover px-2 py-1 rounded hover:bg-secondary/40 transition-colors cursor-pointer" 
        > 
          <span>Show Workflow Map</span> 
          <ChevronDown size={14} /> 
        </button> 
      </div> 
    ); 
  }


  return (
    <div
      ref={containerRef}
      className="w-full bg-card border border-border rounded-xl p-4 shadow-lg relative transition-all duration-300 select-none"
    >
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xs font-black text-primary uppercase tracking-wider">{title || "Agentic Workflow Progress"}</h3>
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

      <div className="w-full">
        <svg
          viewBox="0 15 920 375"
          width="100%"
          height="auto"
          className="w-full h-auto max-w-full z-10 block"
          xmlns="http://www.w3.org/2000/svg"
        >
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
            <marker id="arrow-orange" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#F59E0B" />
            </marker>
          </defs>

          {/* 1. Ingestion -> Security Line */}
          <path
            d="M 131,125 L 152,125"
            fill="none"
            stroke={nodes.upload.isCompleted ? "#10B981" : (nodes.upload.isActive ? "#6366F1" : "#94A3B8")}
            strokeWidth="2"
            markerEnd={`url(#${nodes.upload.isCompleted ? 'arrow-success' : (nodes.upload.isActive ? 'arrow-primary' : 'arrow-gray')})`}
          />

          {/* 2. Security -> Orchestrator Line */}
          <path
            d="M 283,125 L 297,125"
            fill="none"
            stroke={nodes.security.isCompleted ? "#10B981" : (nodes.orchestrator.isActive ? "#6366F1" : "#94A3B8")}
            strokeWidth="2"
            markerEnd={`url(#${nodes.security.isCompleted ? 'arrow-success' : (nodes.orchestrator.isActive ? 'arrow-primary' : 'arrow-gray')})`}
          />

          {/* 3. Orchestrator -> Satellite Specialists Spoke Lines */}
          {[
            { id: 'plan', x: 275, y: 55 },
            { id: 'schedule', x: 450, y: 53 },
            { id: 'poc', x: 250, y: 195 },
            { id: 'stack', x: 485, y: 195 },
            { id: 'arch', x: 365, y: 55 }
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
                x1="365" y1="125"
                x2={spoke.x} y2={spoke.y}
                stroke={isComp ? "#10B981" : (isFail ? "#EF4444" : (isActive ? "#6366F1" : "#94A3B8"))}
                strokeWidth="1.5"
                strokeDasharray={isActive ? "4, 2" : "none"}
                className={isActive ? "animate-[dash_1s_linear_infinite]" : ""}
                markerEnd={`url(#${isComp ? 'arrow-success' : (isFail ? 'arrow-danger' : (isActive ? 'arrow-primary' : 'arrow-gray'))})`}
              />
            );
          })}

          {/* 4. Orchestrator -> Critic Line */}
          <path
            d="M 431,125 L 551,125"
            fill="none"
            stroke={nodes.orchestrator.isCompleted ? "#10B981" : (nodes.critic.isActive ? "#6366F1" : "#94A3B8")}
            strokeWidth="2"
            markerEnd={`url(#${nodes.orchestrator.isCompleted ? 'arrow-success' : (nodes.critic.isActive ? 'arrow-primary' : 'arrow-gray')})`}
          />

          {/* 5. Critic -> HITL Line */}
          <path
            d="M 684,125 L 708,125"
            fill="none"
            stroke={nodes.critic.isCompleted ? "#10B981" : (nodes.hitl.isActive ? "#6366F1" : "#94A3B8")}
            strokeWidth="2"
            markerEnd={`url(#${nodes.critic.isCompleted ? 'arrow-success' : (nodes.hitl.isActive ? 'arrow-primary' : 'arrow-gray')})`}
          />

          {/* 6. HITL -> Export Line */}
          <path
            d="M 768,125 L 791,125"
            fill="none"
            stroke={nodes.hitl.isCompleted ? "#10B981" : (nodes.hitl.isFailed ? "#EF4444" : (nodes.export.isActive ? "#6366F1" : "#94A3B8"))}
            strokeWidth="2"
            markerEnd={`url(#${nodes.hitl.isCompleted ? 'arrow-success' : (nodes.hitl.isFailed ? 'arrow-danger' : 'arrow-gray')})`}
          />

          {/* 7. Central One-way RAG connection */}
          {(() => {
            const isRagUsed = pipelineStatus !== PIPELINE_STATUS.IDLE && 
              pipelineStatus !== PIPELINE_STATUS.SECURITY_CHECK && 
              pipelineStatus !== PIPELINE_STATUS.INITIALIZING && 
              pipelineStatus !== PIPELINE_STATUS.STARTED && 
              pipelineStatus !== PIPELINE_STATUS.RUNNING && 
              pipelineStatus !== PIPELINE_STATUS.ORCHESTRATOR_PARSING;
            return (
              <path
                d="M 350,154 L 270,306"
                stroke={isRagUsed ? "#10B981" : "#94A3B8"}
                strokeWidth="2.5"
                fill="none"
                markerEnd={`url(#${isRagUsed ? 'arrow-success' : 'arrow-gray'})`}
              />
            );
          })()}

          {/* 8. Critic-to-RAG Citation Verification Line */}
          <path
            d="M 620,150 L 620,280 L 315,280 L 315,306"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="1.5"
            strokeDasharray="3, 3"
            className={pipelineStatus === PIPELINE_STATUS.EVALUATING || pipelineStatus === PIPELINE_STATUS.REVISING ? "animate-[dash_1.5s_linear_infinite]" : ""}
            markerEnd="url(#arrow-gray)"
          />

          {/* 9. Orchestrator-to-Agent-Tools connection */}
          <path
            d="M 395,150 L 395,306"
            stroke="#94A3B8"
            strokeWidth="1.5"
            strokeDasharray="3, 3"
            fill="none"
            className={nodes.orchestrator.isActive ? "animate-[dash_1.5s_linear_infinite]" : ""}
            markerEnd="url(#arrow-gray)"
          />

          {/* 10. Export to Tool syncing line */}
          <path
            d="M 855,150 L 855,306"
            stroke={isSyncing ? "#10B981" : "#94A3B8"}
            strokeWidth="1.5"
            strokeDasharray="3, 3"
            fill="none"
            className={pipelineStatus === PIPELINE_STATUS.EXPORTING ? "animate-[dash_1.5s_linear_infinite]" : ""}
            markerEnd={`url(#${isSyncing ? 'arrow-success' : 'arrow-gray'})`}
          />

          {/* BRD INGESTION UPLOAD */}
          <foreignObject x="1" y="96" width="130" height="58">
            <div
              className="w-full h-full flex items-center justify-center relative"
              onMouseEnter={(e) => handleMouseEnter('upload', nodes.upload.label, nodes.upload.desc, e)}
              onMouseLeave={handleMouseLeave}
            >
              <div className={getStyleClasses(nodes.upload, 'rect')}>
                <Upload size={16} className="mr-2 shrink-0" />
                <div className="flex flex-col text-left">
                  <span className="text-[10px] md:text-[11px] font-bold leading-tight">BRD Ingestion</span>
                  <span className="text-[8.5px] opacity-75 leading-tight">Upload</span>
                </div>
              </div>
            </div>
          </foreignObject>

          {/* SECURITY VALIDATOR */}
          <foreignObject x="153" y="96" width="130" height="58">
            <div
              className="w-full h-full flex items-center justify-center relative"
              onMouseEnter={(e) => handleMouseEnter('security', nodes.security.label, nodes.security.desc, e)}
              onMouseLeave={handleMouseLeave}
            >
              <div className={getStyleClasses(nodes.security, 'rect')}>
                <Shield size={16} className="mr-2 shrink-0" />
                <div className="flex flex-col text-left">
                  <span className="text-[10px] md:text-[11px] font-bold leading-tight">Security</span>
                  <span className="text-[8.5px] leading-tight">Validator</span>
                </div>
              </div>
            </div>
          </foreignObject>

          {/* ORCHESTRATOR HUB */}
          <foreignObject x="300" y="96" width="130" height="58">
            <div
              className="w-full h-full flex flex-col items-center justify-center relative"
              onMouseEnter={(e) => handleMouseEnter('orchestrator', nodes.orchestrator.label, nodes.orchestrator.desc, e)}
              onMouseLeave={handleMouseLeave}
            >
              <div className={getStyleClasses(nodes.orchestrator, 'rect')}>
                {nodes.orchestrator.isActive ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : nodes.orchestrator.isCompleted ? (
                  <Check size={16} className="mr-2 stroke-[3px]" />
                ) : (
                  <Cpu size={16} className="mr-2" />
                )}
                <div className="flex flex-col text-left">
                  <span className="text-[10px] md:text-[11px] font-bold leading-tight">Orchestrator</span>
                  <span className="text-[8.5px] leading-tight">Agent (Hub)</span>
                </div>
              </div>
            </div>
          </foreignObject>

          {/* RAG VECTOR DB */}
          <foreignObject x="170" y="310" width="170" height="70">
            {(() => {
              const isRagActive = showRagLines;
              let ragBoxClass = "w-full h-full rounded-xl border p-1.5 px-2 pb-3 text-left cursor-help transition-all duration-200 bg-slate-50/95 dark:bg-slate-900/90 relative flex flex-col justify-between shadow-sm ";
              if (isRagActive) {
                ragBoxClass += "border-primary animate-pulse shadow-primary/10 ring-2 ring-primary/10";
              } else {
                ragBoxClass += "border-border hover:border-primary/40";
              }

              return (
                <div
                  className={ragBoxClass}
                  onMouseEnter={(e) => handleMouseEnter('rag', 'RAG (Vector DB)', 'Grounds plans dynamically in company engineering standards and approved frameworks.', e)}
                  onMouseLeave={handleMouseLeave}
                >
                  <div className="flex items-center justify-between border-b border-primary/15 pb-0.5 mb-0.5">
                    <div className="flex items-center gap-1 text-primary">
                      <Database size={13} className="shrink-0" />
                      <span className="text-[9px] font-extrabold uppercase tracking-wide">RAG (Pinecone)</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-1 text-[8px] text-muted-foreground leading-snug">
                    <div className="hover:text-primary transition-colors">
                      <span className="font-extrabold text-ai-spark block mb-0.5 text-[7px] uppercase">Storage</span>
                      <span>🌲 Pinecone Index</span>
                      <span className="block">📚 Engineering Guidelines</span>
                    </div>
                  </div>
                </div>
              );
            })()}
          </foreignObject>

          {/* SATELLITE SPECIALISTS */}
          {[
            { id: 'plan', key: 'engineering_plan_generator', label: 'Plan Agent', emoji: '📝', x: 180, y: 15 },
            { id: 'schedule', key: 'schedule_estimator', label: 'Schedule Agent', emoji: '📊', x: 445, y: 15 },
            { id: 'poc', key: 'poc_planner', label: 'PoC Agent', emoji: '⏱️', x: 145, y: 195 },
            { id: 'stack', key: 'tech_stack_recommender', label: 'Tech Stack Agent', emoji: '💻', x: 475, y: 195 },
            { id: 'arch', key: 'solution_architect', label: 'Architect Agent', emoji: '🏗️', x: 300, y: 15, w: 130 }
          ].map(spec => {
            const specStatus = getDetailedStatus(spec.key);
            // Redundant `|| nodes.critic.isCompleted` fallback removed — getDetailedStatus
            // now correctly returns 'completed' for all post-parallel states.
            const isComp = specStatus === 'completed';
            const isActive = specStatus === 'running';
            const isFail = specStatus === 'failed';
            const width = spec.w || 110;

            let nodeClass = "px-2.5 py-1 rounded-full border shadow-sm transition-all duration-300 w-full h-[38px] flex items-center justify-center gap-1.5 ";
            if (isComp) nodeClass += "bg-success/15 border-success/35 text-success shadow-success/5";
            else if (isFail) nodeClass += "bg-danger/15 border-danger/35 text-danger shadow-danger/5";
            else if (isActive) nodeClass += "bg-primary/15 border-primary text-primary animate-pulse ring-2 ring-primary/20";
            else nodeClass += "bg-card border-border text-muted-foreground/80";

            return (
              <foreignObject key={spec.id} x={spec.x} y={spec.y} width={width} height="38">
                <div
                  className="w-full h-full flex flex-col items-center justify-center relative cursor-pointer"
                  onMouseEnter={(e) => handleMouseEnter(spec.id, `${spec.label} Agent`, `Autonomous specialist agent producing technical ${spec.label.toLowerCase()} artifacts.`, e)}
                  onMouseLeave={handleMouseLeave}
                >
                  <div className={nodeClass}>
                    {isActive ? (
                      <Loader2 size={11} className="animate-spin shrink-0 text-primary" />
                    ) : isComp ? (
                      <Check size={11} className="shrink-0 stroke-[3px] text-success" />
                    ) : (
                      <span className="text-[11px] select-none shrink-0">{spec.emoji}</span>
                    )}
                    <div className="flex flex-col items-start leading-tight">
                      <span className="text-[10px] font-bold truncate">{spec.label}</span>
                      <span className="text-[8px] tracking-wider">Specialist</span>
                    </div>
                  </div>
                </div>
              </foreignObject>
            );
          })}

          {/* REVISION LOOP GAP */}
          <foreignObject x="480" y="105" width="40" height="40">
            <div
              className="w-full h-full flex items-center justify-center cursor-help"
              onMouseEnter={(e) => handleMouseEnter('loop', 'Revision & Alignment Loop', 'Cycles until quality gates pass.', e)}
              onMouseLeave={handleMouseLeave}
            >
              {(() => {
                const isRevising = pipelineStatus === PIPELINE_STATUS.REVISING;
                const revisionCount = logs.filter(l => l.type === 'revision_start').length;

                if (isRevising) {
                  return (
                    <div className="w-8 h-8 rounded-full border border-warning/40 bg-warning/5 flex items-center justify-center shadow-sm text-warning">
                      {/* The spinner character is now safely isolated to active states */}
                      <span className="text-[12px] animate-spin">🔄</span>
                    </div>
                  );
                }
                if (revisionCount > 0) {
                  // bg-card (opaque) prevents the SVG connector line from bleeding
                  // through the badge; primary color signal stays via border + text.
                  return (
                    <div className="w-8 h-8 rounded-full border border-primary/40 bg-card flex items-center justify-center shadow-sm text-primary text-[8.5px] font-extrabold font-mono">
                      R{revisionCount}
                    </div>
                  );
                }
                return (
                  <div className="w-8 h-8 rounded-full border border-border bg-card flex items-center justify-center shadow-sm text-muted-foreground select-none hover:border-primary/40 transition-colors">
                    <span className="text-[12px]">🔄</span>
                  </div>
                );
              })()}
            </div>
          </foreignObject>

          {/* CRITIC EVALUATION NODE */}
          <foreignObject x="555" y="96" width="130" height="58">
            <div
              className="w-full h-full flex flex-col items-center justify-center relative cursor-help"
              onMouseEnter={(e) => handleMouseEnter('critic', nodes.critic.label, nodes.critic.desc, e)}
              onMouseLeave={handleMouseLeave}
            >
              <div className={getStyleClasses(nodes.critic, 'rect')}>
                {nodes.critic.isActive ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : nodes.critic.isCompleted ? (
                  <Check size={16} className="mr-2 stroke-[3px]" />
                ) : (
                  <GitPullRequest size={16} className="mr-2" />
                )}
                <div className="flex flex-col text-left">
                  <span className="text-[10px] md:text-[11px] font-bold leading-tight">Critic Agent</span>
                  <span className="text-[8.5px] opacity-75 leading-tight">Evaluation</span>
                </div>
              </div>
            </div>
          </foreignObject>

          {/* HITL DECISION DIAMOND */}
          <foreignObject x="690" y="91" width="100" height="90">
            <div
              className="w-full h-full flex flex-col items-center justify-center relative cursor-help"
              onMouseEnter={(e) => handleMouseEnter('hitl', nodes.hitl.label, nodes.hitl.desc, e)}
              onMouseLeave={handleMouseLeave}
            >
              <div className="relative w-12 h-12 flex items-center justify-center">
                <div className={`absolute inset-0 rotate-45 border-2 rounded transition-all duration-300 ${
                  nodes.hitl.isCompleted ? 'bg-success border-success text-white shadow-success/15' :
                  nodes.hitl.isFailed ? 'bg-danger border-danger text-white shadow-danger/15' :
                  nodes.hitl.isActive ? 'bg-card border-teal-500 ring-4 ring-teal-500/20 animate-pulse text-teal-600' :
                  'bg-card border-border text-muted-foreground'
                }`} />
                <div className={`relative z-10 flex items-center justify-center ${
                  nodes.hitl.isCompleted || nodes.hitl.isFailed ? 'text-white' : (nodes.hitl.isActive ? 'text-teal-600' : 'text-muted-foreground')
                }`}>
                  {nodes.hitl.isCompleted ? <Check size={18} className="stroke-[3px]" /> :
                    nodes.hitl.isFailed ? <X size={18} className="stroke-[3px]" /> :
                      <UserCheck size={18} />}
                </div>
              </div>
              <span className={`text-[10px] font-extrabold mt-1.5 leading-none ${nodes.hitl.isActive ? 'text-teal-600 dark:text-teal-400' : 'text-muted-foreground'}`}>
                HITL Decision Gate
              </span>
            </div>
          </foreignObject>

          {/* EXPORTS TERMINAL NODE */}
          <foreignObject x="790" y="96" width="130" height="58">
            <div
              className="w-full h-full flex items-center justify-center relative cursor-help"
              onMouseEnter={(e) => handleMouseEnter('export', nodes.export.label, nodes.export.desc, e)}
              onMouseLeave={handleMouseLeave}
            >
              <div className={getStyleClasses(nodes.export, 'rect')}>
                <Wrench size={16} className="mr-2 shrink-0" />
                <div className="flex flex-col text-left">
                  <span className="text-[10px] md:text-[11px] font-bold leading-tight">Export</span>
                  <span className="text-[8.5px] opacity-75 leading-tight">
                    {pipelineStatus === PIPELINE_STATUS.EXPORTED ? 'Completed' : 'Sync outputs'}
                  </span>
                </div>
              </div>
            </div>
          </foreignObject>

          {/* AGENT TOOLS & STATE */}
          <foreignObject x="365" y="310" width="170" height="70">
            {(() => {
              const isToolActive = nodes.orchestrator.isActive;
              const isToolComplete = nodes.orchestrator.isCompleted;
              let toolBoxClass = "w-full h-full rounded-xl border p-1.5 px-2 pb-3 text-left cursor-help transition-all duration-200 bg-slate-50/95 dark:bg-slate-900/90 relative flex flex-col justify-between shadow-sm ";
              if (isToolComplete) {
                toolBoxClass += "border-success bg-success/5 shadow-success/10 ring-2 ring-success/10";
              } else if (isToolActive) {
                toolBoxClass += "border-primary animate-pulse shadow-primary/10 ring-2 ring-primary/10";
              } else {
                toolBoxClass += "border-border hover:border-primary/40";
              }

              return (
                <div
                  className={toolBoxClass}
                  onMouseEnter={(e) => handleMouseEnter('tools-agent', 'Agent Tools & State (MCP)', 'Provides Tavily web search, GitHub integration, cached via Upstash Redis.', e)}
                  onMouseLeave={handleMouseLeave}
                >
                  <div className="flex items-center justify-between border-b border-primary/15 pb-0.5 mb-0.5">
                    <div className="flex items-center gap-1 text-primary">
                      <Wrench size={13} className="shrink-0" />
                      <span className="text-[9px] font-extrabold uppercase tracking-wide">Agent Tools & State</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-[8px] text-muted-foreground leading-snug">
                    <div className="hover:text-primary transition-colors">
                      <span className="font-extrabold text-ai-spark block mb-0.5 text-[7px] uppercase">Autonomous</span>
                      <span>🔍 Tavily</span>
                      <span className="block">💻 GitHub</span>
                    </div>
                    <div className="border-l border-border/60 pl-1 hover:text-indigo-500 transition-colors">
                      <span className="font-extrabold text-indigo-500 block mb-0.5 text-[7px] uppercase">Cache</span>
                      <span>💾 Upstash</span>
                    </div>
                  </div>
                </div>
              );
            })()}
          </foreignObject>

          {/* DELIVERY & NOTIFICATION TARGETS */}
          <foreignObject x="750" y="310" width="170" height="70">
            {(() => {
              const isToolActive = pipelineStatus === PIPELINE_STATUS.EXPORTING;
              const isToolComplete = pipelineStatus === PIPELINE_STATUS.EXPORTED;
              let toolBoxClass = "w-full h-full rounded-xl border p-1.5 px-2 pb-3 text-left cursor-help transition-all duration-200 bg-slate-50/95 dark:bg-slate-900/90 relative flex flex-col justify-between shadow-sm ";
              if (isToolComplete) {
                toolBoxClass += "border-success bg-success/5 shadow-success/10 ring-2 ring-success/10";
              } else if (isToolActive) {
                toolBoxClass += "border-primary animate-pulse shadow-primary/10 ring-2 ring-primary/10";
              } else {
                toolBoxClass += "border-border hover:border-primary/40";
              }

              return (
                <div
                  className={toolBoxClass}
                  onMouseEnter={(e) => handleMouseEnter('tools-delivery', 'Delivery & Notification Targets', 'Syncs deliverables to Atlassian Jira and Google Sheets, alerts to Slack.', e)}
                  onMouseLeave={handleMouseLeave}
                >
                  <div className="flex items-center justify-between border-b border-primary/15 pb-0.5 mb-0.5">
                    <div className="flex items-center gap-1 text-primary">
                      <Wrench size={13} className="shrink-0" />
                      <span className="text-[9px] font-extrabold uppercase tracking-wide">Delivery Targets</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-[8px] text-muted-foreground leading-snug">
                    <div className="hover:text-success transition-colors">
                      <span className="font-extrabold text-success block mb-0.5 text-[7px] uppercase">EXPORT</span>
                      <span>📋 Jira Epic</span>
                      <span className="block">📊 Sheets</span>
                    </div>
                    <div className="border-l border-border/60 pl-1 hover:text-warning transition-colors">
                      <span className="font-extrabold text-warning block mb-0.5 text-[7px] uppercase">Alerts</span>
                      <span>💬 Slack</span>
                    </div>
                  </div>
                </div>
              );
            })()}
          </foreignObject>
        </svg>
      </div>

      {tooltipState && (
        <div
          className="absolute z-50 p-3 bg-background border border-border rounded-lg shadow-2xl text-[10px] text-muted-foreground leading-normal pointer-events-none transition-all duration-200 w-64 -translate-x-1/2 -translate-y-full animate-in fade-in zoom-in-95 duration-100"
          style={getTooltipPosition()}
        >
          <div className="flex items-center gap-1.5 mb-1 pb-1 border-b border-border font-bold text-foreground uppercase tracking-wide">
            {tooltipState.id === 'upload' && <Upload size={12} className="text-success" />}
            {tooltipState.id === 'security' && <Shield size={12} className="text-danger" />}
            {tooltipState.id === 'orchestrator' && <Cpu size={12} className="text-ai-spark" />}
            {tooltipState.id === 'critic' && <GitPullRequest size={12} className="text-warning" />}
            {tooltipState.id === 'hitl' && <UserCheck size={12} className="text-success" />}
            {tooltipState.id === 'export' && <Wrench size={12} className="text-success" />}
            {tooltipState.id === 'rag' && <Database size={12} className="text-amber-500" />}
            {tooltipState.id === 'loop' && <Loader2 size={12} className="text-warning animate-spin" />}
            {tooltipState.id.includes('tools') && <Wrench size={12} className="text-primary" />}
            {tooltipState.title}
          </div>
          {tooltipState.desc}
        </div>
      )}
    </div>
  );
};