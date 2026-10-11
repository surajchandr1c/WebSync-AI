import React, { useState } from 'react';
import { Worker } from '../../types';
import {
  Server,
  Cpu,
  Layers,
  Sparkles,
  Search,
  ShieldBan,
  Clock,
  Terminal,
} from 'lucide-react';

interface WorkersTabProps {
  workers: Worker[];
  onRevokeWorker: (workerId: string) => void;
  onOpenLocalDaemon: () => void;
}

export const WorkersTab: React.FC<WorkersTabProps> = ({
  workers,
  onRevokeWorker,
  onOpenLocalDaemon,
}) => {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const filtered = workers.filter((w) => {
    const matchesSearch =
      w.name.toLowerCase().includes(search.toLowerCase()) ||
      w.id.toLowerCase().includes(search.toLowerCase()) ||
      w.platform.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filterStatus === 'all' || w.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Worker Nodes</h2>
          <p className="text-xs text-slate-400 mt-1">
            Registered compute nodes running the WebSync AI worker agent across Windows, Linux, and macOS.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={onOpenLocalDaemon}
            className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center space-x-1.5 transition"
          >
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>Local Worker Daemon</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by worker name, id, platform..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          {['all', 'online', 'busy', 'offline'].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wider transition ${
                filterStatus === status
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 bg-slate-950 border border-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Workers Grid */}
      {filtered.length === 0 ? (
        <div className="bg-slate-900/40 border border-slate-800 rounded-2xl py-12 text-center">
          <Server className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-300">No Workers Found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            {search || filterStatus !== 'all'
              ? 'No workers match the current search or status filter.'
              : 'Launch a local worker agent daemon or connect an external node to start computing.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((worker) => {
            const cpuPercent = worker.telemetry?.cpu_percent ?? 0;
            const memPercent = worker.telemetry?.memory_percent ?? 0;
            const memTotalGb = (worker.total_memory_bytes / 1024 ** 3).toFixed(1);

            return (
              <div
                key={worker.id}
                className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-xl p-5 space-y-4 transition shadow-sm"
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <div
                        className={`w-2 h-2 rounded-full ${
                          worker.status === 'online'
                            ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50'
                            : worker.status === 'busy'
                            ? 'bg-amber-400 animate-pulse'
                            : 'bg-slate-500'
                        }`}
                      />
                      <h3 className="text-sm font-bold text-white tracking-tight">{worker.name}</h3>
                    </div>
                    <div className="text-[11px] font-mono text-slate-400">
                      ID: {worker.id}
                    </div>
                  </div>

                  <span
                    className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded font-semibold ${
                      worker.status === 'online'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : worker.status === 'busy'
                        ? 'bg-amber-950 text-amber-300 border border-amber-800'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {worker.status}
                  </span>
                </div>

                {/* Specs Badges */}
                <div className="flex flex-wrap gap-1.5 text-[11px] font-mono">
                  <span className="px-2 py-0.5 bg-slate-950 border border-slate-800 rounded text-slate-300">
                    OS: {worker.platform}
                  </span>
                  <span className="px-2 py-0.5 bg-slate-950 border border-slate-800 rounded text-slate-300">
                    Arch: {worker.cpu_arch}
                  </span>
                  <span className="px-2 py-0.5 bg-slate-950 border border-slate-800 rounded text-slate-300">
                    {worker.cpu_cores_logical} Cores ({worker.cpu_cores_physical} phys)
                  </span>
                  <span className="px-2 py-0.5 bg-slate-950 border border-slate-800 rounded text-slate-300">
                    {memTotalGb} GB RAM
                  </span>
                </div>

                {/* GPU Card if detected */}
                {worker.gpu_info && (
                  <div className="bg-cyan-950/30 border border-cyan-900/50 rounded-lg p-2.5 flex items-center space-x-2.5">
                    <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
                    <div className="text-xs">
                      <div className="font-semibold text-cyan-200">{worker.gpu_info.name}</div>
                      <div className="text-[10px] text-cyan-400/80 font-mono">
                        VRAM: {(worker.gpu_info.total_memory_bytes / 1024 ** 3).toFixed(2)} GB
                      </div>
                    </div>
                  </div>
                )}

                {/* Real-Time Telemetry Progress Bars */}
                <div className="space-y-2.5 pt-2 border-t border-slate-800/80 text-xs">
                  <div>
                    <div className="flex items-center justify-between text-slate-400 mb-1">
                      <span className="flex items-center space-x-1">
                        <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                        <span>CPU Usage</span>
                      </span>
                      <span className="font-mono text-slate-200">{cpuPercent}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 rounded-full ${
                          cpuPercent > 80
                            ? 'bg-rose-500'
                            : cpuPercent > 50
                            ? 'bg-amber-400'
                            : 'bg-cyan-400'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, cpuPercent))}%` }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-slate-400 mb-1">
                      <span className="flex items-center space-x-1">
                        <Layers className="w-3.5 h-3.5 text-indigo-400" />
                        <span>RAM Usage</span>
                      </span>
                      <span className="font-mono text-slate-200">{memPercent}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-950 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 rounded-full ${
                          memPercent > 85
                            ? 'bg-rose-500'
                            : memPercent > 60
                            ? 'bg-amber-400'
                            : 'bg-indigo-400'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, memPercent))}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500 font-mono">
                  <div className="flex items-center space-x-1">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <span>Heartbeat: {new Date(worker.last_heartbeat).toLocaleTimeString()}</span>
                  </div>

                  <button
                    onClick={() => onRevokeWorker(worker.id)}
                    className="text-rose-400 hover:text-rose-300 flex items-center space-x-1 hover:underline"
                    title="Revoke worker authorization"
                  >
                    <ShieldBan className="w-3.5 h-3.5" />
                    <span>Revoke</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
