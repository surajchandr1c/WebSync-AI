'use client';

import React, { useState } from 'react';
import { useCluster } from '@/context/ClusterContext';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { JobEventResponse } from '@websync/shared-types';
import {
  ScrollText,
  Search,
  RefreshCw,
  Clock,
  ChevronDown,
  ChevronRight,
  Radio,
  Copy,
  Check,
  Terminal,
} from 'lucide-react';

export default function ActivityLogsPage() {
  const { events, refreshEvents, wsStatus } = useCluster();

  const [search, setSearch] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('all');
  const [expandedEventIds, setExpandedEventIds] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedEventIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyText = (e: React.MouseEvent, text: string, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredEvents = events.filter((ev) => {
    const matchesSearch =
      ev.job_id.toLowerCase().includes(search.toLowerCase()) ||
      ev.event_type.toLowerCase().includes(search.toLowerCase()) ||
      JSON.stringify(ev.details).toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;
    if (eventTypeFilter === 'all') return true;
    return ev.event_type.toUpperCase().includes(eventTypeFilter.toUpperCase());
  });

  const getEventBadge = (type: string) => {
    const upper = type.toUpperCase();
    if (upper.includes('COMPLETED') || upper.includes('SUCCESS')) {
      return <Badge variant="success">{upper}</Badge>;
    }
    if (upper.includes('FAILED') || upper.includes('ERROR')) {
      return <Badge variant="danger">{upper}</Badge>;
    }
    if (upper.includes('STARTED') || upper.includes('RUNNING')) {
      return <Badge variant="info">{upper}</Badge>;
    }
    if (upper.includes('SCHEDULED') || upper.includes('DISPATCH')) {
      return <Badge variant="warning">{upper}</Badge>;
    }
    if (upper.includes('WORKER')) {
      return <Badge variant="info">{upper}</Badge>;
    }
    return <Badge variant="neutral">{upper}</Badge>;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Cluster Activity Logs
            </h1>
            <Badge variant="info">
              {events.length} Recorded Event{events.length === 1 ? '' : 's'}
            </Badge>
          </div>
          <p className="text-gray-400 text-sm max-w-2xl">
            Audit trail of job state transitions, scheduler decisions, and worker cluster events.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Badge
            variant={wsStatus === 'connected' ? 'success' : 'warning'}
            className="flex items-center space-x-1"
          >
            <Radio className="w-3 h-3 animate-pulse" />
            <span>{wsStatus === 'connected' ? 'Live Stream Active' : 'Connecting Stream'}</span>
          </Badge>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refreshEvents()}
            className="h-8 px-2.5 text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4 bg-[#111827]">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by job ID, event type, or details..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-[#0d131f] border border-[#1f2937] rounded-lg text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Event Type Filter Chips */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <button
              onClick={() => setEventTypeFilter('all')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                eventTypeFilter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              All Events
            </button>
            <button
              onClick={() => setEventTypeFilter('CREATED')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                eventTypeFilter === 'CREATED'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              Created
            </button>
            <button
              onClick={() => setEventTypeFilter('SCHEDULED')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                eventTypeFilter === 'SCHEDULED'
                  ? 'bg-purple-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              Scheduled
            </button>
            <button
              onClick={() => setEventTypeFilter('COMPLETED')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                eventTypeFilter === 'COMPLETED'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              Completed
            </button>
            <button
              onClick={() => setEventTypeFilter('FAILED')}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                eventTypeFilter === 'FAILED'
                  ? 'bg-rose-600 text-white'
                  : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
              }`}
            >
              Failed
            </button>
          </div>
        </div>
      </Card>

      {/* Activity Timeline Stream */}
      {filteredEvents.length === 0 ? (
        <Card className="text-center py-16">
          <ScrollText className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white">No activity events recorded</h3>
          <p className="text-xs text-gray-400 max-w-md mx-auto mt-1">
            {search || eventTypeFilter !== 'all'
              ? 'No events match your search query.'
              : 'As workers register and jobs transition through the state machine, audit events appear here in real time.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-2.5">
          {filteredEvents.map((ev) => {
            const isExpanded = !!expandedEventIds[ev.id];
            const dateObj = new Date(ev.created_at);

            return (
              <Card
                key={ev.id}
                className="p-3.5 hover:border-gray-700 transition-all cursor-pointer bg-[#111827]"
                onClick={() => toggleExpand(ev.id)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start space-x-3">
                    <button className="text-gray-400 hover:text-white mt-0.5">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-blue-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </button>

                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        {getEventBadge(ev.event_type)}
                        <span className="text-xs font-mono text-gray-300">
                          Job:{' '}
                          <span className="text-white font-semibold">
                            {ev.job_id.slice(0, 12)}...
                          </span>
                        </span>
                        <button
                          onClick={(e) => copyText(e, ev.job_id, ev.id)}
                          className="text-gray-500 hover:text-white text-[10px]"
                          title="Copy Job ID"
                        >
                          {copiedId === ev.id ? (
                            <Check className="w-3 h-3 text-emerald-400 inline" />
                          ) : (
                            <Copy className="w-3 h-3 inline" />
                          )}
                        </button>
                      </div>

                      <p className="text-xs text-gray-400 font-mono line-clamp-1">
                        {JSON.stringify(ev.details)}
                      </p>
                    </div>
                  </div>

                  <div className="text-right text-[11px] text-gray-500 font-mono shrink-0">
                    <div>{dateObj.toLocaleTimeString()}</div>
                    <div className="text-[10px] text-gray-600">{dateObj.toLocaleDateString()}</div>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-[#1f2937] space-y-2">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">
                      Audit Event Details (JSON)
                    </span>
                    <pre className="p-3 rounded-lg bg-[#090d16] border border-[#1f2937] font-mono text-xs text-emerald-300 overflow-x-auto leading-relaxed">
                      {JSON.stringify(ev.details, null, 2)}
                    </pre>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
