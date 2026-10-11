import React from 'react';
import { Badge } from '@/components/ui/Badge';

export function Header() {
  return (
    <header className="h-16 border-b border-[#1f2937] bg-[#111827]/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center space-x-3">
        <h2 className="text-sm font-medium text-gray-400">Distributed Compute Mesh</h2>
        <span className="text-gray-600">/</span>
        <span className="text-sm font-semibold text-gray-200">Phase 1: Architecture & Foundation</span>
      </div>

      <div className="flex items-center space-x-4">
        <Badge variant="info">Phase 1 Active</Badge>
        <div className="text-xs text-gray-500 font-mono">Coordinator Port: 8000</div>
      </div>
    </header>
  );
}
