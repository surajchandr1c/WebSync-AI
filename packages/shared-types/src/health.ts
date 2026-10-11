export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'down';
  service: string;
  version: string;
  timestamp: string;
  uptime_seconds: number;
  python_version: string;
  environment: string;
}
