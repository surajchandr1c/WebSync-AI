import React, { useState } from 'react';
import { LocalWorkerStatus, WorkerBinaryInfo } from '../../types';
import {
  Terminal,
  Play,
  Square,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Trash2,
} from 'lucide-react';

interface LocalWorkerDaemonTabProps {
  binaryInfo: WorkerBinaryInfo;
  daemonStatus: LocalWorkerStatus;
  logs: string[];
  coordinatorUrl: string;
  authToken: string;
  onStartDaemon: (params: { workerId: string; workerName: string }) => Promise<void>;
  onStopDaemon: () => Promise<void>;
  onRefreshBinaryStatus: () => Promise<void>;
  onClearLogs: () => void;
  isOperating: boolean;
}

export const LocalWorkerDaemonTab: React.FC<LocalWorkerDaemonTabProps> = ({
  binaryInfo,
  daemonStatus,
  logs,
  coordinatorUrl,
  authToken: _authToken,
  onStartDaemon,
  onStopDaemon,
  onRefreshBinaryStatus,
  onClearLogs,
  isOperating,
}) => {
  const [customWorkerId, setCustomWorkerId] = useState('worker-local-node-1');
  const [customWorkerName, setCustomWorkerName] = useState('Local Desktop Node');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Local Worker Agent Daemon</h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage the standalone native WebSync worker agent executable on this machine.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={onRefreshBinaryStatus}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg border border-slate-700 flex items-center space-x-1.5 transition"
            title="Scan for worker executable"
          >
            <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
            <span>Detect Binary</span>
          </button>
        </div>
      </div>

      {/* Binary Detection Card */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                binaryInfo.found ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'
              }`}
            >
              {binaryInfo.found ? (
                <CheckCircle2 className="w-5 h-5" />
              ) : (
                <AlertCircle className="w-5 h-5" />
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">
                {binaryInfo.found
                  ? 'Standalone Worker Executable Detected'
                  : 'Worker Executable Not Found'}
              </h3>
              <p className="text-xs text-slate-400">
                {binaryInfo.found
                  ? `Ready to launch standalone daemon (v${binaryInfo.version || '0.3.0'}).`
                  : 'websync-worker.exe was not detected in expected distribution directories.'}
              </p>
            </div>
          </div>

          <span
            className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded font-semibold ${
              binaryInfo.found
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                : 'bg-rose-950 text-rose-300 border border-rose-800'
            }`}
          >
            {binaryInfo.found ? 'Installed' : 'Missing'}
          </span>
        </div>

        {binaryInfo.path && (
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between text-xs font-mono text-slate-300">
            <span className="truncate" title={binaryInfo.path}>
              Path: {binaryInfo.path}
            </span>
          </div>
        )}
      </div>

      {/* Daemon Process Controls */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <span>Process Execution Parameters</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Local Worker ID</label>
            <input
              type="text"
              disabled={daemonStatus.running}
              value={customWorkerId}
              onChange={(e) => setCustomWorkerId(e.target.value)}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500 disabled:opacity-50"
            />
          </div>
          <div>
            <label className="block text-slate-300 font-semibold mb-1">Worker Display Name</label>
            <input
              type="text"
              disabled={daemonStatus.running}
              value={customWorkerName}
              onChange={(e) => setCustomWorkerName(e.target.value)}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
            />
          </div>
        </div>

        <div className="pt-2 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-xs text-slate-400 font-mono">
            {daemonStatus.running ? (
              <span className="text-emerald-400">
                ● Daemon running (PID: {daemonStatus.pid}) connecting to {daemonStatus.coordinator_url}
              </span>
            ) : (
              <span>Target Coordinator: {coordinatorUrl}</span>
            )}
          </div>

          <div className="flex items-center space-x-3 w-full sm:w-auto">
            {daemonStatus.running ? (
              <button
                onClick={onStopDaemon}
                disabled={isOperating}
                className="w-full sm:w-auto px-4 py-2 bg-rose-950/80 hover:bg-rose-900 text-rose-200 border border-rose-800 text-xs font-semibold rounded-lg flex items-center justify-center space-x-2 transition disabled:opacity-50"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                <span>Stop Local Worker Daemon</span>
              </button>
            ) : (
              <button
                onClick={() =>
                  onStartDaemon({ workerId: customWorkerId, workerName: customWorkerName })
                }
                disabled={isOperating || !binaryInfo.found}
                className="w-full sm:w-auto px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-cyan-600/20 flex items-center justify-center space-x-2 transition disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Launch Local Worker Daemon</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Real-time Streaming Daemon Logs Console */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>Worker Daemon Process Console</span>
          </h3>

          <button
            onClick={onClearLogs}
            className="text-xs text-slate-400 hover:text-rose-400 flex items-center space-x-1"
          >
            <Trash2 className="w-3 h-3" />
            <span>Clear Console</span>
          </button>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-[11px] h-72 overflow-y-auto space-y-1 shadow-inner text-slate-300">
          {logs.length === 0 ? (
            <div className="text-slate-600 italic">No output yet. Launch daemon to view stdout/stderr stream.</div>
          ) : (
            logs.map((l, i) => (
              <div
                key={i}
                className={
                  l.includes('[ERR]')
                    ? 'text-rose-400'
                    : l.includes('[Local Daemon]')
                    ? 'text-cyan-400'
                    : 'text-slate-300'
                }
              >
                {l}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
