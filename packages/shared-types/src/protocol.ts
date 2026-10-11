export type ProtocolMessageType =
  | 'worker.conn_ack'
  | 'heartbeat'
  | 'heartbeat.ack'
  | 'worker.disconnected'
  | 'job.dispatch'
  | 'job.ack'
  | 'job.started'
  | 'job.progress'
  | 'job.result'
  | 'job.result.ack'
  | 'job.completed'
  | 'job.failed'
  | 'job.cancel'
  | 'job.cancelled'
  | 'worker.connected'
  | 'worker.updated'
  | 'job.created'
  | 'job.scheduled'
  | 'job.requeued'
  | 'protocol.error';

export interface BaseMessageEnvelope<T = Record<string, any>> {
  type: ProtocolMessageType | string;
  message_id: string;
  timestamp: string;
  correlation_id?: string | null;
  job_id?: string | null;
  worker_id?: string | null;
  payload: T;
}

export interface WorkerConnAckPayload {
  worker_id: string;
  heartbeat_interval_seconds: number;
  coordinator_version: string;
  server_time: string;
}

export interface JobDispatchPayload {
  job_id: string;
  job_type: string;
  input_payload: Record<string, any>;
  timeout_seconds: number;
}

export interface JobAckPayload {
  job_id: string;
  accepted: boolean;
  rejection_reason?: string | null;
}

export interface JobProgressPayload {
  job_id: string;
  progress_percent: number;
  message?: string | null;
}

export interface JobResultPayload {
  job_id: string;
  exit_code: number;
  output: string;
  duration_seconds: number;
  error?: string | null;
}

export interface JobCancelPayload {
  job_id: string;
  reason?: string | null;
}

export interface ProtocolErrorPayload {
  error_code: string;
  message: string;
  original_message_id?: string | null;
}
