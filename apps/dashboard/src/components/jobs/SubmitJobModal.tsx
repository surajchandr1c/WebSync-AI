'use client';

import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Input';
import { useCluster } from '@/context/ClusterContext';
import { ApprovedJobType, JobCreateRequest } from '@websync/shared-types';
import { PlaySquare, AlertCircle } from 'lucide-react';

interface SubmitJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function SubmitJobModal({ isOpen, onClose, onSuccess }: SubmitJobModalProps) {
  const { client, refreshJobs, refreshEvents } = useCluster();

  const [jobType, setJobType] = useState<ApprovedJobType>('matrix_multiply');
  const [name, setName] = useState<string>('Matrix Multiplication Benchmark');
  const [minCpu, setMinCpu] = useState<number>(1);
  const [minRamMb, setMinRamMb] = useState<number>(512);
  const [gpuRequired, setGpuRequired] = useState<boolean>(false);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(300);

  // Workload specific inputs
  const [matrixDim, setMatrixDim] = useState<number>(100);
  const [dataRecords, setDataRecords] = useState<number>(5000);
  const [customJson, setCustomJson] = useState<string>('');
  const [useCustomJson, setUseCustomJson] = useState<boolean>(false);

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value as ApprovedJobType;
    setJobType(val);
    if (val === 'matrix_multiply') {
      setName('Matrix Multiplication Benchmark');
    } else if (val === 'data_processing') {
      setName('Batch Data Transform & Aggregation');
    } else {
      setName('Parallel Computing Job');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      let inputPayload: Record<string, any>;

      if (useCustomJson) {
        try {
          inputPayload = JSON.parse(customJson);
        } catch {
          throw new Error('Invalid JSON format in custom input payload.');
        }
      } else {
        if (jobType === 'matrix_multiply') {
          inputPayload = { dim: Number(matrixDim) };
        } else if (jobType === 'data_processing') {
          inputPayload = {
            records: Number(dataRecords),
            operations: ['normalize', 'aggregate', 'checksum'],
          };
        } else {
          inputPayload = { steps: 10 };
        }
      }

      const payload: JobCreateRequest = {
        name: name.trim(),
        job_type: jobType,
        input_payload: inputPayload,
        requirements: {
          min_cpu_cores: Number(minCpu),
          min_ram_mb: Number(minRamMb),
          gpu_required: gpuRequired,
          timeout_seconds: Number(timeoutSeconds),
        },
      };

      await client.createJob(payload);
      await Promise.allSettled([refreshJobs(), refreshEvents()]);

      if (onSuccess) onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit workload');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center space-x-2">
          <PlaySquare className="w-5 h-5 text-blue-400" />
          <span>Submit Computational Job</span>
        </div>
      }
      description="Dispatch a validated computational workload to the distributed cluster."
      maxWidth="max-w-2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="Workload Type"
            value={jobType}
            onChange={handleTypeChange}
            options={[
              { label: 'matrix_multiply (Distributed Math)', value: 'matrix_multiply' },
              { label: 'data_processing (Data Pipelines)', value: 'data_processing' },
              { label: 'image_processing (Computer Vision)', value: 'image_processing' },
            ]}
          />

          <Input
            label="Job Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Distributed Benchmark Run"
            required
          />
        </div>

        {/* Workload Inputs */}
        <div className="p-4 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Execution Payload
            </span>
            <button
              type="button"
              onClick={() => setUseCustomJson(!useCustomJson)}
              className="text-xs text-blue-400 hover:text-blue-300 font-medium"
            >
              {useCustomJson ? 'Use Guided Inputs' : 'Raw JSON Editor'}
            </button>
          </div>

          {!useCustomJson ? (
            <>
              {jobType === 'matrix_multiply' && (
                <Input
                  label="Matrix Dimension (N x N)"
                  type="number"
                  min={2}
                  max={2000}
                  value={matrixDim}
                  onChange={(e) => setMatrixDim(Number(e.target.value))}
                  helperText="Computes square matrix product on worker subprocess."
                />
              )}
              {jobType === 'data_processing' && (
                <Input
                  label="Dataset Record Count"
                  type="number"
                  min={100}
                  max={1000000}
                  value={dataRecords}
                  onChange={(e) => setDataRecords(Number(e.target.value))}
                  helperText="Simulates data extraction, normalization, and statistical summary."
                />
              )}
              {jobType === 'image_processing' && (
                <p className="text-xs text-gray-400">
                  Default image filter parameters will be dispatched to the remote node.
                </p>
              )}
            </>
          ) : (
            <div>
              <textarea
                value={customJson}
                onChange={(e) => setCustomJson(e.target.value)}
                placeholder='{"dim": 100}'
                rows={4}
                className="w-full font-mono text-xs px-3 py-2 bg-[#0a0e17] border border-[#1f2937] rounded-lg text-gray-200 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}
        </div>

        {/* Requirements */}
        <div className="p-4 rounded-lg bg-[#0d131f] border border-[#1f2937] space-y-3">
          <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider block">
            Resource Requirements (Scheduler Filters)
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Input
              label="Min CPU Cores"
              type="number"
              min={1}
              max={64}
              value={minCpu}
              onChange={(e) => setMinCpu(Number(e.target.value))}
            />
            <Input
              label="Min RAM (MB)"
              type="number"
              min={128}
              max={65536}
              value={minRamMb}
              onChange={(e) => setMinRamMb(Number(e.target.value))}
            />
            <Input
              label="Timeout (seconds)"
              type="number"
              min={10}
              max={3600}
              value={timeoutSeconds}
              onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
            />
          </div>

          <label className="flex items-center space-x-2 text-xs text-gray-300 cursor-pointer pt-1">
            <input
              type="checkbox"
              checked={gpuRequired}
              onChange={(e) => setGpuRequired(e.target.checked)}
              className="rounded bg-[#0a0e17] border-gray-700 text-blue-600 focus:ring-blue-500 w-4 h-4"
            />
            <span>Workload requires dedicated GPU accelerator</span>
          </label>
        </div>

        {/* Footer buttons */}
        <div className="flex items-center justify-end space-x-3 pt-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Submitting & Dispatching...' : 'Submit Job'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
