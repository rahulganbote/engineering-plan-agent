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
