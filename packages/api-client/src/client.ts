import {
  HealthResponse,
  WorkerRegistrationPayload,
  WorkerResponse,
  WorkerListResponse,
  JobCreateRequest,
  JobResponse,
  JobListResponse,
  JobResultResponse,
  JobEventListResponse,
} from '@websync/shared-types';

export interface WebSyncClientConfig {
  baseUrl: string;
  authToken?: string;
  timeoutMs?: number;
}

export interface ListWorkersParams {
  status?: string;
  page?: number;
  page_size?: number;
}

export interface ListJobsParams {
  status?: string;
  job_type?: string;
  page?: number;
  page_size?: number;
}

export interface ListEventsParams {
  job_id?: string;
  event_type?: string;
  page?: number;
  page_size?: number;
}

export class WebSyncClient {
  private baseUrl: string;
  private authToken?: string;
  private timeoutMs: number;

  constructor(config: WebSyncClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, '');
    this.authToken = config.authToken;
    this.timeoutMs = config.timeoutMs || 10000;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const headers = new Headers(options.headers || {});

    headers.set('Accept', 'application/json');
    if (!headers.has('Content-Type') && options.body) {
      headers.set('Content-Type', 'application/json');
    }
    if (this.authToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${this.authToken}`);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        let errorDetails = '';
        try {
          const errJson = await response.json();
          errorDetails = typeof errJson === 'object' && errJson.detail ? errJson.detail : JSON.stringify(errJson);
        } catch {
          errorDetails = response.statusText;
        }
        throw new Error(`API error [${response.status}]: ${errorDetails}`);
      }

      return (await response.json()) as T;
    } finally {
      clearTimeout(timeout);
    }
  }

  /**
   * Check coordinator health and operational metadata.
   */
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/v1/health');
  }

  /**
   * List all registered workers.
   */
  async listWorkers(params?: ListWorkersParams): Promise<WorkerListResponse> {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString();
    return this.request<WorkerListResponse>(`/api/v1/workers${qs ? `?${qs}` : ''}`);
  }

  /**
   * Get specific worker details.
   */
  async getWorker(workerId: string): Promise<WorkerResponse> {
    return this.request<WorkerResponse>(`/api/v1/workers/${encodeURIComponent(workerId)}`);
  }

  /**
   * Disconnect or mark worker as offline.
   */
  async disconnectWorker(workerId: string): Promise<WorkerResponse> {
    return this.request<WorkerResponse>(`/api/v1/workers/${encodeURIComponent(workerId)}/disconnect`, {
      method: 'POST',
    });
  }

  /**
   * Register a new worker node.
   */
  async registerWorker(payload: WorkerRegistrationPayload): Promise<WorkerResponse> {
    return this.request<WorkerResponse>('/api/v1/workers/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  /**
   * List computational jobs with optional filtering and pagination.
   */
  async listJobs(params?: ListJobsParams): Promise<JobListResponse> {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.job_type) query.append('job_type', params.job_type);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString();
    return this.request<JobListResponse>(`/api/v1/jobs${qs ? `?${qs}` : ''}`);
  }

  /**
   * Retrieve a specific job by ID.
   */
  async getJob(jobId: string): Promise<JobResponse> {
    return this.request<JobResponse>(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
  }

  /**
   * Submit a new computational job for scheduling and dispatch.
   */
  async createJob(payload: JobCreateRequest): Promise<JobResponse> {
    return this.request<JobResponse>('/api/v1/jobs', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  /**
   * Cancel an in-flight or queued job.
   */
  async cancelJob(jobId: string): Promise<JobResponse> {
    return this.request<JobResponse>(`/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: 'POST',
    });
  }

  /**
   * Retrieve completed or failed job execution result.
   */
  async getJobResult(jobId: string): Promise<JobResultResponse> {
    return this.request<JobResultResponse>(`/api/v1/jobs/${encodeURIComponent(jobId)}/result`);
  }

  /**
   * List system-wide audit and lifecycle events.
   */
  async listEvents(params?: ListEventsParams): Promise<JobEventListResponse> {
    const query = new URLSearchParams();
    if (params?.job_id) query.append('job_id', params.job_id);
    if (params?.event_type) query.append('event_type', params.event_type);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString();
    return this.request<JobEventListResponse>(`/api/v1/events${qs ? `?${qs}` : ''}`);
  }

  /**
   * List audit events for a specific job.
   */
  async getJobEvents(jobId: string, params?: { page?: number; page_size?: number }): Promise<JobEventListResponse> {
    const query = new URLSearchParams();
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString();
    return this.request<JobEventListResponse>(`/api/v1/jobs/${encodeURIComponent(jobId)}/events${qs ? `?${qs}` : ''}`);
  }
}
