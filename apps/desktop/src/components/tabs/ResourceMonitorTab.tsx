import React from 'react';
import { Worker, ClusterStats } from '../../types';
import { Cpu, Layers, Sparkles, Server } from 'lucide-react';

interface ResourceMonitorTabProps {
  stats: ClusterStats;
  workers: Worker[];
}

export const ResourceMonitorTab: React.FC<ResourceMonitorTabProps> = ({ stats, workers }) => {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight">Cluster Telemetry & Resources</h2>
        <p className="text-xs text-slate-400 mt-1">
          Real-time hardware utilization metrics and capacity across distributed nodes.
        </p>
      </div>

      {/* Cluster Wide Aggregates */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* CPU Aggregate */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span>Cluster CPU Capacity</span>
            </span>
            <span className="text-xs font-mono font-bold text-cyan-400">
              {stats.avg_cpu_percent}%
            </span>
          </div>

          <div className="space-y-1">
            <div className="h-3 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-700"
                style={{ width: `${Math.min(100, Math.max(0, stats.avg_cpu_percent))}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500 font-mono">
              <span>0%</span>
              <span>{stats.total_cpu_cores} total threads</span>
              <span>100%</span>
            </div>
          </div>
        </div>

        {/* RAM Aggregate */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>Cluster Memory Pool</span>
            </span>
            <span className="text-xs font-mono font-bold text-indigo-400">
              {stats.avg_memory_percent}%
            </span>
          </div>

          <div className="space-y-1">
            <div className="h-3 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-700"
                style={{ width: `${Math.min(100, Math.max(0, stats.avg_memory_percent))}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500 font-mono">
              <span>0%</span>
              <span>{stats.total_memory_gb} GB pool</span>
              <span>100%</span>
            </div>
          </div>
        </div>

        {/* GPU Aggregate */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <span>Accelerated Compute</span>
            </span>
            <span className="text-xs font-mono font-bold text-emerald-400">
              {stats.total_gpus} GPUs
            </span>
          </div>

          <div className="space-y-1">
            <div className="h-3 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-700"
                style={{ width: `${stats.total_gpus > 0 ? 100 : 0}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500 font-mono">
              <span>CUDA / DirectML</span>
              <span>{stats.total_gpus} hardware units</span>
              <span>Ready</span>
            </div>
          </div>
        </div>
      </div>

      {/* Per Node Breakdown */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center space-x-2">
          <Server className="w-4 h-4 text-cyan-400" />
          <span>Per-Node Telemetry Breakdown</span>
        </h3>

        {workers.length === 0 ? (
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-8 text-center text-xs text-slate-500">
            No telemetry available. Start or connect worker nodes to view real-time resource utilization.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {workers.map((w) => {
              const cpu = w.telemetry?.cpu_percent ?? 0;
              const mem = w.telemetry?.memory_percent ?? 0;
              const memGb = (w.total_memory_bytes / 1024 ** 3).toFixed(1);

              return (
                <div
                  key={w.id}
                  className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3 shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-bold text-slate-200">{w.name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {w.platform} · {w.cpu_cores_logical} cores · {memGb} GB RAM
                      </div>
                    </div>
                    <span
                      className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded ${
                        w.status === 'online'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : w.status === 'busy'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {w.status}
                    </span>
                  </div>

                  {/* CPU Meter */}
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>CPU Utilization</span>
                      <span className="font-mono text-slate-200">{cpu}%</span>
                    </div>
                    <div className="h-2 bg-slate-950 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          cpu > 80 ? 'bg-rose-500' : cpu > 50 ? 'bg-amber-400' : 'bg-cyan-400'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, cpu))}%` }}
                      />
                    </div>
                  </div>

                  {/* RAM Meter */}
                  <div>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                      <span>Memory Utilization</span>
                      <span className="font-mono text-slate-200">{mem}%</span>
                    </div>
                    <div className="h-2 bg-slate-950 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          mem > 85 ? 'bg-rose-500' : mem > 60 ? 'bg-amber-400' : 'bg-indigo-400'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, mem))}%` }}
                      />
                    </div>
                  </div>

                  {/* GPU Info if available */}
                  {w.gpu_info && (
                    <div className="bg-slate-950/80 border border-slate-800 rounded p-2 flex items-center justify-between text-[11px]">
                      <span className="text-cyan-400 flex items-center space-x-1">
                        <Sparkles className="w-3 h-3" />
                        <span>{w.gpu_info.name}</span>
                      </span>
                      <span className="font-mono text-slate-400">
                        {(w.gpu_info.total_memory_bytes / 1024 ** 3).toFixed(2)} GB VRAM
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
