import React from 'react';
import { Shield, FileJson, Cpu, MessageSquare, UserCheck, Check, Loader2, X, Pause } from 'lucide-react';
import { type ArtifactsState, type CriticOutput, type LogEvent } from '../hooks/useSSE';
import { type PipelineStatus, PIPELINE_STATUS } from '../lib/pipelineStatus';

interface TimelineStepperProps {
  pipelineStatus: PipelineStatus;
  completedAgents: Set<string>;
  artifacts: ArtifactsState | null;
  criticOutput: CriticOutput | null;
  logs: LogEvent[];
}

export const TimelineStepper: React.FC<TimelineStepperProps> = ({
  pipelineStatus,
  completedAgents,
  artifacts,
  criticOutput: _criticOutput,
  logs,
}) => {
  const hasBrdSections = Array.isArray(artifacts?.brd_sections) && (artifacts.brd_sections as unknown[]).length > 0;

  // Centralized helper to compute step status
  const getStepStatus = (stepId: number): { isCompleted: boolean; isActive: boolean; isFailed: boolean } => {
    // 1. Check for terminal export failure (special case for Step 7)
    if (stepId === 7 && pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED) {
      return { isCompleted: false, isActive: false, isFailed: true };
    }

    // 2. Cancellation and Error Handling:
    if (pipelineStatus === PIPELINE_STATUS.ERROR || pipelineStatus === PIPELINE_STATUS.CANCELED) {
      const securityPassed = logs.some(l => l.type === 'security_complete') || logs.some(l => l.type === 'agent_start' && l.agent === 'orchestrator') || hasBrdSections;
      const orchestratorCompleted = completedAgents.has('orchestrator') || hasBrdSections || logs.some(l => l.type === 'orchestrator_reconciled');
      const draftingCompleted = (
        completedAgents.has('engineering_plan_generator') &&
        completedAgents.has('schedule_estimator') &&
        completedAgents.has('solution_architect') &&
        completedAgents.has('poc_planner') &&
        completedAgents.has('tech_stack_recommender')
      ) || logs.some(l => l.type === 'orchestrator_reconciled');
      const arbitrationCompleted = logs.some(l => l.type === 'orchestrator_reconciled') || !!artifacts?.alignment_memo;
      const alignmentCompleted = logs.some(l => l.type === 'agent_start' && l.agent === 'critic') || !!artifacts?.critic_output;
      const criticCompleted = logs.some(l => l.type === 'agent_complete' && l.agent === 'critic') || !!artifacts?.critic_output;

      if (stepId === 1) {
        const completed = securityPassed;
        return { isCompleted: completed, isActive: false, isFailed: !completed };
      }
      if (stepId === 2) {
        const completed = orchestratorCompleted;
        const failed = securityPassed && !completed;
        return { isCompleted: completed, isActive: false, isFailed: failed };
      }
      if (stepId === 3) {
        const completed = draftingCompleted;
        const failed = orchestratorCompleted && !completed;
        return { isCompleted: completed, isActive: false, isFailed: failed };
      }
      if (stepId === 4) {
        const completed = arbitrationCompleted;
        const failed = draftingCompleted && !completed;
        return { isCompleted: completed, isActive: false, isFailed: failed };
      }
      if (stepId === 5) {
        const completed = alignmentCompleted;
        const failed = arbitrationCompleted && !completed;
        return { isCompleted: completed, isActive: false, isFailed: failed };
      }
      if (stepId === 6) {
        const completed = criticCompleted;
        const failed = alignmentCompleted && !completed;
        return { isCompleted: completed, isActive: false, isFailed: failed };
      }
      if (stepId === 7) {
        return { isCompleted: false, isActive: false, isFailed: true };
      }
    }

    // 3. Normal Execution Flow:
    const activeStepId = (() => {
      switch (pipelineStatus) {
        case PIPELINE_STATUS.INITIALIZING:
        case PIPELINE_STATUS.STARTED:
        case PIPELINE_STATUS.SECURITY_CHECK:
          return 1;
        case PIPELINE_STATUS.RUNNING:
        case PIPELINE_STATUS.ORCHESTRATOR_PARSING:
          return 2;
        case PIPELINE_STATUS.DRAFTING:
          return 3;
        case PIPELINE_STATUS.ARBITRATING:
          return 4;
        case PIPELINE_STATUS.ALIGNING:
        case PIPELINE_STATUS.REVISING:
          return 5;
        case PIPELINE_STATUS.EVALUATING:
          return 6;
        case PIPELINE_STATUS.AWAITING_HITL:
        case PIPELINE_STATUS.EXPORTING:
          return 7;
        default:
          return 0; // idle or terminal
      }
    })();

    const isActive = activeStepId === stepId;

    const isCompleted = (() => {
      if (pipelineStatus === PIPELINE_STATUS.EXPORTED || pipelineStatus === PIPELINE_STATUS.REJECTED) {
        return true;
      }
      if (pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED) {
        return stepId < 7;
      }
      if (pipelineStatus === PIPELINE_STATUS.REVISING) {
        return stepId < 5 || stepId === 6;
      }
      return activeStepId > stepId;
    })();

    return { isCompleted, isActive, isFailed: false };
  };

  // Define the steps
  const steps = [
    {
      id: 1,
      label: 'Security Validation',
      description: 'Format, Security & PII Check',
      icon: Shield,
      get isCompleted() { return getStepStatus(1).isCompleted; },
      get isFailed() { return getStepStatus(1).isFailed; },
      get isActive() { return getStepStatus(1).isActive; },
    },
    {
      id: 2,
      label: 'Orchestrator',
      get description() {
        const hasReconciled = logs.some(l => l.type === 'orchestrator_reconciled');
        if (hasReconciled) {
          return 'Arbitration Completed';
        }
        if (pipelineStatus === PIPELINE_STATUS.RUNNING || pipelineStatus === PIPELINE_STATUS.ORCHESTRATOR_PARSING) {
          return 'Parsing BRD...';
        }
        return 'Parsing BRD';
      },
      icon: FileJson,
      get isCompleted() { return getStepStatus(2).isCompleted; },
      get isFailed() { return getStepStatus(2).isFailed; },
      get isActive() { return getStepStatus(2).isActive; },
    },
    {
      id: 3,
      label: 'Specialists Drafting',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.DRAFTING) {
          return 'Drafting plans...';
        }
        return 'First Draft Generation';
      },
      icon: Cpu,
      get isCompleted() { return getStepStatus(3).isCompleted; },
      get isFailed() { return getStepStatus(3).isFailed; },
      get isActive() { return getStepStatus(3).isActive; },
    },
    {
      id: 4,
      label: 'Arbitration',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.ARBITRATING) {
          return 'Reconciling agent drafts...';
        }
        return 'Conflict Resolution';
      },
      icon: MessageSquare,
      get isCompleted() { return getStepStatus(4).isCompleted; },
      get isFailed() { return getStepStatus(4).isFailed; },
      get isActive() { return getStepStatus(4).isActive; },
    },
    {
      id: 5,
      label: 'Specialists Alignment',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.ALIGNING) {
          return 'Aligning plans...';
        }
        if (pipelineStatus === PIPELINE_STATUS.REVISING) {
          return 'Revising plans...';
        }
        return 'Finalized Plan';
      },
      icon: Cpu,
      get isCompleted() { return getStepStatus(5).isCompleted; },
      get isFailed() { return getStepStatus(5).isFailed; },
      get isActive() { return getStepStatus(5).isActive; },
    },
    {
      id: 6,
      label: 'Critic',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.EVALUATING) {
          return 'Evaluating quality...';
        }
        if (pipelineStatus === PIPELINE_STATUS.REVISING) {
          return 'Triggered revision...';
        }
        const revisionCount = logs.filter(l => l.type === 'revision_start').length;
        if (revisionCount > 0) {
          return `🔄 Revision ${revisionCount} done`;
        }
        return 'Evaluation & Quality Score';
      },
      icon: MessageSquare,
      get isCompleted() { return getStepStatus(6).isCompleted; },
      get isFailed() { return getStepStatus(6).isFailed; },
      get isActive() { return getStepStatus(6).isActive; },
    },
    {
      id: 7,
      label: 'Decision',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.AWAITING_HITL) {
          return 'Awaiting EM decision';
        }
        if (pipelineStatus === PIPELINE_STATUS.EXPORTING) {
          return 'Exporting plans...';
        }
        if (pipelineStatus === PIPELINE_STATUS.EXPORTED) {
          return 'Exported successfully';
        }
        if (pipelineStatus === PIPELINE_STATUS.REJECTED) {
          return 'Plan rejected';
        }
        if (pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED) {
          return 'Export failed';
        }
        return 'Final decision & export';
      },
      icon: UserCheck,
      get isCompleted() { return getStepStatus(7).isCompleted; },
      get isFailed() { return getStepStatus(7).isFailed; },
      get isActive() { return getStepStatus(7).isActive; },
    },
  ];

  const getDetailedStatus = (agentKey: string, pass: 1 | 2): { status: 'pending' | 'running' | 'completed' | 'failed'; label: string } => {
    const labels: Record<string, string> = {
      engineering_plan_generator: 'Plan',
      solution_architect: 'Architect',
      schedule_estimator: 'Schedule',
      poc_planner: 'PoC',
      tech_stack_recommender: 'Tech Stack',
    };
    const label = labels[agentKey] || agentKey;

    const reconciledIdx = logs.findIndex(l => l.type === 'orchestrator_reconciled');
    const pass1Logs = reconciledIdx === -1 ? logs : logs.slice(0, reconciledIdx);
    const pass2Logs = reconciledIdx === -1 ? [] : logs.slice(reconciledIdx + 1);

    const getPassStatus = (passLogs: LogEvent[]) => {
      const hasFailed = passLogs.some(l => l.type === 'agent_failed' && (l.agent === agentKey || l.payload?.agent === agentKey));
      if (hasFailed) return 'failed';
      const hasCompleted = passLogs.some(l => l.type === 'agent_complete' && (l.agent === agentKey || l.payload?.agent === agentKey));
      if (hasCompleted) return 'completed';
      const hasStarted = passLogs.some(l => l.type === 'agent_start' && (l.agent === agentKey || l.payload?.agent === agentKey));
      if (hasStarted) return 'running';
      return 'pending';
    };

    if (pass === 1) {
      if (
        ([
          PIPELINE_STATUS.ARBITRATING,
          PIPELINE_STATUS.ALIGNING,
          PIPELINE_STATUS.EVALUATING,
          PIPELINE_STATUS.REVISING,
          PIPELINE_STATUS.AWAITING_HITL,
          PIPELINE_STATUS.EXPORTED,
          PIPELINE_STATUS.REJECTED
        ] as PipelineStatus[]).includes(pipelineStatus)
      ) {
        return { status: 'completed', label };
      }
      return { status: getPassStatus(pass1Logs), label };
    } else {
      if (
        ([
          PIPELINE_STATUS.EVALUATING,
          PIPELINE_STATUS.REVISING,
          PIPELINE_STATUS.AWAITING_HITL,
          PIPELINE_STATUS.EXPORTED,
          PIPELINE_STATUS.REJECTED
        ] as PipelineStatus[]).includes(pipelineStatus)
      ) {
        return { status: 'completed', label };
      }
      const pass2Started = pass2Logs.some(l => l.type === 'agent_start');
      if (pass2Started) {
        const s2 = getPassStatus(pass2Logs);
        if (s2 === 'pending') {
          return { status: 'completed', label };
        }
        return { status: s2, label };
      }
      return { status: 'pending', label };
    }
  };

  const canceledStepId = pipelineStatus === PIPELINE_STATUS.CANCELED ? (steps.find(s => !s.isCompleted)?.id || 1) : null;

  return (
    <div className="w-full bg-card border border-border rounded-xl p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-primary uppercase tracking-wider">Agentic Workflow Progress</h3>
        <div className="flex items-center gap-2">
          {pipelineStatus !== PIPELINE_STATUS.IDLE && pipelineStatus !== PIPELINE_STATUS.EXPORTED && pipelineStatus !== PIPELINE_STATUS.REJECTED && pipelineStatus !== PIPELINE_STATUS.ERROR && pipelineStatus !== PIPELINE_STATUS.CANCELED && (
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
          )}
          <span className="text-xs text-muted-foreground font-semibold capitalize">
            Status: <span className={
              pipelineStatus === PIPELINE_STATUS.ERROR ? 'text-danger' :
                pipelineStatus === PIPELINE_STATUS.EXPORTED ? 'text-success' :
                  pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ? 'text-warning' :
                    pipelineStatus === PIPELINE_STATUS.CANCELED ? 'text-slate-500' :
                      'text-primary'
            }>{pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ? 'awaiting decision' : pipelineStatus === PIPELINE_STATUS.EVALUATING ? 'Evaluating' : pipelineStatus.replace(/_/g, ' ')}</span>
          </span>
        </div>
      </div>

      {pipelineStatus === PIPELINE_STATUS.CANCELED && (
        <div className="mb-4 p-3 bg-slate-500/10 border border-slate-500/20 rounded-lg text-xs text-slate-600 dark:text-slate-400 font-semibold flex items-center justify-between animate-scale-in">
          <span>Run was aborted by the user.</span>
          <span className="bg-slate-500/20 px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider">Canceled</span>
        </div>
      )}

      {/* Increased mt-16 to leave enough space for the headers above */}
      <div className="relative flex items-start justify-between w-full mt-16">
        {/* Connecting progress line - sits behind nodes (z-0) and top-6 matches the node circle centers */}
        <div className="absolute left-0 right-0 top-6 h-0.5 bg-secondary z-0" />

        {steps.map((step, idx) => {
          const StepIcon = step.icon;
          const isCompleted = step.isCompleted;
          const isFailed = step.isFailed;
          const isActive = step.isActive;

          // Compute style tokens
          let iconContainerClasses = "w-12 h-12 rounded-full flex items-center justify-center border-2 z-10 transition-all duration-300 ";
          let textLabelClasses = "text-xs font-bold transition-colors duration-300 ";
          const descriptionClasses = "text-[9px] md:text-[10px] text-slate-600 dark:text-slate-400 font-medium hidden md:block text-center ";

          if (isCompleted) {
            iconContainerClasses += "bg-success border-success text-white shadow-[0_0_15px_rgba(16,185,129,0.2)]";
            textLabelClasses += "text-success";
          } else if (isFailed) {
            iconContainerClasses += "bg-danger border-danger text-white shadow-[0_0_15px_rgba(239,68,68,0.2)]";
            textLabelClasses += "text-danger";
          } else if (isActive) {
            if (step.id === 7 && pipelineStatus === PIPELINE_STATUS.AWAITING_HITL) {
              iconContainerClasses += "bg-card border-warning text-warning ring-4 ring-warning/30 animate-pulse shadow-[0_0_20px_rgba(245,158,11,0.4)]";
              textLabelClasses += "text-warning font-extrabold";
            } else {
              iconContainerClasses += "bg-card border-primary text-primary ring-4 ring-primary/30 animate-pulse shadow-[0_0_20px_rgba(99,102,241,0.4)]";
              textLabelClasses += "text-primary font-extrabold";
            }
          } else {
            iconContainerClasses += "bg-card border-border text-muted-foreground";
            textLabelClasses += "text-muted-foreground";
          }

          return (
            <div key={step.id} className={`flex flex-col items-center flex-1 relative z-10 transition-all duration-300 ${
              pipelineStatus === PIPELINE_STATUS.CANCELED && !isCompleted ? 'opacity-40 grayscale-[50%]' : ''
            }`}>
              {/* Line connector segment highlight - starts at center of current step and goes to next step (prevents overlapping issues on checkmarks) */}
              {idx < steps.length - 1 && (
                <div
                  className={`absolute left-[50%] right-[-50%] top-6 h-0.5 z-0 transition-all duration-500 ${
                    step.isCompleted
                      ? 'bg-gradient-to-r from-success to-primary'
                      : step.isFailed
                      ? 'bg-gradient-to-r from-danger to-secondary'
                      : 'bg-secondary'
                  }`}
                />
              )}

              {/* Odd-numbered step header: absolute-positioned above the circle */}
              {step.id % 2 !== 0 && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 flex flex-col items-center text-center h-12 justify-end w-[130px] md:w-[150px]">
                  <span className={`${textLabelClasses} leading-tight flex items-center justify-center gap-1`}>
                    {step.label}
                    {step.id === 5 && pipelineStatus === PIPELINE_STATUS.REVISING && (
                      <span className="text-[9px] font-bold text-warning bg-warning/10 border border-warning/20 px-1.5 py-0.5 rounded-full animate-pulse shrink-0">
                        🔄 Revision {logs.filter(l => l.type === 'revision_start').length}/2
                      </span>
                    )}
                  </span>
                  <span className={`${descriptionClasses} leading-tight mt-0.5 block text-center`}>{step.description}</span>
                </div>
              )}

              <div className={iconContainerClasses}>
                {isCompleted ? (
                  <Check size={20} className="stroke-[3px] animate-scale-in" />
                ) : isFailed ? (
                  <X size={20} className="stroke-[3px] animate-scale-in text-danger" />
                ) : isActive ? (
                  step.id === 7 && pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ? (
                    <Pause size={20} className="animate-pulse text-warning" />
                  ) : (
                    <Loader2 size={20} className="animate-spin text-primary" />
                  )
                ) : (
                  <StepIcon size={18} />
                )}
              </div>

              {/* Even-numbered step header: flows naturally in vertical stack below the circle */}
              {step.id % 2 === 0 && (
                <div className="mt-3 flex flex-col items-center text-center w-[130px] md:w-[150px] z-10">
                  <span className={`${textLabelClasses} leading-tight block text-center`}>{step.label}</span>
                  <span className={`${descriptionClasses} leading-tight mt-0.5 block text-center`}>{step.description}</span>
                </div>
              )}

              {/* Specialist status nested for Step 3 (Pass 1) and Step 5 (Pass 2) */}
              {(step.id === 3 || step.id === 5) && pipelineStatus !== 'idle' && (
                <div className={`mt-4 flex flex-col gap-2 w-full max-w-[140px] z-20 animate-scale-in transition-all duration-300 ${isCompleted ? 'opacity-40 hover:opacity-100' : ''}`}>
                  <div className="flex flex-col gap-1.5 bg-background/40 p-2 rounded-lg border border-border/60 shadow-inner">
                    {[
                      { key: 'solution_architect', shortLabel: 'Architect' },
                      { key: 'tech_stack_recommender', shortLabel: 'Tech Stack' },
                      { key: 'poc_planner', shortLabel: 'PoC' },
                      { key: 'engineering_plan_generator', shortLabel: 'Plan' },
                      { key: 'schedule_estimator', shortLabel: 'Schedule' },
                    ].map(spec => {
                      const pass = step.id === 3 ? 1 : 2;
                      const { status } = getDetailedStatus(spec.key, pass);
                      let specCardClass = "flex items-center justify-between px-2 py-1 rounded border text-[9px] font-semibold transition-all duration-300 ";
                      let statusIcon: React.ReactNode;
                      let delayStyle: React.CSSProperties = {};

                      if (status === 'running') {
                        const idx = [
                          'solution_architect',
                          'tech_stack_recommender',
                          'poc_planner',
                          'engineering_plan_generator',
                          'schedule_estimator',
                        ].indexOf(spec.key);
                        delayStyle = { animationDelay: `${idx * 150}ms` };
                      }

                      if (status === 'completed') {
                        specCardClass += "bg-success/15 border-success/30 text-[#15803d] dark:text-[#4ade80] font-extrabold";
                        statusIcon = <Check size={8} className="stroke-[3px] text-[#15803d] dark:text-[#4ade80] shrink-0" />;
                      } else if (status === 'running') {
                        specCardClass += "bg-primary/10 border-primary/40 text-primary ring-1 ring-primary/10 animate-pulse";
                        statusIcon = <Loader2 size={8} style={delayStyle} className="animate-spin text-primary shrink-0" />;
                      } else if (status === 'failed') {
                        specCardClass += "bg-danger/20 border-danger/40 text-danger";
                        statusIcon = <X size={8} className="stroke-[3px] text-danger shrink-0" />;
                      } else {
                        specCardClass += "bg-card/40 border-border/40 text-muted-foreground";
                        statusIcon = <div className="h-1 w-1 rounded-full bg-secondary shrink-0" />;
                      }

                      return (
                        <div key={spec.key} style={delayStyle} className={specCardClass} title={spec.key}>
                           <span className="truncate pr-1 text-left">{spec.shortLabel}</span>
                          {statusIcon}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Arbitration indicator under step 4 */}
              {step.id === 4 && (
                <div className="mt-2 flex flex-col gap-1.5 w-full max-w-[140px] z-20 animate-scale-in" title={artifacts?.alignment_memo?.overall_strategy || 'Pass 2 Directives'}>
                  {pipelineStatus === PIPELINE_STATUS.ARBITRATING && (
                    <div className="px-2 py-1 rounded bg-warning/15 border border-warning/35 text-[8px] text-warning font-semibold text-center animate-pulse">
                      EM Reconciling Drafts...
                    </div>
                  )}
                  {(artifacts?.alignment_memo || logs.some(l => l.type === 'orchestrator_reconciled')) && (
                    <div className="px-2.5 py-1.5 rounded-lg border border-warning/30 bg-warning/10 text-[9px] text-warning-foreground font-semibold flex flex-col gap-1 text-center">
                      <span>Strategy: {artifacts?.alignment_memo?.directives?.length || logs.find(l => l.type === 'orchestrator_reconciled')?.directive_count || 0} Directives</span>
                      {artifacts?.alignment_memo?.overall_strategy && (
                        <span className="text-[7.5px] opacity-80 line-clamp-2 italic font-normal text-warning-foreground">
                          "{artifacts.alignment_memo.overall_strategy}"
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Revision indicator under step 5 */}
              {step.id === 5 && (
                <div className="mt-2 flex flex-col gap-1.5 w-full max-w-[140px] z-20 animate-scale-in">
                  {logs.filter(l => l.type === 'revision_start').length > 0 && (
                    <div className="px-2 py-1 rounded bg-primary/10 border border-primary/30 text-[8px] text-primary font-bold text-center animate-pulse">
                      🔄 Revision {logs.filter(l => l.type === 'revision_start').length} of 2
                    </div>
                  )}
                </div>
              )}

              {/* Cancellation badge/chip on the canceled step */}
              {step.id === canceledStepId && (
                <div className="mt-2 flex flex-col gap-1.5 w-full max-w-[140px] z-20 animate-scale-in animate-pulse">
                  <div className="px-2 py-1 rounded bg-slate-500/15 border border-slate-500/35 text-[8px] text-slate-500 dark:text-slate-400 font-extrabold text-center">
                    🚫 Canceled at Step {step.id}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

