import React from 'react';
import { ConnectionStatus, ClusterStats } from '../types';
import {
  Activity,
  Wifi,
  WifiOff,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
  Server,
  Cpu,
} from 'lucide-react';

interface HeaderProps {
  coordinatorUrl: string;
  connectionStatus: ConnectionStatus;
  latencyMs: number;
  stats: ClusterStats;
  isRefreshing: boolean;
  onRefresh: () => void;
  onTestConnection: () => void;
  isTesting: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  coordinatorUrl,
  connectionStatus,
  latencyMs,
  stats,
  isRefreshing,
  onRefresh,
  onTestConnection,
  isTesting,
}) => {
  const isSecure = coordinatorUrl.startsWith('https://') || coordinatorUrl.startsWith('wss://');
  const isLocal = coordinatorUrl.includes('localhost') || coordinatorUrl.includes('127.0.0.1');

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 p-0.5 shadow-lg shadow-cyan-500/20">
          <div className="w-full h-full bg-slate-950 rounded-[7px] flex items-center justify-center">
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-base font-bold text-white tracking-tight">WebSync AI</h1>
            <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-800 text-cyan-300">
              Desktop v0.3.0
            </span>
          </div>
          <p className="text-xs text-slate-400 flex items-center space-x-1.5">
            <span>Coordinator:</span>
            <span className="font-mono text-slate-300 font-medium">{coordinatorUrl}</span>
            {isSecure ? (
              <span title="TLS/WSS Secure Connection" className="text-emerald-400 flex items-center">
                <ShieldCheck className="w-3.5 h-3.5 inline ml-0.5" />
              </span>
            ) : isLocal ? (
              <span title="Local Development Host (HTTP allowed)" className="text-amber-400 text-[11px] font-mono">
                (local)
              </span>
            ) : (
              <span title="Insecure Remote Connection!" className="text-rose-400 flex items-center">
                <ShieldAlert className="w-3.5 h-3.5 inline ml-0.5" />
              </span>
            )}
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Quick Cluster Status Indicators */}
        <div className="hidden lg:flex items-center space-x-3 text-xs bg-slate-950/60 border border-slate-800 px-3 py-1.5 rounded-lg">
          <div className="flex items-center space-x-1.5 text-slate-300">
            <Server className="w-3.5 h-3.5 text-emerald-400" />
            <span>
              <strong className="text-white">{stats.online_workers}</strong> / {stats.total_workers} Workers
            </span>
          </div>
          <div className="w-px h-3.5 bg-slate-800" />
          <div className="flex items-center space-x-1.5 text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span>
              <strong className="text-white">{stats.total_cpu_cores}</strong> Cores
            </span>
          </div>
          <div className="w-px h-3.5 bg-slate-800" />
          <div className="flex items-center space-x-1.5 text-slate-300">
            <Activity className="w-3.5 h-3.5 text-indigo-400" />
            <span>
              <strong className="text-white">{stats.active_jobs}</strong> Active Jobs
            </span>
          </div>
        </div>

        {/* Connectivity Status Pill */}
        <div
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-full border text-xs font-medium transition-all ${
            connectionStatus === 'connected'
              ? 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300'
              : connectionStatus === 'connecting'
              ? 'bg-amber-950/60 border-amber-800/80 text-amber-300 animate-pulse'
              : 'bg-rose-950/60 border-rose-800/80 text-rose-300'
          }`}
        >
          {connectionStatus === 'connected' ? (
            <Wifi className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-rose-400" />
          )}
          <span className="capitalize">{connectionStatus}</span>
          {connectionStatus === 'connected' && latencyMs > 0 && (
            <span className="text-[11px] font-mono text-emerald-400/80">({latencyMs}ms)</span>
          )}
        </div>

        {/* Actions */}
        <button
          onClick={onTestConnection}
          disabled={isTesting}
          className="text-xs px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-600 transition flex items-center space-x-1.5 disabled:opacity-50"
          title="Test Coordinator Connection"
        >
          <span className={isTesting ? 'animate-spin' : ''}>⚡</span>
          <span>{isTesting ? 'Testing...' : 'Ping'}</span>
        </button>

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 hover:border-slate-600 transition disabled:opacity-50"
          title="Refresh All Coordinator Data"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
        </button>
      </div>
    </header>
  );
};
