'use client';

import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useCluster } from '@/context/ClusterContext';
import { WorkerResponse } from '@websync/shared-types';
import { Server, Cpu, HardDrive, Zap, PowerOff, ShieldCheck, Bot, Download, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

interface WorkerDetailsModalProps {
  worker: WorkerResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function WorkerDetailsModal({ worker, isOpen, onClose }: WorkerDetailsModalProps) {
  const { client, refreshWorkers } = useCluster();
  const [disconnecting, setDisconnecting] = useState<boolean>(false);
  const [modelToPull, setModelToPull] = useState<string>('llama3.2:1b');
  const [isPulling, setIsPulling] = useState<boolean>(false);
  const [pullMessage, setPullMessage] = useState<string | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);

  if (!worker) return null;

  const handlePullModel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelToPull.trim()) return;
    setIsPulling(true);
    setPullMessage(null);
    setPullError(null);
    try {
      const res = await client.pullModel(worker.worker_id, modelToPull.trim());
      setPullMessage(res.message);
      await refreshWorkers();
    } catch (err) {
      setPullError(err instanceof Error ? err.message : 'Failed to initiate model pull');
    } finally {
      setIsPulling(false);
    }
  };

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

  const diskTotalGb = worker.disk_total_bytes
    ? (worker.disk_total_bytes / (1024 * 1024 * 1024)).toFixed(1)
    : null;
  const diskFreeGb = worker.disk_free_bytes
    ? (worker.disk_free_bytes / (1024 * 1024 * 1024)).toFixed(1)
    : null;
  const diskUsedGb = worker.disk_used_bytes
    ? (worker.disk_used_bytes / (1024 * 1024 * 1024)).toFixed(1)
    : null;
  const websyncAvailRamGb = worker.websync_available_ram_bytes
    ? (worker.websync_available_ram_bytes / (1024 * 1024 * 1024)).toFixed(1)
    : availRamGb;

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
            <span className="text-gray-400 block mb-0.5">Processor Cores</span>
            <span className="text-white font-medium">
              {worker.cpu_count_physical ? `${worker.cpu_count_physical} Phys / ` : ''}
              {worker.cpu_count_logical || '—'} Logical Cores
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Concurrency Limit</span>
            <span className="text-white font-medium">
              {worker.active_job_count} / {worker.max_concurrent_jobs} Slots Active
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Safety Reserve Buffer</span>
            <span className="text-indigo-300 font-mono">
              {worker.configured_min_available_ram_mb || 512} MB Host RAM
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">CPU Reject Threshold</span>
            <span className="text-amber-400 font-mono">
              &gt; {worker.configured_max_cpu_percent || 90}%
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
                <span>Host Physical RAM ({usedRamGb} GB used / {totalRamGb} GB total)</span>
              </span>
              <span className="font-mono font-bold text-white">{ramUsagePercent}%</span>
            </div>
            <div className="w-full bg-gray-800 h-2.5 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, ramUsagePercent))}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[11px] text-gray-400 mt-1">
              <span>{availRamGb} GB free on host OS.</span>
              <span className="text-cyan-300 font-mono">
                WebSync Allocatable: <strong>{websyncAvailRamGb} GB</strong> (after reserve buffer)
              </span>
            </div>
          </div>

          {/* Disk Storage (Physical Local Storage) */}
          {diskTotalGb && (
            <div className="pt-2 border-t border-[#1a2333]">
              <div className="flex items-center justify-between mb-1">
                <span className="flex items-center space-x-1 text-gray-300">
                  <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Local Physical Disk ({diskUsedGb} GB used / {diskTotalGb} GB total)</span>
                </span>
                <span className="font-mono font-bold text-white">{worker.disk_percent ?? 0}%</span>
              </div>
              <div className="w-full bg-gray-800 h-2 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, worker.disk_percent ?? 0))}%` }}
                />
              </div>
              <span className="text-[10px] text-gray-400 mt-1 block">
                {diskFreeGb} GB free storage. Storage is physically isolated to this local disk; no shared cluster filesystem is mounted.
              </span>
            </div>
          )}
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

        {/* Local Ollama AI Runtimes & Installed Models */}
        <div className="p-4 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-gray-300 uppercase tracking-wider block text-[11px] flex items-center space-x-1.5">
              <Bot className="w-3.5 h-3.5 text-indigo-400" />
              <span>Local Ollama AI Runtime</span>
            </span>

            <div className="flex items-center space-x-2">
              <Badge
                variant={
                  worker.ollama_status === 'ready'
                    ? 'success'
                    : worker.ollama_status === 'stopped'
                    ? 'warning'
                    : 'danger'
                }
              >
                {(worker.ollama_status || 'not_installed').toUpperCase()}
              </Badge>
              {worker.last_model_check && (
                <span className="text-[10px] text-gray-400">
                  Checked: {new Date(worker.last_model_check).toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>

          {/* Installed Models Tags */}
          <div className="space-y-1.5">
            <span className="text-gray-400 block text-[10px] font-semibold uppercase tracking-wider">
              Locally Installed Models ({worker.supported_models?.length || 0})
            </span>
            {worker.supported_models && worker.supported_models.length > 0 ? (
              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {worker.supported_models.map((m) => (
                  <span
                    key={m}
                    className="px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-800/40 text-emerald-300 font-mono text-[11px] flex items-center space-x-1"
                  >
                    <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                    <span>{m}</span>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-gray-400 text-[11px] italic">
                No LLM models currently downloaded in local Ollama repository on this node.
              </p>
            )}
          </div>

          {/* User-Triggered Model Pull / Install Form */}
          <form onSubmit={handlePullModel} className="pt-2 border-t border-[#1a2333] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-gray-300 flex items-center space-x-1">
                <Download className="w-3.5 h-3.5 text-blue-400" />
                <span>Pull / Install Model on Node</span>
              </span>
              <span className="text-[10px] text-gray-500">e.g. llama3.2:1b, mistral</span>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={modelToPull}
                onChange={(e) => setModelToPull(e.target.value)}
                placeholder="Model tag (e.g. llama3.2:1b, mistral)"
                disabled={isPulling}
                className="flex-1 px-2.5 py-1.5 bg-[#080d1a] border border-[#1f2937] rounded text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 font-mono"
              />
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={isPulling || !modelToPull.trim()}
                className="text-xs shrink-0"
              >
                {isPulling ? (
                  <>
                    <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                    <span>Pulling...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3 h-3 mr-1" />
                    <span>Pull Model</span>
                  </>
                )}
              </Button>
            </div>

            {pullMessage && (
              <div className="p-2 rounded bg-emerald-950/30 border border-emerald-900/40 text-emerald-300 text-[11px] flex items-center space-x-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                <span>{pullMessage}</span>
              </div>
            )}

            {pullError && (
              <div className="p-2 rounded bg-rose-950/30 border border-rose-900/40 text-rose-300 text-[11px] flex items-center space-x-1.5">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 text-rose-400" />
                <span>{pullError}</span>
              </div>
            )}
          </form>
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
