export const PIPELINE_STATUS = {
  IDLE: 'idle',
  SECURITY_CHECK: 'security_check',
  RUNNING: 'running',
  SPECIALIST_EXECUTING: 'specialist_executing',
  EVALUATING: 'evaluating',
  REVISING: 'revising',
  AWAITING_HITL: 'awaiting_hitl',
  EXPORTED: 'exported',
  REJECTED: 'rejected',
  EXPORT_FAILED: 'export_failed',
  ERROR: 'error',
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
  PIPELINE_STATUS.SPECIALIST_EXECUTING,
  PIPELINE_STATUS.EVALUATING,
  PIPELINE_STATUS.REVISING,
  PIPELINE_STATUS.INITIALIZING,
];
