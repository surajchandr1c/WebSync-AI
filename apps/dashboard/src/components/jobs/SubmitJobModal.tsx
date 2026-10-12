'use client';

import React, { useState, useMemo } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Input';
import { useCluster } from '@/context/ClusterContext';
import { ApprovedJobType, JobCreateRequest } from '@websync/shared-types';
import { PlaySquare, AlertCircle, Bot, Sparkles, Server } from 'lucide-react';

interface SubmitJobModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

const COMMON_LLM_MODELS = [
  'llama3.2:latest',
  'llama3.2:3b',
  'llama3.2:1b',
  'llama3:latest',
  'mistral:latest',
  'phi3:latest',
  'gemma2:latest',
];

export function SubmitJobModal({ isOpen, onClose, onSuccess }: SubmitJobModalProps) {
  const { client, workers, refreshWorkers, refreshJobs, refreshEvents } = useCluster();

  const [jobType, setJobType] = useState<ApprovedJobType>('matrix_multiply');
  const [name, setName] = useState<string>('Matrix Multiplication Benchmark');
  const [minCpu, setMinCpu] = useState<number>(1);
  const [minRamMb, setMinRamMb] = useState<number>(512);
  const [gpuRequired, setGpuRequired] = useState<boolean>(false);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(300);

  // Workload specific inputs
  const [matrixDim, setMatrixDim] = useState<number>(100);
  const [dataRecords, setDataRecords] = useState<number>(5000);
  const [partitions, setPartitions] = useState<number>(2);
  const [customJson, setCustomJson] = useState<string>('');
  const [useCustomJson, setUseCustomJson] = useState<boolean>(false);

  // Remote AI Prompt (llm_prompt) inputs
  const [targetWorkerId, setTargetWorkerId] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('llama3.2:latest');
  const [customModel, setCustomModel] = useState<string>('');
  const [promptText, setPromptText] = useState<string>('');
  const [systemPrompt, setSystemPrompt] = useState<string>('');
  const [temperature, setTemperature] = useState<number>(0.7);

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filter online / active workers
  const activeWorkers = useMemo(() => {
    return (workers || []).filter(
      (w) => !w.is_revoked && (w.connection_status === 'online' || w.connection_status === 'busy')
    );
  }, [workers]);

  // Discovered models actually installed across active workers
  const installedClusterModels = useMemo(() => {
    return Array.from(
      new Set(activeWorkers.flatMap((w) => w.supported_models || []))
    );
  }, [activeWorkers]);

  // Determine available models for the selected worker or cluster
  const availableModels = useMemo(() => {
    if (targetWorkerId) {
      const target = activeWorkers.find((w) => w.worker_id === targetWorkerId);
      return target?.supported_models || [];
    }
    return installedClusterModels;
  }, [targetWorkerId, activeWorkers, installedClusterModels]);

  const activeModel = selectedModel === 'custom' ? customModel.trim() : selectedModel.trim();
  const isModelAvailable = useMemo(() => {
    if (!activeModel) return false;
    const req = activeModel.trim().toLowerCase();
    return availableModels.some((m) => {
      const inst = m.trim().toLowerCase();
      if (req === inst) return true;
      if (!req.includes(':')) {
        return inst === `${req}:latest` || inst === req;
      }
      const instCanonical = inst.includes(':') ? inst : `${inst}:latest`;
      return req === instCanonical;
    });
  }, [activeModel, availableModels]);

  const [pullingInline, setPullingInline] = useState<boolean>(false);
  const [pullFeedback, setPullFeedback] = useState<string | null>(null);

  const handleQuickPull = async (targetId: string, modelName: string) => {
    if (!targetId || !modelName) return;
    setPullingInline(true);
    setPullFeedback(null);
    try {
      const res = await client.pullModel(targetId, modelName);
      setPullFeedback(res.message);
      await refreshWorkers();
    } catch (e) {
      setPullFeedback(e instanceof Error ? e.message : 'Pull failed');
    } finally {
      setPullingInline(false);
    }
  };

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value as ApprovedJobType;
    setJobType(val);
    if (val === 'matrix_multiply') {
      setName('Matrix Multiplication Benchmark');
    } else if (val === 'data_processing') {
      setName('Batch Data Transform & Aggregation');
    } else if (val === 'distributed_data_processing') {
      setName('Distributed Parallel Data Pipeline');
    } else if (val === 'llm_prompt') {
      setName('Remote AI Prompt Execution');
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
      const activeModel = selectedModel === 'custom' ? customModel.trim() : selectedModel.trim();

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
        } else if (jobType === 'distributed_data_processing') {
          inputPayload = {
            records_count: Number(dataRecords),
            partitions: Number(partitions),
          };
        } else if (jobType === 'llm_prompt') {
          if (!promptText.trim()) {
            throw new Error('Please enter a natural-language prompt to submit.');
          }
          if (!activeModel) {
            throw new Error('Please specify an AI model identifier.');
          }
          inputPayload = {
            prompt: promptText.trim(),
            model: activeModel,
            system: systemPrompt.trim() || undefined,
            temperature: Number(temperature),
            target_worker_id: targetWorkerId || undefined,
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
          target_worker_id: targetWorkerId || undefined,
          model: jobType === 'llm_prompt' ? activeModel : undefined,
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
          {jobType === 'llm_prompt' ? (
            <Bot className="w-5 h-5 text-indigo-400" />
          ) : (
            <PlaySquare className="w-5 h-5 text-blue-400" />
          )}
          <span>{jobType === 'llm_prompt' ? 'Submit Remote AI Prompt' : 'Submit Computational Job'}</span>
        </div>
      }
      description={
        jobType === 'llm_prompt'
          ? 'Submit a prompt to be executed by a local Ollama AI model on a remote connected worker PC.'
          : 'Dispatch a validated computational workload to the distributed cluster.'
      }
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
              { label: 'distributed_data_processing (Parallel Chunked Distribution)', value: 'distributed_data_processing' },
              { label: 'image_processing (Computer Vision)', value: 'image_processing' },
              { label: 'llm_prompt (Remote AI Inference)', value: 'llm_prompt' },
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

        {/* Remote AI Inference Custom Configuration */}
        {jobType === 'llm_prompt' && !useCustomJson && (
          <div className="p-4 rounded-lg bg-indigo-950/20 border border-indigo-900/40 space-y-4">
            <div className="flex items-center space-x-2 text-xs font-semibold text-indigo-300 uppercase tracking-wider">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>AI Worker & Model Configuration</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label="Target Worker Node"
                value={targetWorkerId}
                onChange={(e) => setTargetWorkerId(e.target.value)}
                options={[
                  { label: '⚡ Auto-Assign (Adaptive scheduler)', value: '' },
                  ...activeWorkers.map((w) => ({
                    label: `${w.display_name || w.hostname} (${w.worker_id})${
                      w.supported_models && w.supported_models.length > 0
                        ? ` [${w.supported_models.length} models]`
                        : ''
                    }`,
                    value: w.worker_id,
                  })),
                ]}
                helperText="Select a specific computer or let the coordinator schedule dynamically."
              />

              <div className="space-y-1">
                <Select
                  label="Inference Model"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  options={
                    availableModels.length > 0
                      ? [
                          ...availableModels.map((m) => ({ label: m, value: m })),
                          { label: '✏️ Custom Model Tag...', value: 'custom' },
                        ]
                      : [
                          { label: '⚠️ No models installed on nodes', value: '' },
                          { label: '✏️ Custom Model Tag...', value: 'custom' },
                        ]
                  }
                  helperText={
                    availableModels.length > 0
                      ? `${availableModels.length} local Ollama model(s) verified on active nodes.`
                      : 'No models currently installed on active workers. Pull a model below.'
                  }
                />
                {selectedModel === 'custom' && (
                  <Input
                    label="Custom Model Name"
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    placeholder="e.g. llama3.2:1b or mistral"
                    required
                  />
                )}
              </div>
            </div>

            {/* Model Unavailability Warning & 1-Click Install Action */}
            {activeModel && !isModelAvailable && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs space-y-2">
                <div className="flex items-start space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                  <div>
                    <span className="font-semibold text-amber-300 block">
                      Model '{activeModel}' is not installed
                    </span>
                    <span className="text-[11px] text-gray-300">
                      {targetWorkerId
                        ? `Target worker '${targetWorkerId}' lacks this model.`
                        : 'No active cluster worker node currently has this model downloaded in local Ollama.'}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-amber-500/20">
                  <span className="text-[11px] text-gray-400">
                    Pull '{activeModel}' onto{' '}
                    {targetWorkerId ? targetWorkerId : activeWorkers[0]?.display_name || 'node'}:
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      handleQuickPull(
                        targetWorkerId || activeWorkers[0]?.worker_id || '',
                        activeModel
                      )
                    }
                    disabled={pullingInline || (!targetWorkerId && activeWorkers.length === 0)}
                    className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded text-[11px] font-medium transition-colors shrink-0"
                  >
                    {pullingInline ? 'Pulling Model...' : `Install on ${targetWorkerId || activeWorkers[0]?.display_name || 'Node'}`}
                  </button>
                </div>

                {pullFeedback && (
                  <p className="text-[11px] font-mono text-emerald-300 pt-1">{pullFeedback}</p>
                )}
              </div>
            )}

            {/* Prompt Textarea */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <label className="font-medium text-gray-200">Prompt</label>
                <span className="text-[11px] text-gray-400">
                  {promptText.length.toLocaleString()} / 32,768 characters
                </span>
              </div>
              <textarea
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                maxLength={32768}
                rows={4}
                required
                placeholder="Enter prompt for the remote worker PC (e.g. Explain quantum computing in three bullet points)..."
                className="w-full text-xs font-sans p-3 bg-[#0a0e17] border border-[#1f2937] rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 leading-relaxed"
              />
            </div>

            {/* Optional System Prompt & Temperature */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div className="sm:col-span-2">
                <Input
                  label="System Prompt (Optional)"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="e.g. You are a concise distributed computing assistant."
                />
              </div>
              <div>
                <Input
                  label="Temperature"
                  type="number"
                  step="0.1"
                  min="0.0"
                  max="2.0"
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  helperText="Default: 0.7"
                />
              </div>
            </div>
          </div>
        )}

        {/* Traditional Computational Workload Inputs */}
        {jobType !== 'llm_prompt' && (
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
                {jobType === 'distributed_data_processing' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                      label="Dataset Record Count"
                      type="number"
                      min={100}
                      max={50000}
                      value={dataRecords}
                      onChange={(e) => setDataRecords(Number(e.target.value))}
                      helperText="Total dataset to partition across available workers."
                    />
                    <Input
                      label="Number of Partitions (Parallel Chunks)"
                      type="number"
                      min={2}
                      max={16}
                      value={partitions}
                      onChange={(e) => setPartitions(Number(e.target.value))}
                      helperText="Decomposed subtasks executed concurrently across nodes."
                    />
                  </div>
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
        )}

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
            {submitting ? 'Submitting & Dispatching...' : jobType === 'llm_prompt' ? 'Send AI Prompt' : 'Submit Job'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
