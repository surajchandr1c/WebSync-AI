import React from 'react';
import { TabId, LocalWorkerStatus } from '../types';
import {
  LayoutDashboard,
  Server,
  Briefcase,
  Cpu,
  ScrollText,
  Terminal,
  Settings2,
  Play,
  Square,
} from 'lucide-react';

interface SidebarProps {
  currentTab: TabId;
  onSelectTab: (tab: TabId) => void;
  workerCount: number;
  jobCount: number;
  daemonStatus: LocalWorkerStatus;
  onToggleDaemon: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  workerCount,
  jobCount,
  daemonStatus,
  onToggleDaemon,
}) => {
  const navItems: { id: TabId; label: string; icon: React.ReactNode; badge?: string | number }[] = [
    {
      id: 'overview',
      label: 'Overview',
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      id: 'workers',
      label: 'Workers',
      icon: <Server className="w-4 h-4" />,
      badge: workerCount,
    },
    {
      id: 'jobs',
      label: 'Jobs & Tasks',
      icon: <Briefcase className="w-4 h-4" />,
      badge: jobCount,
    },
    {
      id: 'resources',
      label: 'Resource Monitor',
      icon: <Cpu className="w-4 h-4" />,
    },
    {
      id: 'logs',
      label: 'Activity Logs',
      icon: <ScrollText className="w-4 h-4" />,
    },
    {
      id: 'daemon',
      label: 'Local Worker',
      icon: <Terminal className="w-4 h-4" />,
      badge: daemonStatus.running ? 'ON' : undefined,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: <Settings2 className="w-4 h-4" />,
    },
  ];

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-950 flex flex-col justify-between p-4 select-none shrink-0">
      <div className="space-y-6">
        <div>
          <p className="px-3 text-[11px] font-semibold tracking-wider uppercase text-slate-500 mb-2">
            Navigation
          </p>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const active = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelectTab(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition ${
                    active
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <span className={active ? 'text-cyan-400' : 'text-slate-500'}>{item.icon}</span>
                    <span>{item.label}</span>
                  </div>
                  {item.badge !== undefined && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-mono font-semibold ${
                        item.id === 'daemon' && item.badge === 'ON'
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800 animate-pulse'
                          : active
                          ? 'bg-cyan-950 text-cyan-300'
                          : 'bg-slate-900 text-slate-400'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Local Daemon Quick Control Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                daemonStatus.running ? 'bg-emerald-400 animate-ping' : 'bg-slate-600'
              }`}
            />
            <span className="text-xs font-semibold text-slate-200">Local Agent</span>
          </div>
          <span
            className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded ${
              daemonStatus.running
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                : 'bg-slate-800 text-slate-400'
            }`}
          >
            {daemonStatus.running ? 'Running' : 'Stopped'}
          </span>
        </div>

        {daemonStatus.running && (
          <div className="text-[11px] font-mono text-slate-400 space-y-0.5">
            <div>PID: <span className="text-slate-300">{daemonStatus.pid}</span></div>
            <div className="truncate" title={daemonStatus.worker_id || ''}>
              ID: <span className="text-slate-300">{daemonStatus.worker_id}</span>
            </div>
          </div>
        )}

        <button
          onClick={onToggleDaemon}
          className={`w-full py-1.5 px-3 rounded-lg text-xs font-medium flex items-center justify-center space-x-1.5 transition ${
            daemonStatus.running
              ? 'bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800'
              : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-600/20'
          }`}
        >
          {daemonStatus.running ? (
            <>
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop Local Agent</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Start Local Agent</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
