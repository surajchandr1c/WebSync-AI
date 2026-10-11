import React from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export default function JobsPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-white">Jobs</h1>
            <Badge variant="warning">Phase 3: Planned</Badge>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Workload submission, execution queues, status tracking, and result retrieval.
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
          <CardTitle>Distributed Job Scheduling</CardTitle>
          <CardDescription>
            In Phase 3, this view will provide workload submission and real-time execution inspection.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-[#161f33] p-4 rounded-lg border border-blue-900/30 text-sm text-gray-300">
            <p className="font-semibold text-white mb-2">Planned Functionality:</p>
            <ul className="list-disc list-inside space-y-1.5 text-gray-400">
              <li>Direct workload submission (Python scripts, batch computations)</li>
              <li>Resource matching (CPU cores, RAM requirements, GPU detection)</li>
              <li>Job lifecycle states: Queued, Dispatched, Running, Completed, Failed</li>
              <li>Execution stdout/stderr streaming and artifact downloads</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
