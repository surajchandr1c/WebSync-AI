import React from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export default function LogsPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-white">Activity Logs</h1>
            <Badge variant="warning">Phase 5: Planned</Badge>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Real-time audit log streams, worker connectivity events, and job execution logs.
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
          <CardTitle>Centralized Audit & Event Streaming</CardTitle>
          <CardDescription>
            In Phase 5, this view will stream WebSocket logs from coordinators and workers.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-[#161f33] p-4 rounded-lg border border-blue-900/30 text-sm text-gray-300">
            <p className="font-semibold text-white mb-2">Planned Functionality:</p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-400">
              <li>WebSocket-driven live cluster event feed</li>
              <li>Filterable logs by Worker ID, Job ID, and severity level (INFO, WARN, ERROR)</li>
              <li>Execution stdout/stderr streaming in terminal viewer</li>
              <li>Security audit logs: registration tokens, auth attempts, node disconnects</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
