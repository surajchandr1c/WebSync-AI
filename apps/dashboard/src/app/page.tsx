import React from 'react';
import Link from 'next/link';
import { ConnectionStatus } from '@/components/dashboard/ConnectionStatus';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

export default function OverviewPage() {
  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Title & Introduction */}
      <div>
        <div className="flex items-center space-x-3 mb-2">
          <h1 className="text-3xl font-extrabold tracking-tight text-white">WebSync AI</h1>
          <Badge variant="info">Architecture Foundation</Badge>
        </div>
        <p className="text-gray-400 text-base max-w-3xl leading-relaxed">
          A cross-platform distributed computing platform that connects multiple computers over a network,
          enabling distributed execution of approved computational workloads across pooled CPU, RAM, and GPU resources.
        </p>
      </div>

      {/* Real-time Connection Status Card */}
      <ConnectionStatus />

      {/* Monorepo Architecture Foundation Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Coordinator Service</CardTitle>
            <Badge variant="success">Operational</Badge>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-300">
            <p>Central FastAPI orchestration service managing registry, health, and scheduling interface.</p>
            <div className="pt-2 font-mono text-xs text-gray-400 space-y-1">
              <div>Path: services/coordinator</div>
              <div>Stack: Python 3.13 / FastAPI</div>
              <div>Port: 8000 (REST + WS)</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Worker Agent</CardTitle>
            <Badge variant="success">Engine Ready</Badge>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-300">
            <p>Background node service providing hardware telemetry and isolated workload execution.</p>
            <div className="pt-2 font-mono text-xs text-gray-400 space-y-1">
              <div>Path: worker/agent</div>
              <div>Metrics: psutil (Authentic telemetry)</div>
              <div>Execution: Isolated subprocess</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Shared Core Packages</CardTitle>
            <Badge variant="success">Scaffolded</Badge>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-300">
            <p>Typed API client, canonical TypeScript contracts, and UI design primitives.</p>
            <div className="pt-2 font-mono text-xs text-gray-400 space-y-1">
              <div>@websync/shared-types</div>
              <div>@websync/api-client</div>
              <div>@websync/ui</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Planned Modules Roadmap */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Cluster Modules & Planned Capabilities</CardTitle>
            <CardDescription>
              Future phases implement actual distributed execution, scheduling, and desktop packaging.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <Link
              href="/workers"
              className="p-4 rounded-lg bg-[#161f33]/60 border border-[#1f2937] hover:border-blue-500/50 hover:bg-[#161f33] transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                  Workers Management
                </span>
                <Badge variant="neutral">Phase 2</Badge>
              </div>
              <p className="text-xs text-gray-400">
                Outbound node registration, heartbeat tracking, and hardware capability inspection.
              </p>
            </Link>

            <Link
              href="/jobs"
              className="p-4 rounded-lg bg-[#161f33]/60 border border-[#1f2937] hover:border-blue-500/50 hover:bg-[#161f33] transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                  Jobs & Scheduling
                </span>
                <Badge variant="neutral">Phase 3</Badge>
              </div>
              <p className="text-xs text-gray-400">
                Workload submission, resource requirement matching, and execution lifecycle.
              </p>
            </Link>

            <Link
              href="/monitor"
              className="p-4 rounded-lg bg-[#161f33]/60 border border-[#1f2937] hover:border-blue-500/50 hover:bg-[#161f33] transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                  Resource Monitor
                </span>
                <Badge variant="neutral">Phase 4</Badge>
              </div>
              <p className="text-xs text-gray-400">
                Time-series Recharts telemetry for cluster-wide CPU, RAM, and GPU utilization.
              </p>
            </Link>

            <Link
              href="/logs"
              className="p-4 rounded-lg bg-[#161f33]/60 border border-[#1f2937] hover:border-blue-500/50 hover:bg-[#161f33] transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                  Activity Logs
                </span>
                <Badge variant="neutral">Phase 5</Badge>
              </div>
              <p className="text-xs text-gray-400">
                Real-time WebSocket event feeds, execution stdout/stderr buffering, and audit logs.
              </p>
            </Link>

            <Link
              href="/settings"
              className="p-4 rounded-lg bg-[#161f33]/60 border border-[#1f2937] hover:border-blue-500/50 hover:bg-[#161f33] transition-all group"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-white group-hover:text-blue-400 transition-colors">
                  Settings
                </span>
                <Badge variant="neutral">Phase 5</Badge>
              </div>
              <p className="text-xs text-gray-400">
                Cluster configuration, coordinator URLs, secret tokens, and node permissions.
              </p>
            </Link>

            <div className="p-4 rounded-lg bg-[#161f33]/30 border border-[#1f2937]/50">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-400">Desktop Packaging</span>
                <Badge variant="neutral">Phase 6</Badge>
              </div>
              <p className="text-xs text-gray-500">
                Cross-platform native desktop app powered by Tauri 2 and Vite + React.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
