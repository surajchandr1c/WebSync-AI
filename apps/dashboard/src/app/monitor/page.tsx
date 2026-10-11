'use client';

import React from 'react';
import { useCluster } from '@/context/ClusterContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Activity,
  Cpu,
  HardDrive,
  Zap,
  Server,
  RefreshCw,
  Clock,
  Radio,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';

export default function ResourceMonitorPage() {
  const { workers, telemetryHistory, lastSync, refreshWorkers } = useCluster();

  const onlineWorkers = workers.filter(
    (w) => w.connection_status === 'online' || w.connection_status === 'busy'
  );

  const totalPooledRamBytes = workers.reduce((sum, w) => sum + (w.total_ram_bytes || 0), 0);
  const availPooledRamBytes = workers.reduce((sum, w) => sum + (w.available_ram_bytes || 0), 0);
  const usedPooledRamBytes = Math.max(0, totalPooledRamBytes - availPooledRamBytes);
  const totalPooledRamGb = (totalPooledRamBytes / (1024 * 1024 * 1024)).toFixed(1);
  const usedPooledRamGb = (usedPooledRamBytes / (1024 * 1024 * 1024)).toFixed(1);
  const availPooledRamGb = (availPooledRamBytes / (1024 * 1024 * 1024)).toFixed(1);
  const ramUsagePercent =
    totalPooledRamBytes > 0 ? Math.round((usedPooledRamBytes / totalPooledRamBytes) * 100) : 0;

  const avgCpu =
    onlineWorkers.length > 0
      ? (
          onlineWorkers.reduce((sum, w) => sum + (w.cpu_utilization || 0), 0) /
          onlineWorkers.length
        ).toFixed(1)
      : '0.0';

  const gpuWorkers = workers.filter((w) => w.gpu_available && w.gpu_metadata.length > 0);

  // SVG Chart Dimensions
  const chartWidth = 700;
  const chartHeight = 160;
  const padding = 20;

  const cpuPoints = telemetryHistory.map((pt, idx) => {
    const x = padding + (idx / Math.max(1, telemetryHistory.length - 1)) * (chartWidth - 2 * padding);
    const y = chartHeight - padding - (pt.avgCpu / 100) * (chartHeight - 2 * padding);
    return `${x},${y}`;
  });

  const getFreshnessStatus = (isoString?: string | null) => {
    if (!isoString) return { label: 'No Data', variant: 'neutral' as const };
    const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diff <= 10) return { label: 'Fresh (<10s)', variant: 'success' as const };
    if (diff <= 30) return { label: 'Normal (10-30s)', variant: 'info' as const };
    if (diff <= 60) return { label: 'Degraded (>30s)', variant: 'warning' as const };
    return { label: 'Stale / Offline', variant: 'danger' as const };
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Live Resource Monitor
            </h1>
            <Badge variant="success" className="flex items-center space-x-1">
              <Radio className="w-3 h-3 animate-pulse text-emerald-400" />
              <span>psutil Live Stream</span>
            </Badge>
          </div>
          <p className="text-gray-400 text-sm max-w-2xl">
            Real-time telemetry showing aggregated cluster compute load, memory consumption, and GPU metrics.
          </p>
        </div>

        <div className="flex items-center space-x-3 text-xs text-gray-400 font-mono">
          <span>Synced: {lastSync ? lastSync.toLocaleTimeString() : 'Connecting...'}</span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refreshWorkers()}
            className="h-8 px-2.5"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Poll Metrics
          </Button>
        </div>
      </div>

      {/* Aggregate Cluster Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* CPU Load Gauge */}
        <Card className="bg-gradient-to-br from-[#111827] to-[#0e172a]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center space-x-1.5">
              <Cpu className="w-4 h-4 text-blue-400" />
              <span>Pooled CPU Load</span>
            </span>
            <span className="text-xs font-mono text-gray-400">
              {onlineWorkers.length} Active Nodes
            </span>
          </div>

          <div className="flex items-baseline space-x-3 mb-2">
            <span className="text-4xl font-extrabold text-white tracking-tight">{avgCpu}%</span>
            <span className="text-xs text-gray-400">cluster average</span>
          </div>

          <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                Number(avgCpu) > 80
                  ? 'bg-rose-500'
                  : Number(avgCpu) > 50
                  ? 'bg-amber-500'
                  : 'bg-blue-500'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, Number(avgCpu)))}%` }}
            />
          </div>
          <p className="text-[11px] text-gray-500 mt-2">
            Non-blocking psutil metrics polled across all registered agents.
          </p>
        </Card>

        {/* Pooled Memory Gauge */}
        <Card className="bg-gradient-to-br from-[#111827] to-[#0e172a]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center space-x-1.5">
              <HardDrive className="w-4 h-4 text-indigo-400" />
              <span>Pooled RAM Capacity</span>
            </span>
            <span className="text-xs font-mono text-gray-400">{ramUsagePercent}% Used</span>
          </div>

          <div className="flex items-baseline space-x-3 mb-2">
            <span className="text-4xl font-extrabold text-white tracking-tight">
              {usedPooledRamGb}
            </span>
            <span className="text-xs text-gray-400">/ {totalPooledRamGb} GB Used</span>
          </div>

          <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden">
            <div
              className="bg-indigo-500 h-full transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, ramUsagePercent))}%` }}
            />
          </div>
          <p className="text-[11px] text-gray-500 mt-2">
            {availPooledRamGb} GB free and ready for dispatched workloads.
          </p>
        </Card>

        {/* GPU Accelerators */}
        <Card className="bg-gradient-to-br from-[#111827] to-[#0e172a]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center space-x-1.5">
              <Zap className="w-4 h-4 text-amber-400" />
              <span>GPU Accelerators</span>
            </span>
            <Badge variant={gpuWorkers.length > 0 ? 'success' : 'neutral'}>
              {gpuWorkers.length > 0 ? 'Active' : 'No GPU'}
            </Badge>
          </div>

          <div className="flex items-baseline space-x-3 mb-2">
            <span className="text-4xl font-extrabold text-white tracking-tight">
              {gpuWorkers.length}
            </span>
            <span className="text-xs text-gray-400">GPU-enabled nodes</span>
          </div>

          <div className="text-[11px] text-gray-400 space-y-1 mt-2 pt-2 border-t border-[#1f2937]">
            {gpuWorkers.length > 0 ? (
              gpuWorkers.map((w) => (
                <div key={w.worker_id} className="truncate">
                  {w.display_name}:{' '}
                  <span className="text-amber-300 font-mono">
                    {w.gpu_metadata[0]?.name || 'GPU Device'}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-gray-500">
                Nodes report GPU hardware via NVML / torch when present.
              </p>
            )}
          </div>
        </Card>
      </div>

      {/* Real-time Telemetry Trend Chart */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div>
            <CardTitle>Cluster CPU Load Trend</CardTitle>
            <p className="text-xs text-gray-400 mt-0.5">
              Time-series tracking of cluster average CPU utilization as heartbeats arrive ({telemetryHistory.length} samples).
            </p>
          </div>
          <Badge variant="info">Time-Series (0-100%)</Badge>
        </CardHeader>

        <CardContent>
          <div className="bg-[#090d16] border border-[#1f2937] rounded-xl p-4">
            {telemetryHistory.length <= 1 ? (
              <div className="h-40 flex items-center justify-center text-xs text-gray-500">
                Collecting heartbeat telemetry samples... Please wait a few seconds.
              </div>
            ) : (
              <div className="space-y-2">
                <svg
                  viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                  className="w-full h-44 overflow-visible"
                >
                  {/* Grid Lines */}
                  {[0, 25, 50, 75, 100].map((level) => {
                    const y = chartHeight - padding - (level / 100) * (chartHeight - 2 * padding);
                    return (
                      <g key={level}>
                        <line
                          x1={padding}
                          y1={y}
                          x2={chartWidth - padding}
                          y2={y}
                          stroke="#1f2937"
                          strokeDasharray="4 4"
                          strokeWidth="1"
                        />
                        <text
                          x={padding - 5}
                          y={y + 3}
                          fill="#6b7280"
                          fontSize="9"
                          textAnchor="end"
                          fontFamily="monospace"
                        >
                          {level}%
                        </text>
                      </g>
                    );
                  })}

                  {/* Gradient Area under curve */}
                  <defs>
                    <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Fill Polygon */}
                  <polygon
                    points={`${padding},${chartHeight - padding} ${cpuPoints.join(' ')} ${chartWidth - padding},${chartHeight - padding}`}
                    fill="url(#cpuGradient)"
                  />

                  {/* Polyline */}
                  <polyline
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={cpuPoints.join(' ')}
                  />

                  {/* Highlight recent point */}
                  {cpuPoints.length > 0 && (
                    <circle
                      cx={cpuPoints[cpuPoints.length - 1].split(',')[0]}
                      cy={cpuPoints[cpuPoints.length - 1].split(',')[1]}
                      r="4"
                      fill="#60a5fa"
                      stroke="#1e3a8a"
                      strokeWidth="2"
                    />
                  )}
                </svg>

                {/* X-axis labels */}
                <div className="flex justify-between text-[10px] text-gray-500 font-mono px-4">
                  <span>{telemetryHistory[0]?.timeLabel || 'Start'}</span>
                  <span>Latest: {telemetryHistory[telemetryHistory.length - 1]?.timeLabel || 'Now'}</span>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Node Telemetry & Heartbeat Freshness Table */}
      <Card className="overflow-hidden p-0">
        <div className="p-4 border-b border-[#1f2937] flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Worker Heartbeat Freshness</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Live psutil health per worker to guarantee no synthetic or stale metrics.
            </p>
          </div>
          <span className="text-xs font-mono text-gray-400">
            {workers.length} Total Registered Nodes
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-gray-300">
            <thead className="bg-[#0b101a] border-b border-[#1f2937] text-gray-400 uppercase text-[10px] tracking-wider font-semibold">
              <tr>
                <th className="py-3 px-4">Node / Hostname</th>
                <th className="py-3 px-4">Platform</th>
                <th className="py-3 px-4">CPU Utilization</th>
                <th className="py-3 px-4">Available RAM</th>
                <th className="py-3 px-4">Concurrency</th>
                <th className="py-3 px-4">Last Ping</th>
                <th className="py-3 px-4 text-right">Freshness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1f2937]">
              {workers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-gray-500 italic">
                    No worker nodes currently registered.
                  </td>
                </tr>
              ) : (
                workers.map((worker) => {
                  const freshness = getFreshnessStatus(worker.last_heartbeat);
                  const totalRamGb = (worker.total_ram_bytes / (1024 * 1024 * 1024)).toFixed(1);
                  const availRamGb = (worker.available_ram_bytes / (1024 * 1024 * 1024)).toFixed(1);

                  return (
                    <tr key={worker.worker_id} className="hover:bg-[#151f33] transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-white">{worker.display_name}</div>
                        <div className="text-[10px] text-gray-500 font-mono">{worker.hostname}</div>
                      </td>

                      <td className="py-3 px-4 font-mono text-gray-300">{worker.platform}</td>

                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2">
                          <div className="w-16 bg-gray-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className="bg-blue-500 h-full"
                              style={{
                                width: `${Math.min(100, Math.max(0, worker.cpu_utilization))}%`,
                              }}
                            />
                          </div>
                          <span className="font-mono text-white">
                            {worker.cpu_utilization.toFixed(1)}%
                          </span>
                        </div>
                      </td>

                      <td className="py-3 px-4 font-mono">
                        {availRamGb} GB / {totalRamGb} GB
                      </td>

                      <td className="py-3 px-4 font-mono">
                        {worker.active_job_count} / {worker.max_concurrent_jobs}
                      </td>

                      <td className="py-3 px-4 text-gray-400 font-mono">
                        {worker.last_heartbeat
                          ? new Date(worker.last_heartbeat).toLocaleTimeString()
                          : 'None'}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <Badge variant={freshness.variant}>{freshness.label}</Badge>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
