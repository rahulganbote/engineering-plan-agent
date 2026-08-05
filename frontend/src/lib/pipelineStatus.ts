export const PIPELINE_STATUS = {
  IDLE: 'idle',
  SECURITY_CHECK: 'security_check',
  RUNNING: 'running',
  DRAFTING: 'drafting',
  ARBITRATING: 'arbitrating',
  ALIGNING: 'aligning',
  ORCHESTRATOR_ROUTING: 'orchestrator_routing',
  EVALUATING: 'evaluating',
  REVISING: 'revising',
  AWAITING_HITL: 'awaiting_hitl',
  EXPORTING: 'exporting',
  EXPORTED: 'exported',
  REJECTED: 'rejected',
  EXPORT_FAILED: 'export_failed',
  ERROR: 'error',
  CANCELED: 'canceled',
  // Frontend-only/transient statuses
  INITIALIZING: 'initializing',
  STARTED: 'started',
} as const;

export type PipelineStatus = typeof PIPELINE_STATUS[keyof typeof PIPELINE_STATUS];

/**
 * States during which "Cancel Run" is a reasonable action. Excludes terminal
 * states (exported, rejected, error, export_failed), the HITL wait (user
 * should approve or reject, not cancel), and idle. Consumers: TimelineStepper
 * (header link) and AgentWorkspace (sidebar destructive button).
 */
export const CANCELLABLE_STATES: PipelineStatus[] = [
  PIPELINE_STATUS.SECURITY_CHECK,
  PIPELINE_STATUS.RUNNING,
  PIPELINE_STATUS.ORCHESTRATOR_ROUTING,
  PIPELINE_STATUS.DRAFTING,
  PIPELINE_STATUS.ARBITRATING,
  PIPELINE_STATUS.ALIGNING,
  PIPELINE_STATUS.EVALUATING,
  PIPELINE_STATUS.REVISING,
  PIPELINE_STATUS.INITIALIZING,
];
