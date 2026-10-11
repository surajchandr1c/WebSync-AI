'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

interface HealthData {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  uptime_seconds: number;
  python_version: string;
  environment: string;
  database: 'healthy' | 'unhealthy';
}

export function ConnectionStatus() {
  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const coordinatorUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${coordinatorUrl}/api/v1/health`, {
        cache: 'no-store',
      });
      if (!res.ok) {
        throw new Error(`Coordinator returned HTTP ${res.status}`);
      }
      const json: HealthData = await res.json();
      setData(json);
      setLastChecked(new Date());
    } catch (err: unknown) {
      setData(null);
      setError(err instanceof Error ? err.message : 'Failed to connect to coordinator service');
      setLastChecked(new Date());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    // Poll every 15 seconds
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Card className="border-blue-900/40 bg-gradient-to-br from-[#111827] to-[#0d1527]">
      <CardHeader>
        <div className="flex items-center space-x-3">
          <div className="w-3 h-3 rounded-full relative">
            <span
              className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                loading
                  ? 'bg-amber-400 animate-ping'
                  : data && data.status === 'healthy'
                  ? 'bg-emerald-400 animate-ping'
                  : 'bg-rose-400 animate-pulse'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-3 w-3 ${
                loading
                  ? 'bg-amber-500'
                  : data && data.status === 'healthy'
                  ? 'bg-emerald-500'
                  : 'bg-rose-500'
              }`}
            />
          </div>
          <div>
            <CardTitle>Coordinator API Connection</CardTitle>
            <p className="text-xs text-gray-400">Target: http://localhost:8000/api/v1/health</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {loading && <Badge variant="warning">Checking...</Badge>}
          {!loading && data && data.status === 'healthy' && (
            <Badge variant="success">Connected & Healthy</Badge>
          )}
          {!loading && data && data.status === 'degraded' && (
            <Badge variant="warning">Degraded (DB Unhealthy)</Badge>
          )}
          {!loading && error && <Badge variant="danger">Disconnected</Badge>}
          <Button variant="secondary" size="sm" onClick={fetchHealth} disabled={loading}>
            Ping API
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {data ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 pt-2">
            <div className="bg-[#161f33] p-3 rounded-lg border border-blue-900/30">
              <span className="text-xs text-gray-400 block">Service</span>
              <span className="text-sm font-semibold text-white truncate block">{data.service}</span>
              <span className="text-[11px] text-blue-400">v{data.version}</span>
            </div>

            <div className="bg-[#161f33] p-3 rounded-lg border border-blue-900/30">
              <span className="text-xs text-gray-400 block">Reported Uptime</span>
              <span className="text-sm font-semibold text-emerald-400 font-mono">
                {data.uptime_seconds.toFixed(1)}s
              </span>
              <span className="text-[11px] text-gray-500 block">Live session</span>
            </div>

            <div className="bg-[#161f33] p-3 rounded-lg border border-blue-900/30">
              <span className="text-xs text-gray-400 block">Database</span>
              <span
                className={`text-sm font-semibold font-mono ${
                  data.database === 'healthy' ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {data.database === 'healthy' ? 'Connected' : 'Unhealthy'}
              </span>
              <span className="text-[11px] text-gray-500 block">SQLAlchemy</span>
            </div>

            <div className="bg-[#161f33] p-3 rounded-lg border border-blue-900/30">
              <span className="text-xs text-gray-400 block">Coordinator Runtime</span>
              <span className="text-sm font-semibold text-gray-200 font-mono">
                Python {data.python_version}
              </span>
              <span className="text-[11px] text-gray-500 block">FastAPI</span>
            </div>

            <div className="bg-[#161f33] p-3 rounded-lg border border-blue-900/30">
              <span className="text-xs text-gray-400 block">Environment</span>
              <span className="text-sm font-semibold text-amber-400 capitalize">{data.environment}</span>
              <span className="text-[11px] text-gray-500 block">
                {lastChecked ? lastChecked.toLocaleTimeString() : 'N/A'}
              </span>
            </div>
          </div>
        ) : (
          <div className="bg-rose-950/20 border border-rose-900/30 rounded-lg p-4 mt-2">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-rose-300 font-medium">
                  Coordinator service is currently unreachable on port 8000.
                </p>
                <p className="text-xs text-rose-400/80 mt-1">
                  Start the backend coordinator with:{' '}
                  <code className="bg-black/50 px-2 py-0.5 rounded text-rose-200 font-mono">
                    python services/coordinator/src/coordinator/main.py
                  </code>
                </p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
