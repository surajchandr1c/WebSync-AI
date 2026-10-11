import React, { useState } from 'react';
import { Job, Worker } from '../../types';
import {
  Briefcase,
  CheckCircle2,
  AlertCircle,
  XCircle,
  PlusCircle,
  Search,
  Eye,
  X,
} from 'lucide-react';

interface JobsTabProps {
  jobs: Job[];
  workers: Worker[];
  onSubmitJob: (payload: {
    task_type: string;
    payload?: Record<string, any>;
    requirements?: Record<string, any>;
    priority?: number;
    timeout_seconds?: number;
  }) => Promise<void>;
  onCancelJob: (jobId: string) => Promise<void>;
  isSubmitting: boolean;
  isOpenSubmitModal: boolean;
  setIsOpenSubmitModal: (open: boolean) => void;
}

export const JobsTab: React.FC<JobsTabProps> = ({
  jobs,
  workers: _workers,
  onSubmitJob,
  onCancelJob,
  isSubmitting,
  isOpenSubmitModal,
  setIsOpenSubmitModal,
}) => {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  // New Job Form State
  const [taskType, setTaskType] = useState('compute');
  const [codePayload, setCodePayload] = useState(
    '# WebSync Distributed Task\nimport math\n\ndef run():\n    return {"primes": [x for x in range(2, 50) if all(x % d != 0 for d in range(2, int(math.isqrt(x)) + 1))]}\n'
  );
  const [minCores, setMinCores] = useState<number>(1);
  const [minMemoryGb, setMinMemoryGb] = useState<number>(1);
  const [requireGpu, setRequireGpu] = useState(false);
  const [priority, setPriority] = useState(1);
  const [timeoutSec, setTimeoutSec] = useState(120);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmitJob({
      task_type: taskType,
      payload: { code: codePayload, args: {} },
      requirements: {
        min_cpu_cores: minCores,
        min_memory_bytes: minMemoryGb * 1024 ** 3,
        require_gpu: requireGpu,
      },
      priority,
      timeout_seconds: timeoutSec,
    });
    setIsOpenSubmitModal(false);
  };

  const filtered = jobs.filter((j) => {
    const matchesSearch =
      (j.title || '').toLowerCase().includes(search.toLowerCase()) ||
      j.id.toLowerCase().includes(search.toLowerCase()) ||
      j.task_type.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filterStatus === 'all' || j.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Workload Management</h2>
          <p className="text-xs text-slate-400 mt-1">
            Dispatch distributed computational jobs to resource-aware remote nodes.
          </p>
        </div>
        <button
          onClick={() => setIsOpenSubmitModal(true)}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-xl flex items-center space-x-2 shadow-lg shadow-cyan-600/20 transition self-start sm:self-auto"
        >
          <PlusCircle className="w-4 h-4" />
          <span>Dispatch New Job</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search jobs by ID or type..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
          {['all', 'pending', 'scheduled', 'running', 'completed', 'failed'].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wider transition ${
                filterStatus === status
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                  : 'text-slate-400 hover:text-slate-200 bg-slate-950 border border-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Jobs Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Job ID & Title</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Assigned Worker</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-500 font-sans">
                    <Briefcase className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                    No jobs match the current criteria.
                  </td>
                </tr>
              ) : (
                filtered.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/40 transition">
                    <td className="px-4 py-3.5 font-sans font-medium text-slate-200">
                      <div>{job.title}</div>
                      <div className="text-[10px] text-slate-500 font-mono mt-0.5">{job.id}</div>
                    </td>
                    <td className="px-4 py-3.5 text-cyan-400">{job.task_type}</td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold ${
                          job.status === 'completed'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : job.status === 'running'
                            ? 'bg-cyan-950 text-cyan-300 border border-cyan-800 animate-pulse'
                            : job.status === 'failed'
                            ? 'bg-rose-950 text-rose-300 border border-rose-800'
                            : job.status === 'scheduled'
                            ? 'bg-indigo-950 text-indigo-300 border border-indigo-800'
                            : 'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-slate-400">
                      {job.assigned_worker_name || job.assigned_worker_id || '—'}
                    </td>
                    <td className="px-4 py-3.5 text-slate-500">
                      {new Date(job.created_at).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-3.5 text-right font-sans space-x-2">
                      <button
                        onClick={() => setSelectedJob(job)}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 hover:border-slate-600 transition inline-flex items-center space-x-1"
                        title="View Job Details & Output"
                      >
                        <Eye className="w-3 h-3" />
                        <span>Inspect</span>
                      </button>

                      {(job.status === 'running' || job.status === 'pending' || job.status === 'scheduled') && (
                        <button
                          onClick={() => onCancelJob(job.id)}
                          className="px-2.5 py-1 bg-rose-950/60 hover:bg-rose-900 text-rose-300 rounded border border-rose-800 transition inline-flex items-center space-x-1"
                          title="Cancel Job"
                        >
                          <XCircle className="w-3 h-3" />
                          <span>Cancel</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Submit Job Modal */}
      {isOpenSubmitModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Briefcase className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">Dispatch Distributed Job</h3>
              </div>
              <button
                onClick={() => setIsOpenSubmitModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Task Type</label>
                <input
                  type="text"
                  value={taskType}
                  onChange={(e) => setTaskType(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                  placeholder="e.g. compute, matrix_mul, inference"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Task Payload / Code</label>
                <textarea
                  rows={5}
                  value={codePayload}
                  onChange={(e) => setCodePayload(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                  placeholder="Executable task script or input parameters..."
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Min CPU Cores</label>
                  <input
                    type="number"
                    min="1"
                    max="64"
                    value={minCores}
                    onChange={(e) => setMinCores(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Min RAM (GB)</label>
                  <input
                    type="number"
                    min="1"
                    max="128"
                    value={minMemoryGb}
                    onChange={(e) => setMinMemoryGb(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Priority</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={priority}
                    onChange={(e) => setPriority(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Timeout (Seconds)</label>
                  <input
                    type="number"
                    min="10"
                    max="3600"
                    value={timeoutSec}
                    onChange={(e) => setTimeoutSec(parseInt(e.target.value) || 120)}
                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="requireGpu"
                  checked={requireGpu}
                  onChange={(e) => setRequireGpu(e.target.checked)}
                  className="rounded border-slate-700 text-cyan-600 focus:ring-cyan-500"
                />
                <label htmlFor="requireGpu" className="text-slate-300 select-none">
                  Require Dedicated GPU (NVIDIA CUDA / DirectML)
                </label>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsOpenSubmitModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-lg shadow-lg shadow-cyan-600/20 transition disabled:opacity-50"
                >
                  {isSubmitting ? 'Dispatching...' : 'Dispatch Workload'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Inspect Job Details Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">{selectedJob.title}</h3>
                <p className="text-[11px] font-mono text-slate-400">ID: {selectedJob.id}</p>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-3 gap-2 bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-[11px]">
                <div>
                  <span className="text-slate-500">Status: </span>
                  <span className="text-cyan-400 font-bold uppercase">{selectedJob.status}</span>
                </div>
                <div>
                  <span className="text-slate-500">Task Type: </span>
                  <span className="text-slate-200">{selectedJob.task_type}</span>
                </div>
                <div>
                  <span className="text-slate-500">Worker: </span>
                  <span className="text-slate-200">{selectedJob.assigned_worker_id || 'unassigned'}</span>
                </div>
              </div>

              {selectedJob.payload && (
                <div>
                  <div className="text-slate-400 font-semibold mb-1">Job Payload:</div>
                  <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-slate-300 font-mono text-[11px] max-h-40 overflow-y-auto">
                    {JSON.stringify(selectedJob.payload, null, 2)}
                  </pre>
                </div>
              )}

              {selectedJob.result && (
                <div>
                  <div className="text-emerald-400 font-semibold mb-1 flex items-center space-x-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Execution Result Output:</span>
                  </div>
                  <pre className="p-3 bg-slate-950 border border-emerald-900/40 rounded-lg text-emerald-300 font-mono text-[11px] max-h-48 overflow-y-auto">
                    {JSON.stringify(selectedJob.result, null, 2)}
                  </pre>
                </div>
              )}

              {selectedJob.error_message && (
                <div>
                  <div className="text-rose-400 font-semibold mb-1 flex items-center space-x-1">
                    <AlertCircle className="w-3.5 h-3.5" />
                    <span>Failure Reason / Traceback:</span>
                  </div>
                  <pre className="p-3 bg-slate-950 border border-rose-900/40 rounded-lg text-rose-300 font-mono text-[11px] max-h-48 overflow-y-auto">
                    {selectedJob.error_message}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setSelectedJob(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
