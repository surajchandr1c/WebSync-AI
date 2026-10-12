export type JobStatus = 'QUEUED' | 'SCHEDULED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export type ApprovedJobType = 'matrix_multiply' | 'data_processing' | 'image_processing' | 'llm_prompt';

export interface JobRequirements {
  min_cpu_cores: number;
  min_ram_mb: number;
  min_ram_bytes?: number;
  gpu_required: boolean;
  timeout_seconds?: number;
  target_worker_id?: string;
  model?: string;
}

export interface JobCreateRequest {
  name: string;
  job_type: ApprovedJobType | string;
  input_payload: Record<string, any>;
  requirements?: Partial<JobRequirements>;
}

export interface JobResponse {
  job_id: string;
  name: string;
  job_type: string;
  status: JobStatus;
  created_by_user_id?: string | null;
  assigned_worker_id?: string | null;
  input_payload: Record<string, any>;
  requirements: Record<string, any>;
  placement_reason?: Record<string, any> | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface JobListResponse {
  items: JobResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobResultResponse {
  job_id: string;
  status: JobStatus;
  result_exit_code?: number | null;
  result_output?: string | null;
  result_duration_seconds?: number | null;
  result_error?: string | null;
  completed_at?: string | null;
}

// Backwards compatibility alias
export type JobSummary = JobResponse;
export type JobSubmission = JobCreateRequest;
