'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useCluster } from '@/context/ClusterContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { SubmitJobModal } from '@/components/jobs/SubmitJobModal';
import { JobResultModal } from '@/components/jobs/JobResultModal';
import { EnrollWorkerModal } from '@/components/workers/EnrollWorkerModal';
import { WorkerDetailsModal } from '@/components/workers/WorkerDetailsModal';
import { JobResponse, WorkerResponse } from '@websync/shared-types';
import {
  Server,
  PlaySquare,
  Cpu,
  HardDrive,
  Activity,
  ArrowRight,
  Plus,
  Radio,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Sparkles,
} from 'lucide-react';

export default function OverviewPage() {
  const { health, healthError, workers, jobs, isLoading } = useCluster();

  // Modals state
  const [isSubmitJobOpen, setIsSubmitJobOpen] = useState(false);
  const [isEnrollWorkerOpen, setIsEnrollWorkerOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobResponse | null>(null);
  const [selectedWorker, setSelectedWorker] = useState<WorkerResponse | null>(null);

  // Computed metrics
  const onlineWorkers = workers.filter(
    (w) => w.connection_status === 'online' || w.connection_status === 'busy'
  );
  const totalPooledRamBytes = workers.reduce((sum, w) => sum + (w.total_ram_bytes || 0), 0);
  const availPooledRamBytes = workers.reduce((sum, w) => sum + (w.available_ram_bytes || 0), 0);
  const usedPooledRamBytes = Math.max(0, totalPooledRamBytes - availPooledRamBytes);
  const totalPooledRamGb = (totalPooledRamBytes / (1024 * 1024 * 1024)).toFixed(1);
  const usedPooledRamGb = (usedPooledRamBytes / (1024 * 1024 * 1024)).toFixed(1);
  const ramUsagePercent =
    totalPooledRamBytes > 0 ? Math.round((usedPooledRamBytes / totalPooledRamBytes) * 100) : 0;

  const avgCpu =
    onlineWorkers.length > 0
      ? (
          onlineWorkers.reduce((sum, w) => sum + (w.cpu_utilization || 0), 0) /
          onlineWorkers.length
        ).toFixed(1)
      : '0.0';

  const runningJobs = jobs.filter((j) => j.status === 'RUNNING');
  const queuedJobs = jobs.filter((j) => j.status === 'QUEUED' || j.status === 'SCHEDULED');
  const completedJobs = jobs.filter((j) => j.status === 'COMPLETED');
  const failedJobs = jobs.filter((j) => j.status === 'FAILED');

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <Badge variant="success">COMPLETED</Badge>;
      case 'RUNNING':
        return <Badge variant="info">RUNNING</Badge>;
      case 'SCHEDULED':
        return <Badge variant="warning">SCHEDULED</Badge>;
      case 'QUEUED':
        return <Badge variant="neutral">QUEUED</Badge>;
      case 'FAILED':
        return <Badge variant="danger">FAILED</Badge>;
      case 'CANCELLED':
        return <Badge variant="neutral">CANCELLED</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner & Quick Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Cluster Overview
            </h1>
            <Badge variant="info" className="hidden sm:inline-flex">
              WebSync AI Grid
            </Badge>
          </div>
          <p className="text-gray-400 text-sm max-w-2xl">
            Live telemetry, distributed hardware pool, and autonomous scheduler status.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link href="/chat">
            <Button
              variant="secondary"
              size="sm"
              className="flex items-center space-x-1.5 border-blue-500/30 text-blue-300 hover:text-white"
            >
              <Sparkles className="w-4 h-4 text-blue-400" />
              <span>AI Chat Studio</span>
            </Button>
          </Link>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsEnrollWorkerOpen(true)}
            className="flex items-center space-x-1.5"
          >
            <Server className="w-4 h-4 text-gray-400" />
            <span>Enroll Node</span>
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsSubmitJobOpen(true)}
            className="flex items-center space-x-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Submit Job</span>
          </Button>
        </div>
      </div>

      {/* Health / Coordinator Alert Banner if degraded */}
      {healthError && (
        <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-900/50 flex items-center justify-between text-xs text-rose-300">
          <div className="flex items-center space-x-2">
            <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>
              <strong>Coordinator unreachable:</strong> {healthError}. Check that FastAPI is running on port 8000.
            </span>
          </div>
        </div>
      )}

      {/* Cluster Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Workers Metric */}
        <Card className="bg-gradient-to-br from-[#111827] to-[#0e1626]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Connected Nodes
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Server className="w-4 h-4 text-blue-400" />
            </div>
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-white">{onlineWorkers.length}</span>
            <span className="text-xs text-gray-400">/ {workers.length} registered</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 pt-2 border-t border-[#1f2937]">
            <span className="flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
              <span>{onlineWorkers.length} Online</span>
            </span>
            <span>{workers.length - onlineWorkers.length} Offline</span>
          </div>
        </Card>

        {/* Workload / Jobs Metric */}
        <Card className="bg-gradient-to-br from-[#111827] to-[#0e1626]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Active Workloads
            </span>
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <PlaySquare className="w-4 h-4 text-indigo-400" />
            </div>
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-white">
              {runningJobs.length + queuedJobs.length}
            </span>
            <span className="text-xs text-gray-400">in-flight</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 pt-2 border-t border-[#1f2937]">
            <span className="text-blue-400">{runningJobs.length} Running</span>
            <span className="text-amber-400">{queuedJobs.length} Queued</span>
            <span className="text-emerald-400">{completedJobs.length} Done</span>
          </div>
        </Card>

        {/* Pooled RAM Metric */}
        <Card className="bg-gradient-to-br from-[#111827] to-[#0e1626]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Pooled Memory
            </span>
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center">
              <HardDrive className="w-4 h-4 text-cyan-400" />
            </div>
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-white">{totalPooledRamGb}</span>
            <span className="text-xs text-gray-400">GB Pooled RAM</span>
          </div>
          <div className="mt-3 space-y-1 pt-2 border-t border-[#1f2937]">
            <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-cyan-500 h-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, ramUsagePercent))}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-gray-400">
              <span>{usedPooledRamGb} GB Used</span>
              <span>{ramUsagePercent}%</span>
            </div>
          </div>
        </Card>

        {/* Pooled CPU Metric */}
        <Card className="bg-gradient-to-br from-[#111827] to-[#0e1626]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Cluster CPU Load
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Cpu className="w-4 h-4 text-emerald-400" />
            </div>
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-white">{avgCpu}%</span>
            <span className="text-xs text-gray-400">avg utilization</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-gray-400 pt-2 border-t border-[#1f2937]">
            <span>Coordinator: {health?.status === 'healthy' ? 'Active' : 'Unhealthy'}</span>
            <span className="text-emerald-400 font-mono">
              {health?.uptime_seconds ? `${health.uptime_seconds.toFixed(0)}s up` : '—'}
            </span>
          </div>
        </Card>
      </div>

      {/* Two Column Layout: Active Workers Preview + Recent Jobs Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Workers Preview */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Server className="w-4 h-4 text-blue-400" />
              <CardTitle>Worker Fleet Preview</CardTitle>
            </div>
            <Link
              href="/workers"
              className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center space-x-1"
            >
              <span>View All ({workers.length})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardHeader>

          <CardContent>
            {workers.length === 0 ? (
              <div className="text-center py-10 bg-[#0d131f] rounded-lg border border-dashed border-[#1f2937] p-6 space-y-3">
                <Server className="w-8 h-8 text-gray-600 mx-auto" />
                <p className="text-sm text-gray-300 font-medium">No worker nodes registered yet.</p>
                <p className="text-xs text-gray-500 max-w-sm mx-auto">
                  Start a worker agent on Windows, Linux, or macOS to join the cluster.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEnrollWorkerOpen(true)}
                  className="mt-2 text-xs"
                >
                  <Plus className="w-3.5 h-3.5 mr-1" />
                  Enroll First Worker
                </Button>
              </div>
            ) : (
              <div className="space-y-2.5">
                {workers.slice(0, 5).map((w) => {
                  const ramGb = (w.total_ram_bytes / (1024 * 1024 * 1024)).toFixed(1);
                  return (
                    <div
                      key={w.worker_id}
                      onClick={() => setSelectedWorker(w)}
                      className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937] hover:border-blue-500/50 hover:bg-[#11192a] cursor-pointer transition-all flex items-center justify-between text-xs"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-white">{w.display_name}</span>
                          <span className="text-[10px] text-gray-500 font-mono">({w.platform})</span>
                        </div>
                        <div className="text-[11px] text-gray-400">
                          CPU: <strong className="text-gray-200">{w.cpu_utilization.toFixed(1)}%</strong> | RAM:{' '}
                          <strong className="text-gray-200">{ramGb} GB</strong>
                          {w.gpu_available ? (
                            <span className="ml-1.5 text-amber-400 font-medium">• GPU</span>
                          ) : null}
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Badge
                          variant={
                            w.connection_status === 'online'
                              ? 'success'
                              : w.connection_status === 'busy'
                              ? 'warning'
                              : 'danger'
                          }
                        >
                          {w.connection_status}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Jobs Preview */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <PlaySquare className="w-4 h-4 text-indigo-400" />
              <CardTitle>Recent Workloads</CardTitle>
            </div>
            <Link
              href="/jobs"
              className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center space-x-1"
            >
              <span>View All ({jobs.length})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </CardHeader>

          <CardContent>
            {jobs.length === 0 ? (
              <div className="text-center py-10 bg-[#0d131f] rounded-lg border border-dashed border-[#1f2937] p-6 space-y-3">
                <PlaySquare className="w-8 h-8 text-gray-600 mx-auto" />
                <p className="text-sm text-gray-300 font-medium">No computational jobs submitted yet.</p>
                <p className="text-xs text-gray-500 max-w-sm mx-auto">
                  Submit a matrix multiplication or data processing job to execute across the cluster.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsSubmitJobOpen(true)}
                  className="mt-2 text-xs"
                >
                  <Plus className="w-3.5 h-3.5 mr-1" />
                  Submit First Job
                </Button>
              </div>
            ) : (
              <div className="space-y-2.5">
                {jobs.slice(0, 5).map((j) => (
                  <div
                    key={j.job_id}
                    onClick={() => setSelectedJob(j)}
                    className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937] hover:border-blue-500/50 hover:bg-[#11192a] cursor-pointer transition-all flex items-center justify-between text-xs"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-white">{j.name}</span>
                        <span className="text-[10px] text-gray-500 font-mono">{j.job_type}</span>
                      </div>
                      <div className="text-[11px] text-gray-400">
                        Node:{' '}
                        <span className="font-mono text-gray-300">
                          {j.assigned_worker_id ? j.assigned_worker_id.slice(0, 16) : 'Unassigned'}
                        </span>
                        <span className="mx-1.5">•</span>
                        <span>{new Date(j.created_at).toLocaleTimeString()}</span>
                      </div>
                    </div>

                    <div>{getStatusBadge(j.status)}</div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Modals */}
      <SubmitJobModal isOpen={isSubmitJobOpen} onClose={() => setIsSubmitJobOpen(false)} />
      <EnrollWorkerModal isOpen={isEnrollWorkerOpen} onClose={() => setIsEnrollWorkerOpen(false)} />
      <JobResultModal job={selectedJob} isOpen={!!selectedJob} onClose={() => setSelectedJob(null)} />
      <WorkerDetailsModal
        worker={selectedWorker}
        isOpen={!!selectedWorker}
        onClose={() => setSelectedWorker(null)}
      />
    </div>
  );
}
