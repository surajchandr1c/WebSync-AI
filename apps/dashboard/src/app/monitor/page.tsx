import React from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export default function ResourceMonitorPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-white">Resource Monitor</h1>
            <Badge variant="warning">Phase 4: Planned</Badge>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Real-time CPU, RAM, and GPU cluster-wide telemetry visualizations.
          </p>
        </div>
        <Link href="/">
          <Button variant="outline" size="sm">
            Back to Overview
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Telemetry Visualization Engine</CardTitle>
          <CardDescription>
            In Phase 4, this view will feature live Recharts graphs for cluster hardware metrics.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-[#161f33] p-4 rounded-lg border border-blue-900/30 text-sm text-gray-300">
            <p className="font-semibold text-white mb-2">Planned Functionality:</p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-400">
              <li>Time-series CPU percentage per node and aggregate cluster usage</li>
              <li>Memory pressure and available RAM monitoring</li>
              <li>Vendor GPU utilization and VRAM allocation charts</li>
              <li>Historical hardware consumption benchmarks</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
