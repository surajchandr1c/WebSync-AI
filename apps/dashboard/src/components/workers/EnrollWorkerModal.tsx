'use client';

import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { useCluster } from '@/context/ClusterContext';
import { Server, Copy, Check, Terminal } from 'lucide-react';

interface EnrollWorkerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EnrollWorkerModal({ isOpen, onClose }: EnrollWorkerModalProps) {
  const { coordinatorUrl } = useCluster();
  const [copiedOs, setCopiedOs] = useState<string | null>(null);

  const cmdWindows = `.\\.venv\\Scripts\\python -m worker.agent.main --coordinator ${coordinatorUrl} --display-name "Windows-Node-$(Get-Random -Minimum 100 -Maximum 999)"`;
  const cmdLinux = `python3 -m worker.agent.main --coordinator ${coordinatorUrl} --display-name "Linux-Node-$RANDOM"`;
  const cmdMac = `python3 -m worker.agent.main --coordinator ${coordinatorUrl} --display-name "Mac-Node-$RANDOM"`;

  const copyToClipboard = (text: string, os: string) => {
    navigator.clipboard.writeText(text);
    setCopiedOs(os);
    setTimeout(() => setCopiedOs(null), 2500);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center space-x-2">
          <Server className="w-5 h-5 text-blue-400" />
          <span>Enroll New Worker Node</span>
        </div>
      }
      description="Connect any computer on the local network or internet to contribute CPU, RAM, and GPU resources."
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4 text-xs">
        <p className="text-gray-300 leading-relaxed">
          The WebSync AI Python worker agent runs securely in the background, collecting real hardware
          telemetry via <code className="bg-gray-800 text-blue-300 px-1 py-0.5 rounded font-mono">psutil</code> and
          executing approved computational jobs in isolated subprocesses.
        </p>

        {/* Windows */}
        <div className="p-3.5 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-white flex items-center space-x-1.5">
              <Terminal className="w-3.5 h-3.5 text-blue-400" />
              <span>Windows (PowerShell)</span>
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(cmdWindows, 'win')}
              className="text-[11px] h-7 px-2.5"
            >
              {copiedOs === 'win' ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 mr-1" />
                  Copy Command
                </>
              )}
            </Button>
          </div>
          <pre className="p-2.5 rounded bg-[#090d16] border border-gray-800 font-mono text-gray-300 overflow-x-auto text-[11px] leading-relaxed">
            {cmdWindows}
          </pre>
        </div>

        {/* Linux */}
        <div className="p-3.5 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-white flex items-center space-x-1.5">
              <Terminal className="w-3.5 h-3.5 text-amber-400" />
              <span>Linux (Bash / systemd)</span>
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(cmdLinux, 'linux')}
              className="text-[11px] h-7 px-2.5"
            >
              {copiedOs === 'linux' ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 mr-1" />
                  Copy Command
                </>
              )}
            </Button>
          </div>
          <pre className="p-2.5 rounded bg-[#090d16] border border-gray-800 font-mono text-gray-300 overflow-x-auto text-[11px] leading-relaxed">
            {cmdLinux}
          </pre>
        </div>

        {/* macOS */}
        <div className="p-3.5 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-white flex items-center space-x-1.5">
              <Terminal className="w-3.5 h-3.5 text-purple-400" />
              <span>macOS (Terminal / zsh)</span>
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(cmdMac, 'mac')}
              className="text-[11px] h-7 px-2.5"
            >
              {copiedOs === 'mac' ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 mr-1" />
                  Copy Command
                </>
              )}
            </Button>
          </div>
          <pre className="p-2.5 rounded bg-[#090d16] border border-gray-800 font-mono text-gray-300 overflow-x-auto text-[11px] leading-relaxed">
            {cmdMac}
          </pre>
        </div>

        <div className="pt-2 flex justify-end">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </Modal>
  );
}
