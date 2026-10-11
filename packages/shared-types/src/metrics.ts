export interface SystemMetrics {
  cpu_percent: number;
  memory_used_bytes: number;
  memory_available_bytes: number;
  memory_percent: number;
  disk_free_bytes: number;
  disk_percent: number;
}

export interface GPUMetrics {
  utilization_percent: number;
  memory_used_bytes: number;
}

export interface GPUInfo {
  name: string;
  memory_total_bytes: number;
}
