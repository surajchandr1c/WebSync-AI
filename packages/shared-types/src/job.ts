export type JobStatus = 'queued' | 'scheduled' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobRequirements {
  min_cpu_cores: number;
  min_ram_mb: number;
  gpu_required: boolean;
}

export interface JobSubmission {
  name: string;
  runtime: 'python' | 'shell';
  entrypoint?: string;
  script_content: string;
  requirements: JobRequirements;
  timeout_seconds?: number;
}

export interface JobSummary {
  job_id: string;
  name: string;
  status: JobStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  assigned_worker_id?: string;
  exit_code?: number;
}
