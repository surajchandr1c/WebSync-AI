import React from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export default function WorkersPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-white">Workers</h1>
            <Badge variant="warning">Phase 2: Planned</Badge>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Registered worker nodes, hardware capabilities, and real-time connectivity status.
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
          <CardTitle>Worker Fleet Architecture</CardTitle>
          <CardDescription>
            In Phase 2, this view will show connected worker nodes sending outbound heartbeats.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-[#161f33] p-4 rounded-lg border border-blue-900/30 text-sm text-gray-300">
            <p className="font-semibold text-white mb-2">Planned Functionality:</p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-400">
              <li>Auto-registration of remote machines over outbound HTTPS/WSS</li>
              <li>Live CPU core count, RAM capacity, and GPU device breakdown</li>
              <li>Node state management: Idle, Busy, Draining, Offline</li>
              <li>Worker draining and maintenance mode toggle</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
