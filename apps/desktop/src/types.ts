export type TabId =
  | 'overview'
  | 'workers'
  | 'jobs'
  | 'resources'
  | 'logs'
  | 'daemon'
  | 'settings';

export type ConnectionStatus = 'connected' | 'connecting' | 'error' | 'disconnected';

export interface WorkerTelemetry {
  cpu_percent: number;
  memory_percent: number;
  memory_used_gb: number;
  memory_total_gb: number;
  gpu_percent?: number;
  gpu_memory_used_gb?: number;
  gpu_memory_total_gb?: number;
  active_jobs_count: number;
  timestamp: string;
}

export interface WorkerGPUInfo {
  name: string;
  total_memory_bytes: number;
  driver_version?: string;
  cuda_version?: string;
}

export interface Worker {
  id: string;
  name: string;
  hostname: string;
  ip_address?: string;
  platform: 'windows' | 'linux' | 'darwin' | string;
  cpu_arch: string;
  cpu_cores_physical: number;
  cpu_cores_logical: number;
  total_memory_bytes: number;
  gpu_info?: WorkerGPUInfo;
  status: 'online' | 'busy' | 'offline' | 'revoked';
  last_heartbeat: string;
  telemetry?: WorkerTelemetry;
  labels?: Record<string, string>;
}

export interface JobRequirements {
  min_cpu_cores?: number;
  min_memory_bytes?: number;
  require_gpu?: boolean;
  min_gpu_memory_bytes?: number;
  platform?: string;
}

export interface Job {
  id: string;
  title?: string;
  task_type: string;
  status: 'pending' | 'scheduled' | 'running' | 'completed' | 'failed' | 'cancelled';
  assigned_worker_id?: string;
  assigned_worker_name?: string;
  requirements?: JobRequirements;
  payload?: Record<string, any>;
  result?: Record<string, any>;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  priority?: number;
  timeout_seconds?: number;
}

export interface ClusterStats {
  total_workers: number;
  online_workers: number;
  busy_workers: number;
  offline_workers: number;
  total_jobs: number;
  active_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_cpu_cores: number;
  total_memory_gb: number;
  total_gpus: number;
  avg_cpu_percent: number;
  avg_memory_percent: number;
}

export interface SystemLogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success';
  component: 'coordinator' | 'worker' | 'scheduler' | 'desktop' | 'daemon';
  message: string;
  metadata?: Record<string, any>;
}

export interface LocalWorkerStatus {
  running: boolean;
  pid: number | null;
  coordinator_url: string | null;
  worker_id: string | null;
  exit_code: number | null;
  binary_path: string | null;
}

export interface WorkerBinaryInfo {
  found: boolean;
  path: string | null;
  version: string | null;
}

export interface DesktopSettings {
  coordinatorHttpUrl: string;
  coordinatorWsUrl: string;
  authToken: string;
  workerId: string;
  workerName: string;
  autoReconnect: boolean;
  pollIntervalMs: number;
}
