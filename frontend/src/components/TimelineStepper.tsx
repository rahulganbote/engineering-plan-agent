import React from 'react';
import { Shield, FileJson, Cpu, MessageSquare, UserCheck, Check, Loader2, X } from 'lucide-react';
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

  // Define the steps
  const steps = [
    {
      id: 1,
      label: 'Security',
      description: 'Security & PII Check',
      icon: Shield,
      get isCompleted() {
        if (pipelineStatus === PIPELINE_STATUS.ERROR) {
          return logs.some(l => l.type === 'security_complete') || logs.some(l => l.type === 'agent_start' && l.agent === 'orchestrator') || hasBrdSections;
        }
        return (
          [
            PIPELINE_STATUS.RUNNING,
            PIPELINE_STATUS.DRAFTING,
            PIPELINE_STATUS.ARBITRATING,
            PIPELINE_STATUS.ALIGNING,
            PIPELINE_STATUS.SPECIALIST_EXECUTING,
            PIPELINE_STATUS.EVALUATING,
            PIPELINE_STATUS.REVISING,
            PIPELINE_STATUS.AWAITING_HITL,
            PIPELINE_STATUS.EXPORTING,
            PIPELINE_STATUS.EXPORTED,
            PIPELINE_STATUS.REJECTED
          ] as PipelineStatus[]
        ).includes(pipelineStatus) || completedAgents.has('orchestrator') || hasBrdSections;
      },
      get isFailed() {
        return pipelineStatus === PIPELINE_STATUS.ERROR && !this.isCompleted;
      },
      get isActive() {
        return !this.isCompleted && !this.isFailed && (
          pipelineStatus === PIPELINE_STATUS.INITIALIZING ||
          pipelineStatus === PIPELINE_STATUS.STARTED ||
          pipelineStatus === PIPELINE_STATUS.SECURITY_CHECK
        );
      },
    },
    {
      id: 2,
      label: 'Orchestrator',
      get description() {
        const hasReconciled = logs.some(l => l.type === 'orchestrator_reconciled');
        if (hasReconciled) {
          return 'Arbitration Completed';
        }
        if (pipelineStatus === PIPELINE_STATUS.RUNNING) {
          return 'Parsing BRD...';
        }
        return 'Parsing BRD';
      },
      icon: FileJson,
      get isCompleted() {
        return (
          completedAgents.has('orchestrator') ||
          hasBrdSections ||
          (
            [
              PIPELINE_STATUS.DRAFTING,
              PIPELINE_STATUS.ARBITRATING,
              PIPELINE_STATUS.ALIGNING,
              PIPELINE_STATUS.SPECIALIST_EXECUTING,
              PIPELINE_STATUS.EVALUATING,
              PIPELINE_STATUS.REVISING,
              PIPELINE_STATUS.AWAITING_HITL,
              PIPELINE_STATUS.EXPORTING,
              PIPELINE_STATUS.EXPORTED,
              PIPELINE_STATUS.REJECTED
            ] as PipelineStatus[]
          ).includes(pipelineStatus)
        );
      },
      get isFailed() {
        const securityPassed = logs.some(l => l.type === 'security_complete') || logs.some(l => l.type === 'agent_start' && l.agent === 'orchestrator') || hasBrdSections;
        return pipelineStatus === PIPELINE_STATUS.ERROR && securityPassed && !this.isCompleted;
      },
      get isActive() {
        return !this.isCompleted && !this.isFailed && (pipelineStatus === PIPELINE_STATUS.RUNNING);
      },
    },
    {
      id: 3,
      label: 'Specialists Pass 1',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.DRAFTING) {
          return 'Drafting plans...';
        }
        return 'Drafting (Pass 1)';
      },
      icon: Cpu,
      get isCompleted() {
        return (
          [
            PIPELINE_STATUS.ARBITRATING,
            PIPELINE_STATUS.ALIGNING,
            PIPELINE_STATUS.SPECIALIST_EXECUTING,
            PIPELINE_STATUS.EVALUATING,
            PIPELINE_STATUS.REVISING,
            PIPELINE_STATUS.AWAITING_HITL,
            PIPELINE_STATUS.EXPORTING,
            PIPELINE_STATUS.EXPORTED,
            PIPELINE_STATUS.REJECTED
          ] as PipelineStatus[]
        ).includes(pipelineStatus);
      },
      get isFailed() {
        const orchestratorCompleted = completedAgents.has('orchestrator') || hasBrdSections || logs.some(l => l.type === 'orchestrator_reconciled');
        return pipelineStatus === PIPELINE_STATUS.ERROR && orchestratorCompleted && !this.isCompleted;
      },
      get isActive() {
        return !this.isCompleted && !this.isFailed && (pipelineStatus === PIPELINE_STATUS.DRAFTING);
      },
    },
    {
      id: 4,
      label: 'Arbitration',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.ARBITRATING) {
          return 'EM Reconciling drafts...';
        }
        return 'EM Review';
      },
      icon: MessageSquare,
      get isCompleted() {
        return (
          [
            PIPELINE_STATUS.ALIGNING,
            PIPELINE_STATUS.SPECIALIST_EXECUTING,
            PIPELINE_STATUS.EVALUATING,
            PIPELINE_STATUS.REVISING,
            PIPELINE_STATUS.AWAITING_HITL,
            PIPELINE_STATUS.EXPORTING,
            PIPELINE_STATUS.EXPORTED,
            PIPELINE_STATUS.REJECTED
          ] as PipelineStatus[]
        ).includes(pipelineStatus) || logs.some(l => l.type === 'orchestrator_reconciled');
      },
      get isFailed() {
        const pass1Completed = this.isCompleted || logs.some(l => l.type === 'orchestrator_reconciled');
        return pipelineStatus === PIPELINE_STATUS.ERROR && !pass1Completed && !this.isCompleted;
      },
      get isActive() {
        return !this.isCompleted && !this.isFailed && (pipelineStatus === PIPELINE_STATUS.ARBITRATING);
      },
    },
    {
      id: 5,
      label: 'Specialists Pass 2',
      get description() {
        if (pipelineStatus === PIPELINE_STATUS.ALIGNING || pipelineStatus === PIPELINE_STATUS.SPECIALIST_EXECUTING) {
          return 'Aligning plans...';
        }
        if (pipelineStatus === PIPELINE_STATUS.REVISING) {
          return 'Revising plans...';
        }
        return 'Alignment (Pass 2)';
      },
      icon: Cpu,
      get isCompleted() {
        return (
          [
            PIPELINE_STATUS.EVALUATING,
            PIPELINE_STATUS.REVISING,
            PIPELINE_STATUS.AWAITING_HITL,
            PIPELINE_STATUS.EXPORTING,
            PIPELINE_STATUS.EXPORTED,
            PIPELINE_STATUS.REJECTED
          ] as PipelineStatus[]
        ).includes(pipelineStatus);
      },
      get isFailed() {
        const arbitrationCompleted = logs.some(l => l.type === 'orchestrator_reconciled');
        return pipelineStatus === PIPELINE_STATUS.ERROR && arbitrationCompleted && !this.isCompleted;
      },
      get isActive() {
        return !this.isCompleted && !this.isFailed && (
          pipelineStatus === PIPELINE_STATUS.ALIGNING ||
          pipelineStatus === PIPELINE_STATUS.SPECIALIST_EXECUTING ||
          pipelineStatus === PIPELINE_STATUS.REVISING
        );
      },
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
        return 'Review & quality check';
      },
      icon: MessageSquare,
      get isCompleted() {
        return (
          [
            PIPELINE_STATUS.AWAITING_HITL,
            PIPELINE_STATUS.EXPORTING,
            PIPELINE_STATUS.EXPORTED,
            PIPELINE_STATUS.REJECTED
          ] as PipelineStatus[]
        ).includes(pipelineStatus);
      },
      get isFailed() {
        const specialistsCompleted = (
          [
            PIPELINE_STATUS.EVALUATING,
            PIPELINE_STATUS.REVISING,
            PIPELINE_STATUS.AWAITING_HITL,
            PIPELINE_STATUS.EXPORTING,
            PIPELINE_STATUS.EXPORTED
          ] as PipelineStatus[]
        ).includes(pipelineStatus);
        return pipelineStatus === PIPELINE_STATUS.ERROR && specialistsCompleted && !this.isCompleted;
      },
      get isActive() {
        return !this.isCompleted && !this.isFailed && (
          pipelineStatus === PIPELINE_STATUS.EVALUATING ||
          pipelineStatus === PIPELINE_STATUS.REVISING
        );
      },
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
      get isCompleted() {
        return (
          pipelineStatus === PIPELINE_STATUS.EXPORTED ||
          pipelineStatus === PIPELINE_STATUS.REJECTED
        );
      },
      get isFailed() {
        return pipelineStatus === PIPELINE_STATUS.EXPORT_FAILED;
      },
      get isActive() {
        return !this.isCompleted && !this.isFailed && (
          pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ||
          pipelineStatus === PIPELINE_STATUS.EXPORTING
        );
      },
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
          PIPELINE_STATUS.SPECIALIST_EXECUTING,
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

  return (
    <div className="w-full bg-card border border-border rounded-xl p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Agentic Workflow Progress</h3>
        <div className="flex items-center gap-2">
          {pipelineStatus !== PIPELINE_STATUS.IDLE && pipelineStatus !== PIPELINE_STATUS.EXPORTED && pipelineStatus !== PIPELINE_STATUS.REJECTED && pipelineStatus !== PIPELINE_STATUS.ERROR && (
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
                    'text-primary'
            }>{pipelineStatus === PIPELINE_STATUS.AWAITING_HITL ? 'awaiting decision' : pipelineStatus === PIPELINE_STATUS.EVALUATING ? 'Evaluating' : pipelineStatus.replace(/_/g, ' ')}</span>
          </span>
        </div>
      </div>

      <div className="relative flex items-start justify-between w-full">
        {/* Connecting progress line */}
        <div className="absolute left-0 right-0 top-6 h-0.5 bg-secondary -z-0" />

        {steps.map((step, idx) => {
          const StepIcon = step.icon;
          const isCompleted = step.isCompleted;
          const isFailed = step.isFailed;
          const isActive = step.isActive;

          // Compute style tokens
          let iconContainerClasses = "w-12 h-12 rounded-full flex items-center justify-center border-2 z-15 transition-all duration-300 ";
          let textLabelClasses = "text-xs font-bold mt-2 transition-colors duration-300 ";
          const descriptionClasses = "text-[10px] text-muted-foreground truncate hidden md:block ";

          if (isCompleted) {
            iconContainerClasses += "bg-success/80 border-success text-success shadow-[0_0_15px_rgba(16,185,129,0.2)]";
            textLabelClasses += "text-success";
          } else if (isFailed) {
            iconContainerClasses += "bg-danger/20 border-danger text-danger shadow-[0_0_15px_rgba(239,68,68,0.2)]";
            textLabelClasses += "text-danger";
          } else if (isActive) {
            iconContainerClasses += "bg-primary/10 border-primary text-primary ring-4 ring-primary/30 animate-pulse shadow-[0_0_20px_rgba(99,102,241,0.4)]";
            textLabelClasses += "text-primary font-extrabold";
          } else {
            iconContainerClasses += "bg-background border-border text-muted-foreground";
            textLabelClasses += "text-muted-foreground";
          }

          return (
            <div key={step.id} className="flex flex-col items-center flex-1 relative z-10">
              {/* Line connector segment highlight */}
              {idx > 0 && (
                <div
                  className={`absolute left-[-50%] right-[50%] top-6 h-0.5 -z-10 transition-all duration-500 ${
                    steps[idx - 1].isCompleted
                      ? 'bg-gradient-to-r from-success to-primary'
                      : steps[idx - 1].isFailed
                      ? 'bg-gradient-to-r from-danger to-secondary'
                      : 'bg-secondary'
                  }`}
                />
              )}

              <div className={iconContainerClasses}>
                {isCompleted ? (
                  <Check size={20} className="stroke-[3px] animate-scale-in" />
                ) : isFailed ? (
                  <X size={20} className="stroke-[3px] animate-scale-in text-danger" />
                ) : isActive ? (
                  <Loader2 size={20} className="animate-spin text-primary" />
                ) : (
                  <StepIcon size={18} />
                )}
              </div>
              <span className={textLabelClasses}>{step.label}</span>
              <span className={descriptionClasses}>{step.description}</span>

              {/* Specialist status nested for Step 3 (Pass 1) and Step 5 (Pass 2) */}
              {(step.id === 3 || step.id === 5) && pipelineStatus !== 'idle' && (
                <div className="mt-4 flex flex-col gap-2 w-full max-w-[140px] z-20 animate-scale-in">
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

                      if (status === 'completed') {
                        specCardClass += "bg-success/20 border-success/40 text-success";
                        statusIcon = <Check size={8} className="stroke-[3px] text-success shrink-0" />;
                      } else if (status === 'running') {
                        specCardClass += "bg-primary/10 border-primary/40 text-primary ring-1 ring-primary/10 animate-pulse";
                        statusIcon = <Loader2 size={8} className="animate-spin text-primary shrink-0" />;
                      } else if (status === 'failed') {
                        specCardClass += "bg-danger/20 border-danger/40 text-danger";
                        statusIcon = <X size={8} className="stroke-[3px] text-danger shrink-0" />;
                      } else {
                        specCardClass += "bg-card/40 border-border/40 text-muted-foreground";
                        statusIcon = <div className="h-1 w-1 rounded-full bg-secondary shrink-0" />;
                      }

                      return (
                        <div key={spec.key} className={specCardClass} title={spec.key}>
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
                <div className="mt-2 flex flex-col gap-1.5 w-full max-w-[140px] z-20 animate-scale-in">
                  {pipelineStatus === PIPELINE_STATUS.ARBITRATING && (
                    <div className="px-2 py-1 rounded bg-warning/15 border border-warning/35 text-[8px] text-warning font-semibold text-center animate-pulse">
                      EM Reconciling Drafts...
                    </div>
                  )}
                  {(artifacts?.alignment_memo || logs.some(l => l.type === 'orchestrator_reconciled')) && (
                    <div className="px-2.5 py-1.5 rounded-lg border border-warning/30 bg-warning/10 text-[9px] text-warning-foreground font-semibold flex flex-col gap-1 text-center">
                      <span>Pass 2: {artifacts?.alignment_memo?.directives?.length || logs.find(l => l.type === 'orchestrator_reconciled')?.directive_count || 0} Directives</span>
                      {artifacts?.alignment_memo?.overall_strategy && (
                        <span className="text-[7.5px] opacity-80 line-clamp-2 italic font-normal text-warning-foreground">
                          "{artifacts.alignment_memo.overall_strategy}"
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Critic revision indicator under step 6 */}
              {step.id === 6 && (
                <div className="mt-2 flex flex-col gap-1.5 w-full max-w-[140px] z-20 animate-scale-in">
                  {logs.filter(l => l.type === 'revision_start').length > 0 && (
                    <div className="px-2 py-1 rounded bg-primary/10 border border-primary/30 text-[8px] text-primary font-bold text-center animate-pulse">
                      🔄 {logs.filter(l => l.type === 'revision_start').length} Revision(s) taken
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

