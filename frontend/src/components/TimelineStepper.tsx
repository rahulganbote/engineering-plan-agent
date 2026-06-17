import React from 'react';
import { Shield, FileJson, Cpu, MessageSquare, UserCheck, FileCheck, Check, Loader2 } from 'lucide-react';
import { type ArtifactsState, type CriticOutput, type ApprovalResult } from '../hooks/useSSE';

interface TimelineStepperProps {
  pipelineStatus: string;
  completedAgents: Set<string>;
  artifacts: ArtifactsState | null;
  criticOutput: CriticOutput | null;
  approvalResult: ApprovalResult | null;
}

export const TimelineStepper: React.FC<TimelineStepperProps> = ({
  pipelineStatus,
  completedAgents,
  artifacts,
  criticOutput,
  approvalResult,
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

  return (
    <div className="w-full bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Pipeline Execution Timeline</h3>
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

      <div className="relative flex items-center justify-between w-full">
        {/* Connecting progress line */}
        <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-0.5 bg-slate-800 -z-0" />

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
                  className={`absolute left-[-50%] right-[50%] top-6 h-0.5 -z-10 transition-all duration-500 ${
                    steps[idx - 1].isCompleted 
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
            </div>
          );
        })}
      </div>
    </div>
  );
};
