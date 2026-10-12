'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useCluster } from '@/context/ClusterContext';
import { JobResponse, JobResultResponse, JobEventResponse } from '@websync/shared-types';
import {
  CheckCircle2,
  XCircle,
  Clock,
  Cpu,
  Server,
  Terminal,
  ShieldAlert,
  Bot,
  Sparkles,
  Copy,
  Check,
  AlertCircle,
  Layers,
  Network,
  Share2,
  Database,
} from 'lucide-react';

interface JobResultModalProps {
  job: JobResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function JobResultModal({ job, isOpen, onClose }: JobResultModalProps) {
  const { client, workers, refreshJobs, refreshEvents, refreshWorkers } = useCluster();
  const [result, setResult] = useState<JobResultResponse | null>(null);
  const [events, setEvents] = useState<JobEventResponse[]>([]);
  const [subtasks, setSubtasks] = useState<JobResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [cancelling, setCancelling] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [installingModel, setInstallingModel] = useState<boolean>(false);
  const [installSuccess, setInstallSuccess] = useState<string | null>(null);
  const [installError, setInstallError] = useState<string | null>(null);

  const handleInstallMissingModel = async () => {
    if (!job) return;
    const targetModel =
      (job.input_payload as any)?.model ||
      job.placement_reason?.requested_model ||
      job.requirements?.model;
    const targetWorker =
      job.assigned_worker_id ||
      workers.find((w) => w.connection_status === 'online' || w.connection_status === 'busy')?.worker_id;

    if (!targetModel || !targetWorker) {
      setInstallError('No eligible online worker found to receive the model download.');
      return;
    }

    setInstallingModel(true);
    setInstallSuccess(null);
    setInstallError(null);
    try {
      const res = await client.pullModel(targetWorker, targetModel);
      setInstallSuccess(res.message);
      await refreshWorkers();
    } catch (e) {
      setInstallError(e instanceof Error ? e.message : 'Model installation failed');
    } finally {
      setInstallingModel(false);
    }
  };

  useEffect(() => {
    if (!isOpen || !job) {
      setResult(null);
      setEvents([]);
      setSubtasks([]);
      setCopied(false);
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

        // Fetch decomposed subtasks if distributed parent job
        if (
          (job.child_count != null && job.child_count > 0) ||
          job.job_type === 'distributed_data_processing'
        ) {
          try {
            const subs = await client.getJobSubtasks(job.job_id);
            if (isSubscribed) setSubtasks(subs);
          } catch (e) {
            console.debug('Failed to load subtasks:', e);
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

  // Parse structured AI output if present
  const aiOutput = useMemo(() => {
    if (!result?.result_output) return null;
    try {
      const parsed = JSON.parse(result.result_output);
      if (parsed && typeof parsed === 'object' && ('response' in parsed || 'model' in parsed)) {
        return parsed as {
          model?: string;
          response?: string;
          eval_count?: number;
          eval_duration_ms?: number;
          total_duration_ms?: number;
          done?: boolean;
        };
      }
    } catch {
      // not JSON
    }
    return null;
  }, [result?.result_output]);

  // Parse structured distributed execution output if present
  const distributedOutput = useMemo(() => {
    if (!result?.result_output) return null;
    try {
      const parsed = JSON.parse(result.result_output);
      if (
        parsed &&
        typeof parsed === 'object' &&
        parsed.execution_mode === 'genuine_distributed_parallel'
      ) {
        return parsed as {
          status: string;
          execution_mode: string;
          total_partitions: number;
          completed_partitions: number;
          total_records: number;
          global_sum: number;
          global_mean: number;
          global_min: number;
          global_max: number;
          executing_workers: string[];
          worker_count: number;
          wall_clock_duration_seconds: number;
          partitions: Array<{
            subtask_job_id: string;
            partition_index: number;
            worker_id: string;
            record_count: number;
            partition_sum: number;
            partition_mean: number;
            partition_min: number;
            partition_max: number;
            duration_seconds: number;
          }>;
          summary: string;
        };
      }
    } catch {
      // not JSON
    }
    return null;
  }, [result?.result_output]);

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

  const handleCopyAiResponse = async () => {
    const textToCopy = aiOutput?.response || result?.result_output || '';
    if (!textToCopy) return;
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard', err);
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
            {job.job_type === 'llm_prompt' ? (
              <Bot className="w-5 h-5 text-indigo-400" />
            ) : (
              <Cpu className="w-5 h-5 text-blue-400" />
            )}
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
            {job.placement_reason.guidance && (
              <div className="p-2.5 bg-amber-950/40 border border-amber-900/50 rounded text-amber-200 text-[11px] mt-1.5 space-y-1.5">
                <p className="leading-relaxed">{job.placement_reason.guidance}</p>
                <div className="pt-1 flex items-center space-x-2">
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={handleInstallMissingModel}
                    disabled={installingModel}
                    className="text-xs bg-amber-600 hover:bg-amber-500 text-white"
                  >
                    {installingModel
                      ? 'Installing...'
                      : `Install '${job.placement_reason.requested_model || 'Model'}' on Available Node`}
                  </Button>
                  {installSuccess && (
                    <span className="text-[11px] font-mono text-emerald-400">✓ {installSuccess}</span>
                  )}
                  {installError && (
                    <span className="text-[11px] font-mono text-rose-400">✗ {installError}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Dedicated Remote AI Output Card */}
        {(job.job_type === 'llm_prompt' || aiOutput) && (
          <div className="rounded-lg border border-indigo-900/50 bg-[#0c1222] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#1f2937] pb-2.5">
              <div className="flex items-center space-x-2 text-indigo-300 font-semibold text-xs">
                <Bot className="w-4 h-4 text-indigo-400" />
                <span>Remote AI Inference Outcome</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-[11px] font-mono bg-indigo-950/60 text-indigo-300 px-2.5 py-0.5 rounded border border-indigo-800/50">
                  {aiOutput?.model || (job.input_payload as any)?.model || 'Model'}
                </span>
                {aiOutput?.eval_count != null && (
                  <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-900/40">
                    {aiOutput.eval_count} tokens
                  </span>
                )}
                {aiOutput?.total_duration_ms != null && (
                  <span className="text-[11px] font-mono text-gray-300 bg-gray-800/40 px-2 py-0.5 rounded border border-gray-700/40">
                    {(aiOutput.total_duration_ms / 1000).toFixed(2)}s
                  </span>
                )}
              </div>
            </div>

            {/* Prompt Submitted */}
            {(job.input_payload as any)?.prompt && (
              <div className="space-y-1">
                <span className="text-[11px] uppercase font-semibold text-gray-400 tracking-wider">
                  Prompt Submitted
                </span>
                <div className="bg-[#080d1a] border border-[#1a2333] rounded p-2.5 text-xs text-gray-200 leading-relaxed font-sans">
                  {(job.input_payload as any).prompt}
                </div>
              </div>
            )}

            {/* AI Generated Response */}
            {aiOutput?.response ? (
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] uppercase font-semibold text-emerald-400 tracking-wider flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Generated AI Response</span>
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyAiResponse}
                    className="flex items-center space-x-1 text-[11px] text-gray-400 hover:text-white transition-colors bg-[#111827] px-2 py-1 rounded border border-[#1f2937]"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-400">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Response</span>
                      </>
                    )}
                  </button>
                </div>
                <div className="bg-[#080d1a] border border-emerald-900/40 rounded p-4 text-xs text-gray-100 font-sans leading-relaxed whitespace-pre-wrap select-text max-h-72 overflow-y-auto">
                  {aiOutput.response}
                </div>
              </div>
            ) : null}

            {/* Error & Troubleshooting Guidance */}
            {result?.result_error && (
              <div className="p-3 bg-rose-950/20 border border-rose-900/40 rounded text-xs text-rose-300 space-y-1.5">
                <div className="font-semibold flex items-center space-x-1.5 text-rose-400">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Inference Error Details</span>
                </div>
                <p className="text-[11px] font-mono text-gray-300 whitespace-pre-wrap">
                  {result.result_error}
                </p>
                {result.result_error.toLowerCase().includes('ollama') && (
                  <div className="p-2.5 bg-amber-950/30 border border-amber-900/40 rounded text-[11px] text-amber-200 space-y-2">
                    <div className="font-semibold">Troubleshooting Steps:</div>
                    <ul className="list-disc list-inside space-y-0.5 text-amber-300/90">
                      <li>Make sure Ollama is installed on the worker PC (https://ollama.com).</li>
                      <li>Run <code className="bg-black/40 px-1 py-0.5 rounded font-mono">ollama serve</code> to start the local inference server.</li>
                      <li>Pull the model with <code className="bg-black/40 px-1 py-0.5 rounded font-mono">ollama pull {(job.input_payload as any)?.model || 'llama3.2:latest'}</code>.</li>
                    </ul>

                    {/* 1-Click Install Action */}
                    <div className="flex items-center justify-between pt-1.5 border-t border-amber-900/40">
                      <span className="text-[11px] text-amber-300">
                        Download model directly to target node:
                      </span>
                      <Button
                        type="button"
                        variant="primary"
                        size="sm"
                        onClick={handleInstallMissingModel}
                        disabled={installingModel}
                        className="text-xs bg-amber-600 hover:bg-amber-500 text-white shrink-0"
                      >
                        {installingModel
                          ? 'Triggering Download...'
                          : `1-Click Install '${(job.input_payload as any)?.model || 'Model'}'`}
                      </Button>
                    </div>

                    {installSuccess && (
                      <p className="text-[11px] font-mono text-emerald-300 pt-1">
                        ✓ {installSuccess}
                      </p>
                    )}
                    {installError && (
                      <p className="text-[11px] font-mono text-rose-300 pt-1">
                        ✗ {installError}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Dedicated Distributed Parallel Computing Card */}
        {(job.job_type === 'distributed_data_processing' || distributedOutput || subtasks.length > 0) && (
          <div className="rounded-lg border border-cyan-900/50 bg-[#09121f] p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-[#1f2937] pb-2.5">
              <div className="flex items-center space-x-2 text-cyan-300 font-semibold text-xs">
                <Network className="w-4 h-4 text-cyan-400" />
                <span>Distributed Parallel Execution & Decomposition</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-[11px] font-mono bg-cyan-950/60 text-cyan-300 px-2.5 py-0.5 rounded border border-cyan-800/50">
                  {distributedOutput?.worker_count ?? (subtasks.length > 0 ? Array.from(new Set(subtasks.map(s => s.assigned_worker_id).filter(Boolean))).length : 0)} Node(s) Engaged
                </span>
                <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-900/40">
                  {distributedOutput?.completed_partitions ?? subtasks.filter(s => s.status === 'COMPLETED').length} / {distributedOutput?.total_partitions ?? subtasks.length} Chunks Complete
                </span>
                {distributedOutput?.wall_clock_duration_seconds != null && (
                  <span className="text-[11px] font-mono text-gray-300 bg-gray-800/40 px-2 py-0.5 rounded border border-gray-700/40">
                    {distributedOutput.wall_clock_duration_seconds}s
                  </span>
                )}
              </div>
            </div>

            {/* Executing Workers Nodes */}
            <div className="space-y-1.5">
              <span className="text-[11px] uppercase font-semibold text-gray-400 tracking-wider">
                Contributing Worker Hardware
              </span>
              <div className="flex flex-wrap gap-2">
                {(distributedOutput?.executing_workers || Array.from(new Set(subtasks.map(s => s.assigned_worker_id).filter(Boolean)))).length > 0 ? (
                  (distributedOutput?.executing_workers || Array.from(new Set(subtasks.map(s => s.assigned_worker_id).filter(Boolean)))).map((wid) => (
                    <div
                      key={wid as string}
                      className="flex items-center space-x-1.5 text-xs font-mono bg-[#0c1829] border border-cyan-800/50 px-2.5 py-1 rounded text-cyan-200"
                    >
                      <Server className="w-3.5 h-3.5 text-cyan-400" />
                      <span>{wid as string}</span>
                    </div>
                  ))
                ) : (
                  <span className="text-xs text-gray-500 italic">Assigning partition subtasks...</span>
                )}
              </div>
            </div>

            {/* Aggregated Statistical Metrics */}
            {distributedOutput && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 bg-[#070d17] p-3 rounded-lg border border-[#1a2333] text-xs">
                <div>
                  <span className="text-gray-400 block text-[10px]">Total Records</span>
                  <span className="font-mono font-bold text-white text-sm">
                    {distributedOutput.total_records.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">Global Sum</span>
                  <span className="font-mono font-bold text-cyan-300 text-sm">
                    {distributedOutput.global_sum.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">Global Mean</span>
                  <span className="font-mono font-bold text-emerald-300 text-sm">
                    {distributedOutput.global_mean.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 block text-[10px]">Min / Max Bounds</span>
                  <span className="font-mono text-gray-300 text-xs">
                    {distributedOutput.global_min} / {distributedOutput.global_max}
                  </span>
                </div>
              </div>
            )}

            {/* Subtasks / Partitions Breakdown Table */}
            {subtasks.length > 0 && (
              <div className="space-y-2 pt-1">
                <span className="text-[11px] uppercase font-semibold text-gray-400 tracking-wider block">
                  Decomposed Parallel Tasks ({subtasks.length} Partitions)
                </span>
                <div className="overflow-x-auto rounded border border-[#1f2937]">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[#0b101a] text-gray-400 uppercase text-[10px] tracking-wider font-semibold border-b border-[#1f2937]">
                      <tr>
                        <th className="py-2 px-3">Subtask ID & Chunk</th>
                        <th className="py-2 px-3">Assigned Node</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3 text-right">Duration</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f2937] text-gray-300 bg-[#070b13]">
                      {subtasks.map((st) => (
                        <tr key={st.job_id} className="hover:bg-[#0d1424]">
                          <td className="py-2 px-3 font-mono text-white">
                            <div>{st.name}</div>
                            <div className="text-[10px] text-gray-500">{st.job_id.slice(0, 8)}...</div>
                          </td>
                          <td className="py-2 px-3 font-mono text-cyan-300">
                            {st.assigned_worker_id || <span className="text-gray-500 italic">Scheduling...</span>}
                          </td>
                          <td className="py-2 px-3">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              st.status === 'COMPLETED'
                                ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40'
                                : st.status === 'RUNNING'
                                ? 'bg-blue-950/60 text-blue-400 border border-blue-800/40'
                                : 'bg-gray-800 text-gray-300'
                            }`}>
                              {st.status}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right font-mono text-gray-300">
                            {st.completed_at && st.started_at
                              ? `${((new Date(st.completed_at).getTime() - new Date(st.started_at).getTime()) / 1000).toFixed(2)}s`
                              : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
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
                <span>Execution Logs & Raw Result Payload</span>
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
