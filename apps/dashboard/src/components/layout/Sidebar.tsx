'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Badge } from '@/components/ui/Badge';

interface NavItem {
  label: string;
  href: string;
  icon: (props: { className?: string }) => React.JSX.Element;
  status: 'working' | 'planned';
}

const navItems: NavItem[] = [
  {
    label: 'Overview',
    href: '/',
    status: 'working',
    icon: (p) => (
      <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    label: 'Workers',
    href: '/workers',
    status: 'planned',
    icon: (p) => (
      <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
      </svg>
    ),
  },
  {
    label: 'Jobs',
    href: '/jobs',
    status: 'planned',
    icon: (p) => (
      <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
      </svg>
    ),
  },
  {
    label: 'Resource Monitor',
    href: '/monitor',
    status: 'planned',
    icon: (p) => (
      <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    label: 'Activity Logs',
    href: '/logs',
    status: 'planned',
    icon: (p) => (
      <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    label: 'Settings',
    href: '/settings',
    status: 'planned',
    icon: (p) => (
      <svg {...p} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-[#0d131f] border-r border-[#1f2937] flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Branding */}
        <div className="h-16 px-6 flex items-center space-x-3 border-b border-[#1f2937]">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <span className="text-white font-bold text-base">W</span>
          </div>
          <div>
            <h1 className="font-bold text-white text-base tracking-tight leading-none">WebSync AI</h1>
            <span className="text-[10px] uppercase font-mono tracking-widest text-blue-400">Distributed Grid</span>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.label}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-900/30'
                    : 'text-gray-400 hover:text-white hover:bg-[#111827]'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <item.icon className="w-5 h-5 shrink-0" />
                  <span>{item.label}</span>
                </div>
                {item.status === 'working' ? (
                  <Badge variant="success" className="text-[10px] py-0 px-1.5">
                    Live
                  </Badge>
                ) : (
                  <Badge variant="neutral" className="text-[10px] py-0 px-1.5">
                    Planned
                  </Badge>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer / Info */}
      <div className="p-4 border-t border-[#1f2937] bg-[#0b101a]">
        <div className="text-xs text-gray-500 space-y-1 font-mono">
          <div>WebSync AI v0.1.0</div>
          <div className="text-gray-600">Phase 1: Foundation Ready</div>
        </div>
      </div>
    </aside>
  );
}
