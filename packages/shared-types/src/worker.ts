import { GPUInfo, GPUMetrics, SystemMetrics } from './metrics';

export type WorkerStatus = 'registered' | 'online' | 'busy' | 'draining' | 'offline';

export interface WorkerCapabilities {
  hostname: string;
  platform: string;
  platform_version: string;
  architecture: string;
  cpu_count_logical: number;
  cpu_count_physical: number;
  total_memory_bytes: number;
  gpu_info: GPUInfo[];
  supported_runtimes: string[];
}

export interface WorkerRegistrationPayload extends WorkerCapabilities {
  worker_id: string;
}

export interface WorkerHeartbeatPayload {
  timestamp: string;
  metrics: SystemMetrics;
  active_jobs_count: number;
  gpu_metrics?: GPUMetrics[];
}

export interface WorkerSummary {
  worker_id: string;
  hostname: string;
  platform: string;
  status: WorkerStatus;
  last_seen?: string;
  latest_metrics?: SystemMetrics;
}
