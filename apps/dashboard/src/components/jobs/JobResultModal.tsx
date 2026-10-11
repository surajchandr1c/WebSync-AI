'use client';

import React, { useEffect, useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useCluster } from '@/context/ClusterContext';
import { JobResponse, JobResultResponse, JobEventResponse } from '@websync/shared-types';
import { CheckCircle2, XCircle, Clock, Cpu, Server, Terminal, ShieldAlert } from 'lucide-react';

interface JobResultModalProps {
  job: JobResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function JobResultModal({ job, isOpen, onClose }: JobResultModalProps) {
  const { client, refreshJobs, refreshEvents } = useCluster();
  const [result, setResult] = useState<JobResultResponse | null>(null);
  const [events, setEvents] = useState<JobEventResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [cancelling, setCancelling] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen || !job) {
      setResult(null);
      setEvents([]);
      return;
    }

    let isSubscribed = true;

    const loadData = async () => {
      setLoading(true);
      try {
        // Fetch job result if completed or failed
        if (job.status === 'COMPLETED' || job.status === 'FAILED' || job.status === 'CANCELLED') {
          try {
            const res = await client.getJobResult(job.job_id);
            if (isSubscribed) setResult(res);
          } catch (e) {
            console.debug('Result not yet ready:', e);
          }
        }

        // Fetch audit events
        try {
          const evRes = await client.getJobEvents(job.job_id);
          if (isSubscribed) setEvents(evRes.items);
        } catch (e) {
          console.debug('Failed to load events:', e);
        }
      } finally {
        if (isSubscribed) setLoading(false);
      }
    };

    loadData();

    return () => {
      isSubscribed = false;
    };
  }, [isOpen, job, client]);

  if (!job) return null;

  const handleCancelJob = async () => {
    setCancelling(true);
    try {
      await client.cancelJob(job.job_id);
      await Promise.allSettled([refreshJobs(), refreshEvents()]);
      onClose();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to cancel job');
    } finally {
      setCancelling(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <Badge variant="success">COMPLETED</Badge>;
      case 'RUNNING':
        return <Badge variant="info">RUNNING</Badge>;
      case 'SCHEDULED':
        return <Badge variant="warning">SCHEDULED</Badge>;
      case 'QUEUED':
        return <Badge variant="neutral">QUEUED</Badge>;
      case 'FAILED':
        return <Badge variant="danger">FAILED</Badge>;
      case 'CANCELLED':
        return <Badge variant="neutral">CANCELLED</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const isTerminal =
    job.status === 'COMPLETED' || job.status === 'FAILED' || job.status === 'CANCELLED';

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center justify-between w-full pr-8">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-white">{job.name}</span>
            {getStatusBadge(job.status)}
          </div>
        </div>
      }
      description={`Job ID: ${job.job_id}`}
      maxWidth="max-w-3xl"
    >
      <div className="space-y-5">
        {/* Top Summary Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#0d131f] p-3.5 rounded-lg border border-[#1f2937] text-xs">
          <div>
            <span className="text-gray-400 block mb-0.5">Workload Type</span>
            <span className="font-mono font-medium text-blue-400">{job.job_type}</span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Assigned Node</span>
            <span className="font-mono text-gray-200">
              {job.assigned_worker_id || 'Pending Placement'}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Submitted</span>
            <span className="text-gray-300">
              {new Date(job.created_at).toLocaleTimeString()}
            </span>
          </div>
          <div>
            <span className="text-gray-400 block mb-0.5">Execution Duration</span>
            <span className="text-emerald-400 font-mono">
              {result?.result_duration_seconds != null
                ? `${result.result_duration_seconds.toFixed(2)}s`
                : '—'}
            </span>
          </div>
        </div>

        {/* Scheduler Placement Explanation */}
        {job.placement_reason && (
          <div className="p-3.5 rounded-lg bg-indigo-950/20 border border-indigo-900/40 text-xs space-y-1.5">
            <div className="flex items-center space-x-2 text-indigo-300 font-semibold">
              <Server className="w-4 h-4 text-indigo-400" />
              <span>Adaptive Placement Decision</span>
            </div>
            <p className="text-gray-300 text-[11px] leading-relaxed">
              Selected Worker:{' '}
              <strong className="text-white font-mono">
                {job.placement_reason.selected_worker_id || job.assigned_worker_id}
              </strong>
              {job.placement_reason.strategy && (
                <span> (Strategy: {job.placement_reason.strategy})</span>
              )}
            </p>
            {job.placement_reason.selected_score !== undefined && (
              <div className="font-mono text-[11px] text-indigo-200 pt-1">
                Candidate Score: {job.placement_reason.selected_score.toFixed(4)}
              </div>
            )}
          </div>
        )}

        {/* Execution Output / Terminal View */}
        {(result?.result_output || result?.result_error || job.status === 'COMPLETED' || job.status === 'FAILED') && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-gray-300 flex items-center space-x-1.5">
                <Terminal className="w-4 h-4 text-blue-400" />
                <span>Execution Logs & Result Payload</span>
              </span>
              <span className="font-mono text-gray-400">
                Exit Code: {result?.result_exit_code ?? '—'}
              </span>
            </div>

            <pre className="bg-[#090d16] border border-[#1f2937] p-4 rounded-lg text-xs font-mono text-emerald-300 overflow-x-auto max-h-56 leading-relaxed whitespace-pre-wrap">
              {result?.result_output || result?.result_error || (loading ? 'Loading execution logs...' : 'No output recorded.')}
            </pre>
          </div>
        )}

        {/* Workload Inputs */}
        <div className="space-y-1.5">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
            Input Payload
          </span>
          <pre className="bg-[#0d131f] border border-[#1f2937] p-3 rounded-lg text-[11px] font-mono text-gray-300 overflow-x-auto max-h-36">
            {JSON.stringify(job.input_payload, null, 2)}
          </pre>
        </div>

        {/* Audit Trail Timeline */}
        {events.length > 0 && (
          <div className="space-y-2 pt-1">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
              Lifecycle Audit Trail ({events.length} events)
            </span>
            <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
              {events.map((ev) => (
                <div
                  key={ev.id}
                  className="flex items-center justify-between text-[11px] p-2 rounded bg-[#0d131f] border border-[#1f2937]"
                >
                  <div className="flex items-center space-x-2">
                    <span className="font-mono font-semibold text-blue-400">{ev.event_type}</span>
                    <span className="text-gray-400 truncate max-w-xs">
                      {JSON.stringify(ev.details)}
                    </span>
                  </div>
                  <span className="text-gray-500 font-mono text-[10px] shrink-0">
                    {new Date(ev.created_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-[#1f2937]">
          <div>
            {!isTerminal && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelJob}
                disabled={cancelling}
                className="text-rose-400 border-rose-900/50 hover:bg-rose-950/30"
              >
                <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                {cancelling ? 'Cancelling...' : 'Cancel Job'}
              </Button>
            )}
          </div>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
