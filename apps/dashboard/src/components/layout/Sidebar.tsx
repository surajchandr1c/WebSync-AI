'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Server,
  PlaySquare,
  Activity,
  ScrollText,
  Settings,
  Radio,
  Sparkles,
} from 'lucide-react';
import { useCluster } from '@/context/ClusterContext';

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: (cluster: ReturnType<typeof useCluster>) => React.ReactNode;
}

const navItems: NavItem[] = [
  {
    label: 'Overview',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    label: 'AI Chat Studio',
    href: '/chat',
    icon: Sparkles,
  },
  {
    label: 'Workers',
    href: '/workers',
    icon: Server,
    badge: (c) => {
      const online = c.workers.filter(
        (w) => w.connection_status === 'online' || w.connection_status === 'busy'
      ).length;
      return online > 0 ? (
        <span className="bg-emerald-500/20 text-emerald-400 text-[10px] font-bold px-1.5 py-0.2 rounded-full border border-emerald-500/30">
          {online}
        </span>
      ) : null;
    },
  },
  {
    label: 'Jobs',
    href: '/jobs',
    icon: PlaySquare,
    badge: (c) => {
      const active = c.jobs.filter(
        (j) => j.status === 'RUNNING' || j.status === 'QUEUED' || j.status === 'SCHEDULED'
      ).length;
      return active > 0 ? (
        <span className="bg-blue-500/20 text-blue-400 text-[10px] font-bold px-1.5 py-0.2 rounded-full border border-blue-500/30">
          {active}
        </span>
      ) : null;
    },
  },
  {
    label: 'Resource Monitor',
    href: '/monitor',
    icon: Activity,
  },
  {
    label: 'Activity Logs',
    href: '/logs',
    icon: ScrollText,
  },
  {
    label: 'Settings',
    href: '/settings',
    icon: Settings,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const cluster = useCluster();

  return (
    <aside className="w-64 bg-[#0d131f] border-r border-[#1f2937] flex flex-col justify-between shrink-0 h-screen sticky top-0 z-40 select-none">
      <div>
        {/* Branding */}
        <div className="h-16 px-6 flex items-center space-x-3 border-b border-[#1f2937]">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/25">
            <Radio className="w-5 h-5 text-white animate-pulse" />
          </div>
          <div>
            <h1 className="font-bold text-white text-base tracking-tight leading-none">
              WebSync AI
            </h1>
            <span className="text-[10px] uppercase font-mono tracking-widest text-blue-400">
              Distributed Compute
            </span>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            const badgeContent = item.badge ? item.badge(cluster) : null;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-900/30'
                    : 'text-gray-400 hover:text-white hover:bg-[#111827]'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-gray-400'}`} />
                  <span>{item.label}</span>
                </div>
                {badgeContent}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer / Coordinator Connection Status */}
      <div className="p-4 border-t border-[#1f2937] bg-[#0b101a] space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-400">Coordinator</span>
          <span
            className={`inline-flex items-center gap-1.5 font-medium ${
              cluster.health?.status === 'healthy'
                ? 'text-emerald-400'
                : cluster.health?.status === 'degraded'
                ? 'text-amber-400'
                : 'text-rose-400'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                cluster.health?.status === 'healthy'
                  ? 'bg-emerald-400 animate-pulse'
                  : 'bg-rose-400'
              }`}
            />
            {cluster.health?.status === 'healthy'
              ? 'Healthy'
              : cluster.health?.status === 'degraded'
              ? 'Degraded'
              : 'Offline'}
          </span>
        </div>

        <div className="text-[11px] text-gray-500 font-mono flex items-center justify-between">
          <span>WebSync AI v0.1.0</span>
          <span>FastAPI</span>
        </div>
      </div>
    </aside>
  );
}
