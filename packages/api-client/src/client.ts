import {
  HealthResponse,
  WorkerRegistrationPayload,
  WorkerSummary,
} from '@websync/shared-types';

export interface WebSyncClientConfig {
  baseUrl: string;
  authToken?: string;
  timeoutMs?: number;
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
          errorDetails = JSON.stringify(errJson);
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
  async listWorkers(): Promise<WorkerSummary[]> {
    return this.request<WorkerSummary[]>('/api/v1/workers');
  }

  /**
   * Register a new worker node.
   */
  async registerWorker(payload: WorkerRegistrationPayload): Promise<WorkerSummary> {
    return this.request<WorkerSummary>('/api/v1/workers/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}
