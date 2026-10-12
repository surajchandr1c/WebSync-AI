import { GPUInfo } from './metrics';

export type WorkerStatus = 'registered' | 'online' | 'busy' | 'offline' | 'disconnected';

export interface WorkerResponse {
  worker_id: string;
  display_name: string;
  hostname: string;
  platform: string;
  platform_version: string;
  cpu_utilization: number;
  total_ram_bytes: number;
  available_ram_bytes: number;
  supported_workloads: string[];
  supported_models?: string[];
  gpu_available: boolean;
  gpu_metadata: GPUInfo[];
  active_job_count: number;
  max_concurrent_jobs: number;
  connection_status: WorkerStatus;
  last_heartbeat?: string | null;
  registered_at: string;
  is_revoked: boolean;
}

export interface WorkerListResponse {
  items: WorkerResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface WorkerRegistrationPayload {
  worker_id: string;
  display_name: string;
  hostname: string;
  platform: string;
  platform_version?: string;
  cpu_utilization?: number;
  total_ram_bytes: number;
  available_ram_bytes: number;
  supported_workloads?: string[];
  supported_models?: string[];
  gpu_available?: boolean;
  gpu_metadata?: GPUInfo[];
  max_concurrent_jobs?: number;
}

export interface WorkerRegistrationResponse {
  worker_id: string;
  display_name: string;
  hostname: string;
  platform: string;
  connection_status: string;
  auth_token: string;
  heartbeat_interval_seconds: number;
}

// Backwards compatibility alias
export type WorkerSummary = WorkerResponse;
