'use client';

import React, { useState } from 'react';
import { useCluster } from '@/context/ClusterContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { WorkerDetailsModal } from '@/components/workers/WorkerDetailsModal';
import { EnrollWorkerModal } from '@/components/workers/EnrollWorkerModal';
import { WorkerResponse } from '@websync/shared-types';
import {
  Server,
  Search,
  Plus,
  Cpu,
  HardDrive,
  Zap,
  PowerOff,
  Clock,
  Filter,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Bot,
} from 'lucide-react';

export default function WorkersPage() {
  const { workers, isLoading, refreshWorkers, client } = useCluster();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'online' | 'busy' | 'offline'>('all');
  const [selectedWorker, setSelectedWorker] = useState<WorkerResponse | null>(null);
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState(false);

  // Filter workers
  const filteredWorkers = workers.filter((w) => {
    const matchesSearch =
      w.display_name.toLowerCase().includes(search.toLowerCase()) ||
      w.hostname.toLowerCase().includes(search.toLowerCase()) ||
      w.worker_id.toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;
    if (statusFilter === 'all') return true;
    return w.connection_status === statusFilter;
  });

  const onlineCount = workers.filter((w) => w.connection_status === 'online').length;
  const busyCount = workers.filter((w) => w.connection_status === 'busy').length;
  const offlineCount = workers.filter((w) => w.connection_status === 'offline').length;

  const handleDisconnect = async (e: React.MouseEvent, worker: WorkerResponse) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to disconnect worker node "${worker.display_name}"?`)) {
      return;
    }
    try {
      await client.disconnectWorker(worker.worker_id);
      await refreshWorkers();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to disconnect worker');
    }
  };

  const getRelativeTime = (isoString?: string | null) => {
    if (!isoString) return 'Never';
    const diffSeconds = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diffSeconds < 5) return 'Just now';
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    return `${Math.floor(diffMinutes / 60)}h ago`;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Worker Nodes
            </h1>
            <Badge variant="info">
              {workers.length} Registered Node{workers.length === 1 ? '' : 's'}
            </Badge>
          </div>
          <p className="text-gray-400 text-sm max-w-2xl">
            Inspect physical compute machines contributing CPU, RAM, and GPU resources to the distributed cluster.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsEnrollModalOpen(true)}
            className="flex items-center space-x-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Enroll New Node</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4 bg-[#111827]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by worker ID, hostname, or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-[#0d131f] border border-[#1f2937] rounded-lg text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Status Filter Chips */}
          <div className="flex items-center space-x-1.5 text-xs">
            <span className="text-gray-400 text-xs mr-1 hidden sm:inline">Status:</span>
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                statusFilter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              All ({workers.length})
            </button>
            <button
              onClick={() => setStatusFilter('online')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                statusFilter === 'online'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              Online ({onlineCount})
            </button>
            <button
              onClick={() => setStatusFilter('busy')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                statusFilter === 'busy'
                  ? 'bg-amber-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              Busy ({busyCount})
            </button>
            <button
              onClick={() => setStatusFilter('offline')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                statusFilter === 'offline'
                  ? 'bg-rose-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              Offline ({offlineCount})
            </button>
          </div>
        </div>
      </Card>

      {/* Workers Grid / Table */}
      {filteredWorkers.length === 0 ? (
        <Card className="text-center py-16">
          <Server className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white">No worker nodes found</h3>
          <p className="text-xs text-gray-400 max-w-md mx-auto mt-1 mb-4">
            {search || statusFilter !== 'all'
              ? 'No workers match the selected filters. Try clearing your search query.'
              : 'There are currently no connected worker nodes in the cluster. Run a worker agent to begin distributed compute.'}
          </p>
          <Button variant="outline" size="sm" onClick={() => setIsEnrollModalOpen(true)}>
            <Plus className="w-3.5 h-3.5 mr-1" />
            Enroll Worker Node
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredWorkers.map((worker) => {
            const totalRamGb = (worker.total_ram_bytes / (1024 * 1024 * 1024)).toFixed(1);
            const availRamGb = (worker.available_ram_bytes / (1024 * 1024 * 1024)).toFixed(1);
            const websyncAvailRamGb = worker.websync_available_ram_bytes
              ? (worker.websync_available_ram_bytes / (1024 * 1024 * 1024)).toFixed(1)
              : availRamGb;
            const diskFreeGb = worker.disk_free_bytes
              ? (worker.disk_free_bytes / (1024 * 1024 * 1024)).toFixed(1)
              : null;
            const diskTotalGb = worker.disk_total_bytes
              ? (worker.disk_total_bytes / (1024 * 1024 * 1024)).toFixed(1)
              : null;
            const ramUsagePercent =
              worker.total_ram_bytes > 0
                ? Math.round(
                    ((worker.total_ram_bytes - worker.available_ram_bytes) /
                      worker.total_ram_bytes) *
                      100
                  )
                : 0;

            const isOnline =
              worker.connection_status === 'online' || worker.connection_status === 'busy';

            return (
              <Card
                key={worker.worker_id}
                onClick={() => setSelectedWorker(worker)}
                className="hover:border-blue-500/50 hover:bg-[#131b2e] cursor-pointer transition-all flex flex-col justify-between"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-white text-sm">
                          {worker.display_name}
                        </span>
                        <span className="text-[10px] text-gray-400 px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700">
                          {worker.platform}
                        </span>
                      </div>
                      <p className="text-[11px] font-mono text-gray-400 truncate max-w-[200px]">
                        {worker.hostname}
                      </p>
                    </div>

                    <Badge
                      variant={
                        worker.connection_status === 'online'
                          ? 'success'
                          : worker.connection_status === 'busy'
                          ? 'warning'
                          : 'danger'
                      }
                    >
                      {worker.connection_status}
                    </Badge>
                  </div>

                  {/* Telemetry Metrics */}
                  <div className="space-y-2.5 my-3 text-xs">
                    {/* CPU Progress */}
                    <div>
                      <div className="flex items-center justify-between text-[11px] text-gray-300 mb-1">
                        <span className="flex items-center space-x-1">
                          <Cpu className="w-3.5 h-3.5 text-blue-400" />
                          <span>CPU ({worker.cpu_count_logical || '—'} cores)</span>
                        </span>
                        <span className="font-mono font-semibold text-white">
                          {worker.cpu_utilization.toFixed(1)}%
                        </span>
                      </div>
                      <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${
                            worker.cpu_utilization > 80
                              ? 'bg-rose-500'
                              : worker.cpu_utilization > 50
                              ? 'bg-amber-500'
                              : 'bg-blue-500'
                          }`}
                          style={{
                            width: `${Math.min(100, Math.max(0, worker.cpu_utilization))}%`,
                          }}
                        />
                      </div>
                    </div>

                    {/* RAM Progress */}
                    <div>
                      <div className="flex items-center justify-between text-[11px] text-gray-300 mb-1">
                        <span className="flex items-center space-x-1">
                          <HardDrive className="w-3.5 h-3.5 text-indigo-400" />
                          <span>RAM (WebSync: {websyncAvailRamGb} GB free)</span>
                        </span>
                        <span className="font-mono font-semibold text-white">
                          {availRamGb} / {totalRamGb} GB
                        </span>
                      </div>
                      <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 transition-all duration-300"
                          style={{ width: `${Math.min(100, Math.max(0, ramUsagePercent))}%` }}
                        />
                      </div>
                    </div>

                    {/* Disk Storage (Physical Local Storage) */}
                    {diskTotalGb && (
                      <div className="flex items-center justify-between text-[11px] text-gray-400 pt-0.5">
                        <span className="flex items-center space-x-1">
                          <HardDrive className="w-3 h-3 text-emerald-400" />
                          <span>Local Disk</span>
                        </span>
                        <span className="font-mono text-gray-300">
                          {diskFreeGb} GB free / {diskTotalGb} GB ({worker.disk_percent ?? 0}%)
                        </span>
                      </div>
                    )}

                    {/* GPU & Concurrency */}
                    <div className="flex items-center justify-between pt-1 text-[11px] text-gray-400">
                      <span className="flex items-center space-x-1">
                        <Zap
                          className={`w-3.5 h-3.5 ${
                            worker.gpu_available ? 'text-amber-400' : 'text-gray-600'
                          }`}
                        />
                        <span>
                          {worker.gpu_available && worker.gpu_metadata.length > 0
                            ? worker.gpu_metadata[0].name.slice(0, 18)
                            : 'CPU Only'}
                        </span>
                      </span>

                      <span>
                        Jobs: <strong className="text-white">{worker.active_job_count}</strong> /{' '}
                        {worker.max_concurrent_jobs}
                      </span>
                    </div>

                    {/* Local Ollama Runtime Status */}
                    <div className="flex items-center justify-between text-[11px] text-gray-400 pt-0.5">
                      <span className="flex items-center space-x-1">
                        <Bot
                          className={`w-3.5 h-3.5 ${
                            worker.ollama_status === 'ready'
                              ? 'text-emerald-400'
                              : worker.ollama_status === 'stopped'
                              ? 'text-amber-400'
                              : 'text-gray-500'
                          }`}
                        />
                        <span>
                          {worker.ollama_status === 'ready'
                            ? `Ollama: ${worker.supported_models?.length || 0} local models`
                            : `Ollama: ${(worker.ollama_status || 'not_installed').replace('_', ' ')}`}
                        </span>
                      </span>

                      {worker.supported_models && worker.supported_models.length > 0 ? (
                        <span className="font-mono text-emerald-400 text-[10px]">
                          {worker.supported_models[0].split(':')[0]}
                          {worker.supported_models.length > 1 ? ` +${worker.supported_models.length - 1}` : ''}
                        </span>
                      ) : (
                        <span className="text-gray-600 text-[10px]">no models</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Card Footer */}
                <div className="pt-3 border-t border-[#1f2937] flex items-center justify-between text-[11px] text-gray-400">
                  <span className="flex items-center space-x-1">
                    <Clock className="w-3 h-3 text-gray-500" />
                    <span>Ping: {getRelativeTime(worker.last_heartbeat)}</span>
                  </span>

                  <div className="flex items-center space-x-2">
                    {isOnline && (
                      <button
                        onClick={(e) => handleDisconnect(e, worker)}
                        className="text-rose-400 hover:text-rose-300 p-1 rounded hover:bg-rose-950/30 transition-colors"
                        title="Disconnect Worker Node"
                      >
                        <PowerOff className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <span className="text-blue-400 font-medium">Inspect →</span>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Modals */}
      <WorkerDetailsModal
        worker={selectedWorker}
        isOpen={!!selectedWorker}
        onClose={() => setSelectedWorker(null)}
      />
      <EnrollWorkerModal isOpen={isEnrollModalOpen} onClose={() => setIsEnrollModalOpen(false)} />
    </div>
  );
}
