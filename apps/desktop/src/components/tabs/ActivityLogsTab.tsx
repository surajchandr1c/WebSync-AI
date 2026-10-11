import React, { useState } from 'react';
import { SystemLogEntry } from '../../types';
import { ScrollText, Trash2 } from 'lucide-react';

interface ActivityLogsTabProps {
  logs: SystemLogEntry[];
  onClearLogs: () => void;
}

export const ActivityLogsTab: React.FC<ActivityLogsTabProps> = ({ logs, onClearLogs }) => {
  const [filterLevel, setFilterLevel] = useState<string>('all');
  const [autoScroll, setAutoScroll] = useState(true);

  const filtered = logs.filter((l) => filterLevel === 'all' || l.level === filterLevel);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">System & Activity Logs</h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time synchronization events, worker heartbeats, and cluster dispatches.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={onClearLogs}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs rounded-lg border border-slate-700 flex items-center space-x-1.5 transition"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400" />
            <span>Clear Feed</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center justify-between bg-slate-900/60 p-3 rounded-xl border border-slate-800 text-xs">
        <div className="flex items-center space-x-2">
          {['all', 'info', 'success', 'warn', 'error'].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setFilterLevel(lvl)}
              className={`px-2.5 py-1 rounded uppercase font-mono tracking-wider transition ${
                filterLevel === lvl
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 bg-slate-950 border border-slate-800'
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>

        <label className="flex items-center space-x-2 text-slate-400 select-none cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-slate-700 text-cyan-600 focus:ring-cyan-500"
          />
          <span>Auto-scroll</span>
        </label>
      </div>

      {/* Log Feed */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs max-h-[550px] overflow-y-auto space-y-1.5 shadow-inner">
        {filtered.length === 0 ? (
          <div className="py-12 text-center text-slate-500 font-sans">
            <ScrollText className="w-8 h-8 text-slate-700 mx-auto mb-2" />
            No system log events recorded yet.
          </div>
        ) : (
          filtered.map((log) => (
            <div
              key={log.id}
              className="flex items-start space-x-3 p-1.5 rounded hover:bg-slate-900/50 transition border-l-2 border-transparent hover:border-slate-700"
            >
              <span className="text-slate-500 shrink-0 text-[11px]">{log.timestamp}</span>

              <span
                className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-bold shrink-0 ${
                  log.level === 'success'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : log.level === 'warn'
                    ? 'bg-amber-950 text-amber-400 border border-amber-800'
                    : log.level === 'error'
                    ? 'bg-rose-950 text-rose-400 border border-rose-800'
                    : 'bg-slate-800 text-slate-300 border border-slate-700'
                }`}
              >
                {log.level}
              </span>

              <span className="text-cyan-400/80 shrink-0 text-[11px]">[{log.component}]</span>

              <span className="text-slate-300 break-all">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
