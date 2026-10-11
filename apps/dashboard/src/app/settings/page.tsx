import React from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-white">Settings</h1>
            <Badge variant="info">Configuration</Badge>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            WebSync AI cluster connection and environment settings.
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
          <CardTitle>Environment & Endpoint Configuration</CardTitle>
          <CardDescription>
            These values configure the dashboard connection to the WebSync AI Coordinator.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="bg-[#161f33] p-4 rounded-lg border border-blue-900/30">
              <span className="text-xs text-gray-400 block mb-1">Coordinator API URL</span>
              <span className="font-mono text-white text-sm">http://localhost:8000</span>
              <p className="text-xs text-gray-500 mt-2">Configurable via NEXT_PUBLIC_API_URL</p>
            </div>

            <div className="bg-[#161f33] p-4 rounded-lg border border-blue-900/30">
              <span className="text-xs text-gray-400 block mb-1">WebSocket URL</span>
              <span className="font-mono text-white text-sm">ws://localhost:8000/ws</span>
              <p className="text-xs text-gray-500 mt-2">Configurable via NEXT_PUBLIC_WS_URL</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
