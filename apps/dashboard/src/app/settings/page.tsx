'use client';

import React, { useState } from 'react';
import { useCluster } from '@/context/ClusterContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import {
  Settings,
  Server,
  Database,
  Radio,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Terminal,
  Shield,
  Layers,
} from 'lucide-react';

export default function SettingsPage() {
  const {
    coordinatorUrl,
    setCoordinatorUrl,
    wsUrl,
    health,
    healthError,
    refreshAll,
    client,
  } = useCluster();

  const [inputUrl, setInputUrl] = useState(coordinatorUrl);
  const [testingPing, setTestingPing] = useState(false);
  const [pingResult, setPingResult] = useState<{ success: boolean; latencyMs?: number; error?: string } | null>(null);
  const [copiedOs, setCopiedOs] = useState<string | null>(null);

  const handleSaveAndTest = async () => {
    setTestingPing(true);
    setPingResult(null);
    const start = performance.now();

    try {
      const trimmed = inputUrl.trim().replace(/\/+$/, '');
      setCoordinatorUrl(trimmed);
      const testRes = await fetch(`${trimmed}/api/v1/health`, { cache: 'no-store' });
      const latencyMs = Math.round(performance.now() - start);

      if (!testRes.ok) {
        throw new Error(`HTTP ${testRes.status} from coordinator`);
      }
      setPingResult({ success: true, latencyMs });
      await refreshAll();
    } catch (err: unknown) {
      setPingResult({
        success: false,
        error: err instanceof Error ? err.message : 'Connection failed',
      });
    } finally {
      setTestingPing(false);
    }
  };

  const copyCommand = (text: string, os: string) => {
    navigator.clipboard.writeText(text);
    setCopiedOs(os);
    setTimeout(() => setCopiedOs(null), 2500);
  };

  const cmdWin = `.\\.venv\\Scripts\\python -m worker.agent.main --coordinator ${coordinatorUrl} --display-name "Worker-Windows"`;
  const cmdLinux = `python3 -m worker.agent.main --coordinator ${coordinatorUrl} --display-name "Worker-Linux"`;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-3 mb-1">
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
            Cluster Settings & Architecture
          </h1>
          <Badge variant="info">WebSync AI v0.1.0</Badge>
        </div>
        <p className="text-gray-400 text-sm max-w-2xl">
          Coordinator endpoints, runtime metadata, verified workload runtimes, and node connection guides.
        </p>
      </div>

      {/* Coordinator Connection Settings */}
      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Server className="w-5 h-5 text-blue-400" />
            <CardTitle>Coordinator Target Configuration</CardTitle>
          </div>
          <Badge variant={health?.status === 'healthy' ? 'success' : 'danger'}>
            {health?.status === 'healthy' ? 'Connected' : 'Offline / Error'}
          </Badge>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 space-y-1.5">
              <Input
                label="Coordinator API URL"
                value={inputUrl}
                onChange={(e) => setInputUrl(e.target.value)}
                placeholder="http://localhost:8000"
                helperText="REST API base URL for health, workers, and jobs."
              />
            </div>

            <div className="flex items-end">
              <Button
                variant="primary"
                onClick={handleSaveAndTest}
                disabled={testingPing}
                className="w-full text-xs h-9"
              >
                {testingPing ? 'Pinging Endpoint...' : 'Apply & Test Ping'}
              </Button>
            </div>
          </div>

          {/* Ping test result */}
          {pingResult && (
            <div
              className={`p-3 rounded-lg text-xs flex items-center space-x-2 ${
                pingResult.success
                  ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border border-rose-500/30 text-rose-300'
              }`}
            >
              {pingResult.success ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>
                    Successfully connected to coordinator. Round-trip latency:{' '}
                    <strong>{pingResult.latencyMs}ms</strong>.
                  </span>
                </>
              ) : (
                <>
                  <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>Ping failed: {pingResult.error}</span>
                </>
              )}
            </div>
          )}

          <div className="p-3 bg-[#0d131f] rounded-lg border border-[#1f2937] text-xs font-mono text-gray-400 flex items-center justify-between">
            <span>WebSocket Stream Target:</span>
            <span className="text-blue-400">{wsUrl}</span>
          </div>
        </CardContent>
      </Card>

      {/* Coordinator System Metadata */}
      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Layers className="w-5 h-5 text-indigo-400" />
            <CardTitle>Coordinator Runtime Information</CardTitle>
          </div>
        </CardHeader>

        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937]">
              <span className="text-gray-400 block mb-1">Service</span>
              <span className="font-semibold text-white">
                {health?.service || 'WebSync Coordinator'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937]">
              <span className="text-gray-400 block mb-1">Database Layer</span>
              <span
                className={`font-semibold font-mono ${
                  health?.database === 'healthy' ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {health?.database === 'healthy' ? 'Connected (Healthy)' : 'Unreachable'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937]">
              <span className="text-gray-400 block mb-1">Python Version</span>
              <span className="font-semibold text-white font-mono">
                {health?.python_version || '3.13+'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937]">
              <span className="text-gray-400 block mb-1">Service Uptime</span>
              <span className="font-semibold text-emerald-400 font-mono">
                {health?.uptime_seconds ? `${health.uptime_seconds.toFixed(1)}s` : '—'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Approved Workload Registry */}
      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Shield className="w-5 h-5 text-emerald-400" />
            <CardTitle>Approved Computational Workload Runtimes</CardTitle>
          </div>
        </CardHeader>

        <CardContent>
          <p className="text-xs text-gray-400 mb-3">
            WebSync AI enforces a strict workload registry. Only registered, sandboxed task handlers
            are accepted by the coordinator scheduler to prevent arbitrary remote code execution.
          </p>

          <div className="space-y-2 text-xs">
            <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937] flex items-center justify-between">
              <div>
                <span className="font-bold text-white font-mono block">matrix_multiply</span>
                <span className="text-gray-400 text-[11px]">
                  High-performance square matrix multiplication benchmark. Inputs: <code className="text-blue-400">{"{ dim: number }"}</code>
                </span>
              </div>
              <Badge variant="success">Validated</Badge>
            </div>

            <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937] flex items-center justify-between">
              <div>
                <span className="font-bold text-white font-mono block">data_processing</span>
                <span className="text-gray-400 text-[11px]">
                  Parallel batch data transform, normalization, and statistical checksum calculations. Inputs: <code className="text-blue-400">{"{ records: number, operations: string[] }"}</code>
                </span>
              </div>
              <Badge variant="success">Validated</Badge>
            </div>

            <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1f2937] flex items-center justify-between">
              <div>
                <span className="font-bold text-white font-mono block">image_processing</span>
                <span className="text-gray-400 text-[11px]">
                  Distributed computer vision convolutions and filter transforms across pooled GPUs.
                </span>
              </div>
              <Badge variant="success">Validated</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Fast Node Enrollment Guide */}
      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Terminal className="w-5 h-5 text-amber-400" />
            <CardTitle>Worker Node Startup Commands</CardTitle>
          </div>
        </CardHeader>

        <CardContent className="space-y-3 text-xs">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-300 font-semibold">Windows PowerShell:</span>
              <button
                onClick={() => copyCommand(cmdWin, 'win')}
                className="text-blue-400 hover:text-blue-300 flex items-center space-x-1"
              >
                {copiedOs === 'win' ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <pre className="p-2.5 rounded bg-[#090d16] border border-[#1f2937] font-mono text-[11px] text-gray-300 overflow-x-auto">
              {cmdWin}
            </pre>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-300 font-semibold">Linux / macOS:</span>
              <button
                onClick={() => copyCommand(cmdLinux, 'linux')}
                className="text-blue-400 hover:text-blue-300 flex items-center space-x-1"
              >
                {copiedOs === 'linux' ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <pre className="p-2.5 rounded bg-[#090d16] border border-[#1f2937] font-mono text-[11px] text-gray-300 overflow-x-auto">
              {cmdLinux}
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
