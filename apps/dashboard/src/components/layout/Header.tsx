'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { RefreshCw, Wifi, WifiOff, Server, PlaySquare } from 'lucide-react';
import { useCluster } from '@/context/ClusterContext';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

const routeTitles: Record<string, string> = {
  '/': 'Overview',
  '/chat': 'Remote AI Prompt Studio',
  '/workers': 'Workers Management',
  '/jobs': 'Distributed Jobs & Scheduling',
  '/monitor': 'Live Resource Monitor',
  '/logs': 'Cluster Activity Logs',
  '/settings': 'Settings & Cluster Architecture',
};

export function Header() {
  const pathname = usePathname();
  const cluster = useCluster();
  const title = routeTitles[pathname] || 'Dashboard';

  const onlineWorkers = cluster.workers.filter(
    (w) => w.connection_status === 'online' || w.connection_status === 'busy'
  ).length;

  const activeJobs = cluster.jobs.filter(
    (j) => j.status === 'RUNNING' || j.status === 'QUEUED' || j.status === 'SCHEDULED'
  ).length;

  return (
    <header className="h-16 border-b border-[#1f2937] bg-[#111827]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 shrink-0">
      <div className="flex items-center space-x-3">
        <h2 className="text-base font-bold text-white tracking-tight">{title}</h2>
        <span className="text-gray-600">/</span>
        <span className="text-xs font-mono text-gray-400">
          {cluster.coordinatorUrl.replace(/^https?:\/\//, '')}
        </span>
      </div>

      <div className="flex items-center space-x-3 sm:space-x-4">
        {/* Quick stats pills */}
        <div className="hidden md:flex items-center space-x-2 text-xs">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-[#0d131f] border border-[#1f2937] text-gray-300">
            <Server className="w-3.5 h-3.5 text-blue-400" />
            <span>
              <strong className="text-white">{onlineWorkers}</strong> / {cluster.workers.length} Nodes
            </span>
          </div>

          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-[#0d131f] border border-[#1f2937] text-gray-300">
            <PlaySquare className="w-3.5 h-3.5 text-indigo-400" />
            <span>
              <strong className="text-white">{activeJobs}</strong> Active Jobs
            </span>
          </div>
        </div>

        {/* Stale Data Warning */}
        {cluster.isStale && (
          <Badge variant="warning" className="hidden lg:inline-flex text-[11px] px-2 py-0.5">
            Stale Data (Polling)
          </Badge>
        )}

        {/* WebSocket Connection Pill */}
        <div className="flex items-center space-x-1.5">
          {cluster.wsStatus === 'connected' ? (
            <Badge variant="success" className="flex items-center space-x-1 px-2.5 py-1">
              <Wifi className="w-3 h-3 animate-pulse" />
              <span>Realtime Live</span>
            </Badge>
          ) : cluster.wsStatus === 'connecting' ? (
            <Badge variant="warning" className="flex items-center space-x-1 px-2.5 py-1">
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>Connecting WS...</span>
            </Badge>
          ) : (
            <Badge variant="danger" className="flex items-center space-x-1 px-2.5 py-1">
              <WifiOff className="w-3 h-3" />
              <span>WS Disconnected</span>
            </Badge>
          )}
        </div>

        {/* Manual Refresh Button */}
        <Button
          variant="secondary"
          size="sm"
          onClick={() => cluster.refreshAll()}
          disabled={cluster.isLoading}
          className="flex items-center space-x-1.5 text-xs px-2.5 py-1 h-8"
          title="Refresh coordinator state"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 text-gray-400 ${cluster.isLoading ? 'animate-spin text-blue-400' : ''}`}
          />
          <span className="hidden sm:inline">Refresh</span>
        </Button>
      </div>
    </header>
  );
}
