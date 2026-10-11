'use client';

import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useCluster } from '@/context/ClusterContext';
import { WorkerResponse } from '@websync/shared-types';
import { Server, Cpu, HardDrive, Zap, PowerOff, ShieldCheck } from 'lucide-react';

interface WorkerDetailsModalProps {
  worker: WorkerResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function WorkerDetailsModal({ worker, isOpen, onClose }: WorkerDetailsModalProps) {
  const { client, refreshWorkers } = useCluster();
  const [disconnecting, setDisconnecting] = useState<boolean>(false);

  if (!worker) return null;

  const totalRamGb = (worker.total_ram_bytes / (1024 * 1024 * 1024)).toFixed(1);
  const availRamGb = (worker.available_ram_bytes / (1024 * 1024 * 1024)).toFixed(1);
  const usedRamGb = (
    Math.max(0, worker.total_ram_bytes - worker.available_ram_bytes) /
    (1024 * 1024 * 1024)
  ).toFixed(1);
  const ramUsagePercent =
    worker.total_ram_bytes > 0
      ? Math.round(
          ((worker.total_ram_bytes - worker.available_ram_bytes) / worker.total_ram_bytes) * 100
        )
      : 0;

  const handleDisconnect = async () => {
    if (!confirm(`Are you sure you want to disconnect worker node "${worker.display_name}"?`)) {
      return;
    }
    setDisconnecting(true);
    try {
      await client.disconnectWorker(worker.worker_id);
      await refreshWorkers();
      onClose();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to disconnect worker');
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center space-x-2">
          <Server className="w-5 h-5 text-blue-400" />
          <span>{worker.display_name}</span>
          <Badge
            variant={
              worker.connection_status === 'online'
                ? 'success'
                : worker.connection_status === 'busy'
                ? 'warning'
                : 'danger'
            }
          >
            {worker.connection_status.toUpperCase()}
          </Badge>
        </div>
      }
      description={`Worker Node: ${worker.worker_id}`}
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4 text-xs">
        {/* Hardware & OS Specs */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 bg-[#0d131f] p-4 rounded-lg border border-[#1f2937]">
          <div>
            <span className="text-gray-400 block mb-0.5">Operating System</span>
            <span className="font-semibold text-white">
              {worker.platform} {worker.platform_version ? `(${worker.platform_version})` : ''}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Hostname</span>
            <span className="font-mono text-gray-200">{worker.hostname}</span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Concurrency Limit</span>
            <span className="text-white font-medium">
              {worker.active_job_count} / {worker.max_concurrent_jobs} Slots Active
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Last Heartbeat</span>
            <span className="text-gray-300">
              {worker.last_heartbeat
                ? new Date(worker.last_heartbeat).toLocaleTimeString()
                : 'None received'}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Enrolled At</span>
            <span className="text-gray-300">
              {new Date(worker.registered_at).toLocaleDateString()}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Security Token</span>
            <span className="text-emerald-400 font-medium flex items-center space-x-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Verified Agent</span>
            </span>
          </div>
        </div>

        {/* Live Resource Utilization Gauges */}
        <div className="p-4 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-3">
          <span className="font-semibold text-gray-300 uppercase tracking-wider block text-[11px]">
            Live Telemetry (Authentic psutil metrics)
          </span>

          {/* CPU Bar */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="flex items-center space-x-1 text-gray-300">
                <Cpu className="w-3.5 h-3.5 text-blue-400" />
                <span>CPU Utilization</span>
              </span>
              <span className="font-mono font-bold text-white">
                {worker.cpu_utilization.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  worker.cpu_utilization > 80
                    ? 'bg-rose-500'
                    : worker.cpu_utilization > 50
                    ? 'bg-amber-500'
                    : 'bg-blue-500'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, worker.cpu_utilization))}%` }}
              />
            </div>
          </div>

          {/* RAM Bar */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="flex items-center space-x-1 text-gray-300">
                <HardDrive className="w-3.5 h-3.5 text-indigo-400" />
                <span>Physical RAM ({usedRamGb} GB used / {totalRamGb} GB total)</span>
              </span>
              <span className="font-mono font-bold text-white">{ramUsagePercent}%</span>
            </div>
            <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, ramUsagePercent))}%` }}
              />
            </div>
            <span className="text-[11px] text-gray-400 mt-1 block">
              {availRamGb} GB free and available for cluster workload dispatch.
            </span>
          </div>
        </div>

        {/* GPU Device Metadata */}
        <div className="p-4 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-2">
          <span className="font-semibold text-gray-300 uppercase tracking-wider block text-[11px] flex items-center space-x-1.5">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>GPU Accelerators</span>
          </span>

          {worker.gpu_available && worker.gpu_metadata.length > 0 ? (
            <div className="space-y-2">
              {worker.gpu_metadata.map((gpu, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded bg-[#090d16] border border-gray-800 flex items-center justify-between"
                >
                  <div>
                    <span className="font-semibold text-white block">{gpu.name}</span>
                    <span className="text-[11px] text-gray-400">
                      {gpu.memory_total_bytes
                        ? `${(gpu.memory_total_bytes / (1024 * 1024 * 1024)).toFixed(1)} GB VRAM`
                        : 'GPU detected'}
                    </span>
                  </div>
                  <Badge variant="success">GPU Ready</Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-xs">
              No hardware GPU acceleration detected on this worker (CPU-only execution).
            </p>
          )}
        </div>

        {/* Supported Workload Types */}
        <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-1.5">
          <span className="text-gray-400 block text-[11px] font-semibold uppercase tracking-wider">
            Approved Workload Capability Runtimes
          </span>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {worker.supported_workloads.map((wl) => (
              <span
                key={wl}
                className="px-2 py-0.5 rounded bg-blue-900/30 border border-blue-800/40 text-blue-300 font-mono text-[11px]"
              >
                {wl}
              </span>
            ))}
          </div>
        </div>

        {/* Actions Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-[#1f2937]">
          <Button
            variant="outline"
            size="sm"
            onClick={handleDisconnect}
            disabled={disconnecting}
            className="text-rose-400 border-rose-900/50 hover:bg-rose-950/30"
          >
            <PowerOff className="w-3.5 h-3.5 mr-1" />
            {disconnecting ? 'Disconnecting...' : 'Disconnect Node'}
          </Button>

          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
