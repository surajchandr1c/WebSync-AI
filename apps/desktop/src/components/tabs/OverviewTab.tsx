import React from 'react';
import { Worker, Job, ClusterStats, TabId, LocalWorkerStatus } from '../../types';
import {
  Server,
  Briefcase,
  Cpu,
  Layers,
  CheckCircle2,
  Play,
  ArrowRight,
  PlusCircle,
  Terminal,
} from 'lucide-react';

interface OverviewTabProps {
  stats: ClusterStats;
  workers: Worker[];
  jobs: Job[];
  onSelectTab: (tab: TabId) => void;
  onOpenNewJob: () => void;
  daemonStatus: LocalWorkerStatus;
  onToggleDaemon: () => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  stats,
  workers,
  jobs,
  onSelectTab,
  onOpenNewJob,
  daemonStatus: _daemonStatus,
  onToggleDaemon,
}) => {
  const onlineWorkers = workers.filter((w) => w.status === 'online' || w.status === 'busy');
  const recentJobs = jobs.slice(0, 5);

  const successRate =
    stats.completed_jobs + stats.failed_jobs > 0
      ? Math.round((stats.completed_jobs / (stats.completed_jobs + stats.failed_jobs)) * 100)
      : 100;

  return (
    <div className="space-y-6">
      {/* Top Banner / Welcome */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-cyan-950/40 border border-slate-800 rounded-2xl p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Cluster Command Center</h2>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
            Real-time telemetry, remote worker orchestration, and distributed workload execution across
            heterogeneous computing nodes.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={onOpenNewJob}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-xl flex items-center space-x-2 shadow-lg shadow-cyan-600/20 transition"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Submit Job</span>
          </button>
          <button
            onClick={() => onSelectTab('daemon')}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 hover:border-slate-600 flex items-center space-x-2 transition"
          >
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span>Worker Controls</span>
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Nodes Online</span>
            <Server className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-white">{stats.online_workers}</span>
            <span className="text-xs text-slate-500">/ {stats.total_workers} total</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span>{stats.busy_workers} busy processing jobs</span>
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Cluster Cores</span>
            <Cpu className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-white">{stats.total_cpu_cores}</span>
            <span className="text-xs text-slate-500">CPU threads</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Avg CPU Load: <span className="text-slate-200 font-semibold">{stats.avg_cpu_percent}%</span>
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Cluster Memory</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-white">{stats.total_memory_gb}</span>
            <span className="text-xs text-slate-500">GB RAM</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Avg RAM Usage: <span className="text-slate-200 font-semibold">{stats.avg_memory_percent}%</span>
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Job Success</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-white">{successRate}%</span>
            <span className="text-xs text-slate-500">rate</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            <span className="text-slate-200 font-semibold">{stats.completed_jobs}</span> completed / {stats.failed_jobs} failed
          </div>
        </div>
      </div>

      {/* Two Column Section: Active Workers & Recent Jobs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Workers Snapshot */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Server className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-semibold text-white">Connected Workers</h3>
            </div>
            <button
              onClick={() => onSelectTab('workers')}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {onlineWorkers.length === 0 ? (
            <div className="py-8 text-center border border-dashed border-slate-800 rounded-lg">
              <Server className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-400">No active worker nodes found.</p>
              <button
                onClick={onToggleDaemon}
                className="mt-3 text-xs px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg inline-flex items-center space-x-1.5"
              >
                <Play className="w-3 h-3" />
                <span>Start Local Worker</span>
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {onlineWorkers.slice(0, 4).map((worker) => (
                <div
                  key={worker.id}
                  className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-center justify-between"
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`w-2.5 h-2.5 rounded-full ${
                        worker.status === 'busy'
                          ? 'bg-amber-400 animate-pulse'
                          : 'bg-emerald-400'
                      }`}
                    />
                    <div>
                      <div className="text-xs font-semibold text-slate-200">{worker.name}</div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {worker.platform} · {worker.cpu_cores_logical} cores ·{' '}
                        {(worker.total_memory_bytes / 1024 ** 3).toFixed(1)} GB
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded ${
                        worker.status === 'busy'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800'
                          : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      }`}
                    >
                      {worker.status}
                    </span>
                    <div className="text-[10px] text-slate-500 mt-1 font-mono">
                      CPU: {worker.telemetry?.cpu_percent || 0}%
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Jobs Snapshot */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Briefcase className="w-4 h-4 text-indigo-400" />
              <h3 className="text-sm font-semibold text-white">Recent Workloads</h3>
            </div>
            <button
              onClick={() => onSelectTab('jobs')}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {recentJobs.length === 0 ? (
            <div className="py-8 text-center border border-dashed border-slate-800 rounded-lg">
              <Briefcase className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-400">No jobs submitted yet.</p>
              <button
                onClick={onOpenNewJob}
                className="mt-3 text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg inline-flex items-center space-x-1.5"
              >
                <PlusCircle className="w-3 h-3" />
                <span>Submit First Job</span>
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {recentJobs.map((job) => (
                <div
                  key={job.id}
                  className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-center justify-between"
                >
                  <div>
                    <div className="text-xs font-semibold text-slate-200">{job.title}</div>
                    <div className="text-[11px] text-slate-500 font-mono">
                      Type: {job.task_type} · ID: {job.id.slice(0, 8)}
                    </div>
                  </div>
                  <span
                    className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded ${
                      job.status === 'completed'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : job.status === 'running'
                        ? 'bg-cyan-950 text-cyan-300 border border-cyan-800 animate-pulse'
                        : job.status === 'failed'
                        ? 'bg-rose-950 text-rose-300 border border-rose-800'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {job.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
