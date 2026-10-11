'use client';

import React, { useState } from 'react';
import { useCluster } from '@/context/ClusterContext';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { SubmitJobModal } from '@/components/jobs/SubmitJobModal';
import { JobResultModal } from '@/components/jobs/JobResultModal';
import { JobResponse } from '@websync/shared-types';
import {
  PlaySquare,
  Search,
  Plus,
  Server,
  Clock,
  Terminal,
  ShieldAlert,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';

export default function JobsPage() {
  const { jobs, isLoading, client, refreshJobs, refreshEvents } = useCluster();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [selectedJob, setSelectedJob] = useState<JobResponse | null>(null);
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.name.toLowerCase().includes(search.toLowerCase()) ||
      job.job_id.toLowerCase().includes(search.toLowerCase()) ||
      (job.assigned_worker_id &&
        job.assigned_worker_id.toLowerCase().includes(search.toLowerCase()));

    if (!matchesSearch) return false;
    if (statusFilter !== 'all' && job.status !== statusFilter) return false;
    if (typeFilter !== 'all' && job.job_type !== typeFilter) return false;
    return true;
  });

  const runningCount = jobs.filter((j) => j.status === 'RUNNING').length;
  const queuedCount = jobs.filter((j) => j.status === 'QUEUED' || j.status === 'SCHEDULED').length;
  const completedCount = jobs.filter((j) => j.status === 'COMPLETED').length;
  const failedCount = jobs.filter((j) => j.status === 'FAILED').length;

  const copyJobId = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCancelJob = async (e: React.MouseEvent, jobId: string) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to cancel job ${jobId}?`)) return;
    setCancellingId(jobId);
    try {
      await client.cancelJob(jobId);
      await Promise.allSettled([refreshJobs(), refreshEvents()]);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to cancel job');
    } finally {
      setCancellingId(null);
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

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Jobs & Scheduling
            </h1>
            <Badge variant="info">{jobs.length} Submitted Workloads</Badge>
          </div>
          <p className="text-gray-400 text-sm max-w-2xl">
            Monitor distributed job execution, adaptive scheduler placements, and inspect stdout results.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsSubmitModalOpen(true)}
            className="flex items-center space-x-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Submit Job</span>
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
              placeholder="Search by job ID, name, or assigned worker..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-[#0d131f] border border-[#1f2937] rounded-lg text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* Status Filter Chips */}
            <div className="flex items-center space-x-1">
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  statusFilter === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
                }`}
              >
                All ({jobs.length})
              </button>
              <button
                onClick={() => setStatusFilter('RUNNING')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  statusFilter === 'RUNNING'
                    ? 'bg-blue-600 text-white'
                    : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
                }`}
              >
                Running ({runningCount})
              </button>
              <button
                onClick={() => setStatusFilter('QUEUED')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  statusFilter === 'QUEUED'
                    ? 'bg-amber-600 text-white'
                    : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
                }`}
              >
                Queued ({queuedCount})
              </button>
              <button
                onClick={() => setStatusFilter('COMPLETED')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  statusFilter === 'COMPLETED'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
                }`}
              >
                Completed ({completedCount})
              </button>
              <button
                onClick={() => setStatusFilter('FAILED')}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  statusFilter === 'FAILED'
                    ? 'bg-rose-600 text-white'
                    : 'bg-[#0d131f] text-gray-400 hover:text-white border border-[#1f2937]'
                }`}
              >
                Failed ({failedCount})
              </button>
            </div>

            {/* Workload Type Selector */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-[#0d131f] border border-[#1f2937] rounded-md px-2.5 py-1 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Workload Types</option>
              <option value="matrix_multiply">matrix_multiply</option>
              <option value="data_processing">data_processing</option>
              <option value="image_processing">image_processing</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Jobs Table */}
      {filteredJobs.length === 0 ? (
        <Card className="text-center py-16">
          <PlaySquare className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white">No jobs found</h3>
          <p className="text-xs text-gray-400 max-w-md mx-auto mt-1 mb-4">
            {search || statusFilter !== 'all' || typeFilter !== 'all'
              ? 'No jobs match your filter criteria. Try resetting the filters.'
              : 'Submit a new workload to evaluate adaptive scheduling and distributed execution.'}
          </p>
          <Button variant="outline" size="sm" onClick={() => setIsSubmitModalOpen(true)}>
            <Plus className="w-3.5 h-3.5 mr-1" />
            Submit Job
          </Button>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-gray-300">
              <thead className="bg-[#0b101a] border-b border-[#1f2937] text-gray-400 uppercase text-[10px] tracking-wider font-semibold">
                <tr>
                  <th className="py-3 px-4">Job Name & ID</th>
                  <th className="py-3 px-4">Workload</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Assigned Worker</th>
                  <th className="py-3 px-4">Submitted</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1f2937]">
                {filteredJobs.map((job) => {
                  const isCancelable =
                    job.status === 'QUEUED' ||
                    job.status === 'SCHEDULED' ||
                    job.status === 'RUNNING';

                  return (
                    <tr
                      key={job.job_id}
                      onClick={() => setSelectedJob(job)}
                      className="hover:bg-[#151f33] cursor-pointer transition-colors"
                    >
                      {/* Name & ID */}
                      <td className="py-3 px-4">
                        <div className="font-semibold text-white">{job.name}</div>
                        <div className="flex items-center space-x-1.5 text-[10px] text-gray-400 font-mono mt-0.5">
                          <span>{job.job_id.slice(0, 8)}...</span>
                          <button
                            onClick={(e) => copyJobId(e, job.job_id)}
                            className="hover:text-white"
                            title="Copy full Job ID"
                          >
                            {copiedId === job.job_id ? (
                              <Check className="w-3 h-3 text-emerald-400 inline" />
                            ) : (
                              <Copy className="w-3 h-3 text-gray-500 inline" />
                            )}
                          </button>
                        </div>
                      </td>

                      {/* Workload */}
                      <td className="py-3 px-4">
                        <span className="font-mono text-blue-400 px-2 py-0.5 rounded bg-blue-950/40 border border-blue-900/40">
                          {job.job_type}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-4">{getStatusBadge(job.status)}</td>

                      {/* Worker */}
                      <td className="py-3 px-4">
                        {job.assigned_worker_id ? (
                          <div className="flex items-center space-x-1 font-mono text-gray-300">
                            <Server className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                            <span className="truncate max-w-[150px]">
                              {job.assigned_worker_id}
                            </span>
                          </div>
                        ) : (
                          <span className="text-gray-500 italic">Pending placement</span>
                        )}
                      </td>

                      {/* Submitted */}
                      <td className="py-3 px-4 text-gray-400">
                        {new Date(job.created_at).toLocaleTimeString()}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          {isCancelable && (
                            <button
                              onClick={(e) => handleCancelJob(e, job.job_id)}
                              disabled={cancellingId === job.job_id}
                              className="px-2 py-1 rounded bg-rose-950/30 border border-rose-900/50 text-rose-400 hover:bg-rose-900/50 transition-colors text-[11px]"
                              title="Cancel Job"
                            >
                              {cancellingId === job.job_id ? 'Cancelling...' : 'Cancel'}
                            </button>
                          )}
                          <Button
                            variant="secondary"
                            size="sm"
                            className="text-[11px] h-7 px-2.5"
                          >
                            <Terminal className="w-3 h-3 mr-1" />
                            Inspect
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Modals */}
      <SubmitJobModal isOpen={isSubmitModalOpen} onClose={() => setIsSubmitModalOpen(false)} />
      <JobResultModal job={selectedJob} isOpen={!!selectedJob} onClose={() => setSelectedJob(null)} />
    </div>
  );
}
