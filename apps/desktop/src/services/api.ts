import { Worker, Job } from '../types';

export interface UrlValidationResult {
  isValid: boolean;
  isSecure: boolean;
  isLocalhost: boolean;
  errorMessage?: string;
}

export function validateCoordinatorUrl(urlString: string): UrlValidationResult {
  if (!urlString || typeof urlString !== 'string') {
    return { isValid: false, isSecure: false, isLocalhost: false, errorMessage: 'URL cannot be empty' };
  }

  try {
    const parsed = new URL(urlString.trim());
    const protocol = parsed.protocol.toLowerCase();
    const hostname = parsed.hostname.toLowerCase();

    const isLocal =
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname === '::1' ||
      hostname.startsWith('127.');

    const isHttps = protocol === 'https:' || protocol === 'wss:';
    const isHttp = protocol === 'http:' || protocol === 'ws:';

    if (!isHttps && !isHttp) {
      return {
        isValid: false,
        isSecure: false,
        isLocalhost: isLocal,
        errorMessage: `Unsupported protocol: "${protocol}". Must use HTTP/HTTPS or WS/WSS.`,
      };
    }

    if (!isLocal && !isHttps) {
      return {
        isValid: false,
        isSecure: false,
        isLocalhost: false,
        errorMessage:
          'Security Policy Violation: Remote coordinator URLs must use HTTPS or WSS. Plain HTTP/WS is only permitted for localhost development.',
      };
    }

    return {
      isValid: true,
      isSecure: isHttps,
      isLocalhost: isLocal,
    };
  } catch (err: any) {
    return {
      isValid: false,
      isSecure: false,
      isLocalhost: false,
      errorMessage: `Invalid URL format: ${err.message || 'Unable to parse URL'}`,
    };
  }
}

export class CoordinatorApiClient {
  private baseUrl: string;
  private token: string;

  constructor(baseUrl: string, token: string = '') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.token = token;
  }

  setBaseUrl(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  setToken(token: string) {
    this.token = token;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
      headers['X-Worker-Token'] = this.token;
    }
    return headers;
  }

  async testHealth(): Promise<{ ok: boolean; status: string; latencyMs: number; error?: string }> {
    const validation = validateCoordinatorUrl(this.baseUrl);
    if (!validation.isValid) {
      return { ok: false, status: 'invalid_url', latencyMs: 0, error: validation.errorMessage };
    }

    const start = performance.now();
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: this.getHeaders(),
        signal: AbortSignal.timeout(5000),
      });

      const latencyMs = Math.round(performance.now() - start);
      if (response.ok) {
        const data = await response.json().catch(() => ({}));
        return { ok: true, status: data.status || 'healthy', latencyMs };
      } else {
        return {
          ok: false,
          status: `HTTP ${response.status}`,
          latencyMs,
          error: `Server responded with HTTP status ${response.status}`,
        };
      }
    } catch (err: any) {
      const latencyMs = Math.round(performance.now() - start);
      return { ok: false, status: 'error', latencyMs, error: err.message || 'Connection refused or timed out' };
    }
  }

  async getWorkers(): Promise<Worker[]> {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/workers`, {
        headers: this.getHeaders(),
        signal: AbortSignal.timeout(6000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.workers || [];
      return list.map((w: any) => ({
        id: w.id || w.worker_id,
        name: w.name || w.hostname || `Worker-${w.id?.slice(0, 6)}`,
        hostname: w.hostname || 'unknown',
        ip_address: w.ip_address || w.ip,
        platform: w.platform || 'windows',
        cpu_arch: w.cpu_arch || 'x86_64',
        cpu_cores_physical: w.cpu_cores_physical || w.cores_physical || 4,
        cpu_cores_logical: w.cpu_cores_logical || w.cores_logical || 8,
        total_memory_bytes: w.total_memory_bytes || (w.total_memory_gb ? w.total_memory_gb * 1024 ** 3 : 16 * 1024 ** 3),
        gpu_info: w.gpu_info || (w.gpu_name ? { name: w.gpu_name, total_memory_bytes: (w.gpu_memory_gb || 4) * 1024 ** 3 } : undefined),
        status: w.status || 'online',
        last_heartbeat: w.last_heartbeat || new Date().toISOString(),
        telemetry: w.telemetry || {
          cpu_percent: w.cpu_percent || 0,
          memory_percent: w.memory_percent || 0,
          memory_used_gb: w.memory_used_gb || 0,
          memory_total_gb: (w.total_memory_bytes || 16 * 1024 ** 3) / 1024 ** 3,
          active_jobs_count: w.active_jobs_count || 0,
          timestamp: new Date().toISOString(),
        },
        labels: w.labels || {},
      }));
    } catch (err) {
      console.warn('Failed to fetch workers from coordinator:', err);
      return [];
    }
  }

  async getJobs(): Promise<Job[]> {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/jobs`, {
        headers: this.getHeaders(),
        signal: AbortSignal.timeout(6000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      const list = Array.isArray(data) ? data : data.jobs || [];
      return list.map((j: any) => ({
        id: j.id || j.job_id,
        title: j.title || j.name || `${j.task_type || 'Job'} #${(j.id || '').slice(0, 8)}`,
        task_type: j.task_type || 'compute',
        status: j.status || 'pending',
        assigned_worker_id: j.assigned_worker_id || j.worker_id,
        assigned_worker_name: j.assigned_worker_name,
        requirements: j.requirements,
        payload: j.payload,
        result: j.result,
        error_message: j.error_message || j.error,
        created_at: j.created_at || new Date().toISOString(),
        started_at: j.started_at,
        completed_at: j.completed_at,
        priority: j.priority || 1,
        timeout_seconds: j.timeout_seconds || 300,
      }));
    } catch (err) {
      console.warn('Failed to fetch jobs from coordinator:', err);
      return [];
    }
  }

  async createJob(payload: {
    task_type: string;
    payload?: Record<string, any>;
    requirements?: Record<string, any>;
    priority?: number;
    timeout_seconds?: number;
  }): Promise<Job> {
    const res = await fetch(`${this.baseUrl}/api/v1/jobs`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to create job: HTTP ${res.status}`);
    }
    return res.json();
  }

  async cancelJob(jobId: string): Promise<boolean> {
    const res = await fetch(`${this.baseUrl}/api/v1/jobs/${jobId}/cancel`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return res.ok;
  }

  async revokeWorker(workerId: string): Promise<boolean> {
    const res = await fetch(`${this.baseUrl}/api/v1/workers/${workerId}/revoke`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return res.ok;
  }
}
