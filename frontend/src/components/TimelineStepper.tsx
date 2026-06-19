import React from 'react';
import { Shield, FileJson, Cpu, MessageSquare, UserCheck, FileCheck, Check, Loader2, X } from 'lucide-react';
import { type ArtifactsState, type CriticOutput, type ApprovalResult, type LogEvent } from '../hooks/useSSE';

interface TimelineStepperProps {
  pipelineStatus: string;
  completedAgents: Set<string>;
  artifacts: ArtifactsState | null;
  criticOutput: CriticOutput | null;
  approvalResult: ApprovalResult | null;
  logs: LogEvent[];
}

export const TimelineStepper: React.FC<TimelineStepperProps> = ({
  pipelineStatus,
  completedAgents,
  artifacts,
  criticOutput,
  approvalResult,
  logs,
}) => {

  // Define the steps
  const steps = [
    {
      id: 1,
      label: 'Security',
      description: 'Security & PII Check',
      icon: Shield,
      isCompleted: pipelineStatus !== 'idle' && pipelineStatus !== 'error',
      isActive: false, // Security validation is instantaneous before pipeline runs
    },
    {
      id: 2,
      label: 'Orchestrator',
      description: 'Parsing BRD',
      icon: FileJson,
      get isCompleted() {
        return completedAgents.has('orchestrator') || !!artifacts?.brd_sections;
      },
      get isActive() {
        return !this.isCompleted && (pipelineStatus === 'initializing' || pipelineStatus === 'started');
      },
    },
    {
      id: 3,
      label: 'Specialists',
      description: '5 Parallel Spokes',
      icon: Cpu,
      get isCompleted() {
        return (
          completedAgents.has('engineering_plan_generator') &&
          completedAgents.has('schedule_estimator') &&
          completedAgents.has('solution_architect') &&
          completedAgents.has('poc_planner') &&
          completedAgents.has('tech_stack_recommender')
        ) || !!artifacts?.plan_output;
      },
      get isActive() {
        return !this.isCompleted && (pipelineStatus === 'dispatching' || pipelineStatus === 'revising');
      },
    },
    {
      id: 4,
      label: 'Critic',
      description: 'Review & Revision',
      icon: MessageSquare,
      get isCompleted() {
        return completedAgents.has('critic') || !!criticOutput || !!artifacts?.critic_output;
      },
      get isActive() {
        return !this.isCompleted && pipelineStatus === 'critic_review';
      },
    },
    {
      id: 5,
      label: 'HITL Gate',
      description: 'Approval Paused',
      icon: UserCheck,
      get isCompleted() {
        return (
          !!approvalResult ||
          pipelineStatus === 'exported' ||
          pipelineStatus === 'export_failed' ||
          pipelineStatus === 'rejected'
        );
      },
      get isActive() {
        return !this.isCompleted && pipelineStatus === 'awaiting_hitl';
      },
    },
    {
      id: 6,
      label: 'Decision',
      description: 'Final Export',
      icon: FileCheck,
      get isCompleted() {
        return (
          pipelineStatus === 'exported' ||
          pipelineStatus === 'export_failed' ||
          pipelineStatus === 'rejected'
        );
      },
      get isActive() {
        return !this.isCompleted && (pipelineStatus === 'exported' || pipelineStatus === 'export_failed' || pipelineStatus === 'rejected');
      },
    },
  ];

  const getDetailedStatus = (agentKey: string): { status: 'pending' | 'running' | 'completed' | 'failed'; label: string } => {
    const labels: Record<string, string> = {
      security: 'Security & Injection Scan',
      orchestrator: 'Orchestrator BRD Parser',
      engineering_plan_generator: 'Engineering Plan Specialist',
      solution_architect: 'Solution Architect Specialist',
      schedule_estimator: 'Schedule & Estimator Specialist',
      poc_planner: 'PoC & Spike Planner Specialist',
      tech_stack_recommender: 'Tech Stack Specialist',
      critic: 'Critic Reviewer & Revision Gate',
    };

    const label = labels[agentKey] || agentKey;

    if (agentKey === 'security') {
      if (pipelineStatus === 'error' && !logs.some(l => l.type === 'agent_start' || l.type === 'status')) {
        return { status: 'failed', label };
      }
      if (pipelineStatus !== 'idle') {
        return { status: 'completed', label };
      }
      return { status: 'pending', label };
    }

    if (completedAgents.has(agentKey)) {
      return { status: 'completed', label };
    }

    if (agentKey === 'orchestrator') {
      const anySpecialistActive = completedAgents.has('engineering_plan_generator') ||
        logs.some(l => l.type === 'agent_start' && l.agent !== 'orchestrator');
      if (anySpecialistActive || !!artifacts?.brd_sections || ['dispatching', 'critic_review', 'awaiting_hitl', 'exported', 'rejected'].includes(pipelineStatus)) {
        return { status: 'completed', label };
      }
      if (pipelineStatus === 'initializing' || pipelineStatus === 'started' || logs.some(l => l.type === 'agent_start' && l.agent === 'orchestrator')) {
        return { status: 'running', label };
      }
      return { status: 'pending', label };
    }

    if (agentKey === 'critic') {
      if (completedAgents.has('critic') || !!criticOutput || !!artifacts?.critic_output) {
        return { status: 'completed', label };
      }
      if (pipelineStatus === 'critic_review') {
        return { status: 'running', label };
      }
      return { status: 'pending', label };
    }

    const hasFailed = logs.some(l => l.type === 'agent_failed' && (l.agent === agentKey || l.payload?.agent === agentKey));
    if (hasFailed) return { status: 'failed', label };

    const hasStarted = logs.some(l => l.type === 'agent_start' && (l.agent === agentKey || l.payload?.agent === agentKey));
    if (hasStarted) return { status: 'running', label };

    return { status: 'pending', label };
  };

  return (
    <div className="w-full bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider"><span>⚙️</span> Pipeline Execution Timeline</h3>
        <div className="flex items-center gap-2">
          {pipelineStatus !== 'idle' && pipelineStatus !== 'exported' && pipelineStatus !== 'rejected' && pipelineStatus !== 'error' && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
            </span>
          )}
          <span className="text-xs text-slate-400 font-semibold capitalize">
            Status: <span className={
              pipelineStatus === 'error' ? 'text-red-400' :
                pipelineStatus === 'exported' ? 'text-emerald-400' :
                  pipelineStatus === 'awaiting_hitl' ? 'text-amber-400' :
                    'text-indigo-400'
            }>{pipelineStatus}</span>
          </span>
        </div>
      </div>

      <div className="relative flex items-start justify-between w-full">
        {/* Connecting progress line */}
        <div className="absolute left-0 right-0 top-6 h-0.5 bg-slate-800 -z-0" />

        {steps.map((step, idx) => {
          const StepIcon = step.icon;
          const isCompleted = step.isCompleted;
          const isActive = step.isActive;

          // Compute style tokens
          let iconContainerClasses = "w-12 h-12 rounded-full flex items-center justify-center border-2 z-15 transition-all duration-300 ";
          let textLabelClasses = "text-xs font-bold mt-2 transition-colors duration-300 ";
          const descriptionClasses = "text-[10px] text-slate-500 truncate hidden md:block ";

          if (isCompleted) {
            iconContainerClasses += "bg-emerald-950/80 border-emerald-500 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)]";
            textLabelClasses += "text-emerald-400";
          } else if (isActive) {
            iconContainerClasses += "bg-indigo-950/80 border-indigo-500 text-indigo-400 ring-4 ring-indigo-500/30 animate-pulse shadow-[0_0_20px_rgba(99,102,241,0.4)]";
            textLabelClasses += "text-indigo-400 font-extrabold";
          } else {
            iconContainerClasses += "bg-slate-950 border-slate-800 text-slate-600";
            textLabelClasses += "text-slate-500";
          }

          return (
            <div key={step.id} className="flex flex-col items-center flex-1 relative z-10">
              {/* Line connector segment highlight */}
              {idx > 0 && (
                <div
                  className={`absolute left-[-50%] right-[50%] top-6 h-0.5 -z-10 transition-all duration-500 ${steps[idx - 1].isCompleted
                      ? 'bg-gradient-to-r from-emerald-500 to-indigo-500'
                      : 'bg-slate-800'
                    }`}
                />
              )}

              <div className={iconContainerClasses}>
                {isCompleted ? (
                  <Check size={20} className="stroke-[3px] animate-scale-in" />
                ) : isActive ? (
                  <Loader2 size={20} className="animate-spin text-indigo-400" />
                ) : (
                  <StepIcon size={18} />
                )}
              </div>
              <span className={textLabelClasses}>{step.label}</span>
              <span className={descriptionClasses}>{step.description}</span>

              {/* Specialist status stacked in parallel for Step 3 */}
              {step.id === 3 && pipelineStatus !== 'idle' && (
                <div className="mt-4 flex flex-col gap-1.5 w-full max-w-[140px] bg-slate-950/40 p-2 rounded-lg border border-slate-800/60 shadow-inner z-20 animate-scale-in">
                  {[
                    { key: 'engineering_plan_generator', shortLabel: 'Plan' },
                    { key: 'solution_architect', shortLabel: 'Architect' },
                    { key: 'schedule_estimator', shortLabel: 'Estimator' },
                    { key: 'poc_planner', shortLabel: 'PoC' },
                    { key: 'tech_stack_recommender', shortLabel: 'Tech Stack' },
                  ].map(spec => {
                    const { status } = getDetailedStatus(spec.key);
                    let specCardClass = "flex items-center justify-between px-2 py-1 rounded border text-[9px] font-semibold transition-all duration-300 ";
                    let statusIcon: React.ReactNode;

                    if (status === 'completed') {
                      specCardClass += "bg-emerald-950/20 border-emerald-800/40 text-emerald-400";
                      statusIcon = <Check size={8} className="stroke-[3px] text-emerald-400 shrink-0" />;
                    } else if (status === 'running') {
                      specCardClass += "bg-indigo-950/20 border-indigo-500/40 text-indigo-300 ring-1 ring-indigo-500/10 animate-pulse";
                      statusIcon = <Loader2 size={8} className="animate-spin text-indigo-400 shrink-0" />;
                    } else if (status === 'failed') {
                      specCardClass += "bg-red-950/20 border-red-900/40 text-red-400";
                      statusIcon = <X size={8} className="stroke-[3px] text-red-400 shrink-0" />;
                    } else {
                      specCardClass += "bg-slate-900/40 border-slate-800/40 text-slate-500";
                      statusIcon = <div className="h-1 w-1 rounded-full bg-slate-700 shrink-0" />;
                    }

                    return (
                      <div key={spec.key} className={specCardClass} title={spec.key}>
                        <span className="truncate pr-1 text-left">{spec.shortLabel}</span>
                        {statusIcon}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

