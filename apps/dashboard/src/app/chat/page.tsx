'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useCluster } from '@/context/ClusterContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { JobResponse, JobResultResponse, WorkerResponse } from '@websync/shared-types';
import {
  Sparkles,
  Send,
  Bot,
  User,
  Server,
  Cpu,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Settings2,
  RefreshCw,
  Terminal,
  Zap,
} from 'lucide-react';

const COMMON_MODELS = [
  'llama3.2:latest',
  'llama3.2:3b',
  'llama3.2:1b',
  'gemma4:31b',
  'mistral:latest',
  'phi3:latest',
];

const SAMPLE_PROMPTS = [
  'Explain how distributed consensus works in three concise bullet points.',
  'Write a clean Python function to calculate matrix trace and determinant.',
  'Compare edge AI inference versus centralized cloud LLMs in two sentences.',
];

export default function ChatPage() {
  const { workers, jobs, client, refreshJobs, refreshEvents } = useCluster();

  // Selected worker and inference settings
  const [targetWorkerId, setTargetWorkerId] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('llama3.2:latest');
  const [customModel, setCustomModel] = useState<string>('');
  const [systemPrompt, setSystemPrompt] = useState<string>('');
  const [temperature, setTemperature] = useState<number>(0.7);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // Prompt input state
  const [promptInput, setPromptInput] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  // Cached results for completed jobs
  const [jobResults, setJobResults] = useState<Record<string, JobResultResponse>>({});
  const [copiedJobId, setCopiedJobId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Active / Online workers eligible for workloads
  const eligibleWorkers = useMemo(() => {
    return (workers || []).filter(
      (w) => !w.is_revoked && (w.connection_status === 'online' || w.connection_status === 'busy')
    );
  }, [workers]);

  // Models available from selected worker or across active cluster
  const availableModels = useMemo(() => {
    if (targetWorkerId) {
      const target = eligibleWorkers.find((w) => w.worker_id === targetWorkerId);
      if (target?.supported_models && target.supported_models.length > 0) {
        return target.supported_models;
      }
    }
    const union = Array.from(
      new Set(eligibleWorkers.flatMap((w) => w.supported_models || []))
    );
    return union.length > 0 ? union : COMMON_MODELS;
  }, [targetWorkerId, eligibleWorkers]);

  // Filter historical llm_prompt jobs sorted oldest to newest for chat flow
  const llmJobs = useMemo(() => {
    return (jobs || [])
      .filter((j) => j.job_type === 'llm_prompt')
      .slice()
      .reverse(); // oldest first
  }, [jobs]);

  // Load results for completed jobs
  useEffect(() => {
    const fetchMissingResults = async () => {
      const completed = (jobs || []).filter(
        (j) =>
          j.job_type === 'llm_prompt' &&
          (j.status === 'COMPLETED' || j.status === 'FAILED') &&
          !jobResults[j.job_id]
      );

      for (const j of completed) {
        try {
          const res = await client.getJobResult(j.job_id);
          setJobResults((prev) => ({ ...prev, [j.job_id]: res }));
        } catch {}
      }
    };

    fetchMissingResults();
  }, [jobs, client, jobResults]);

  // Auto-scroll chat to bottom on new jobs
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [llmJobs.length, activeJobId]);

  const handleSendPrompt = async () => {
    if (!promptInput.trim() || isSubmitting) return;

    const promptText = promptInput.trim();
    const finalModel = selectedModel === 'custom' ? customModel.trim() : selectedModel.trim();
    if (!finalModel) return;

    setIsSubmitting(true);
    setPromptInput('');

    try {
      const payload: Record<string, any> = {
        prompt: promptText,
        model: finalModel,
        temperature: Number(temperature),
      };

      if (systemPrompt.trim()) {
        payload.system = systemPrompt.trim();
      }

      if (targetWorkerId) {
        payload.target_worker_id = targetWorkerId;
      }

      const req = {
        name: `AI Prompt: ${promptText.slice(0, 30)}${promptText.length > 30 ? '...' : ''}`,
        job_type: 'llm_prompt',
        input_payload: payload,
        requirements: {
          model: finalModel,
          ...(targetWorkerId ? { target_worker_id: targetWorkerId } : {}),
        },
      };

      const created = await client.createJob(req);
      setActiveJobId(created.job_id);

      await Promise.allSettled([refreshJobs(), refreshEvents()]);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to dispatch AI prompt job');
    } finally {
      setIsSubmitting(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendPrompt();
    }
  };

  const copyToClipboard = (jobId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedJobId(jobId);
    setTimeout(() => setCopiedJobId(null), 2000);
  };

  const parseAiResponse = (rawOutput?: string | null) => {
    if (!rawOutput) return null;
    try {
      const parsed = JSON.parse(rawOutput);
      if (parsed && typeof parsed === 'object') {
        return {
          response: parsed.response || parsed.output || rawOutput,
          model: parsed.model,
          evalCount: parsed.eval_count,
          evalDurationMs: parsed.eval_duration_ms,
          totalDurationMs: parsed.total_duration_ms,
        };
      }
    } catch {}
    return { response: rawOutput };
  };

  return (
    <div className="max-w-7xl mx-auto h-[calc(100vh-6.5rem)] flex flex-col md:flex-row gap-5">
      {/* Left Sidebar: Inference Controls & Node Selection */}
      <div className="w-full md:w-80 shrink-0 flex flex-col gap-4 overflow-y-auto">
        <Card className="border-blue-900/40 bg-gradient-to-b from-[#111827] to-[#0c1424]">
          <CardHeader className="pb-3 border-b border-[#1f2937]">
            <div className="flex items-center space-x-2">
              <div className="w-7 h-7 rounded-md bg-blue-600/20 text-blue-400 flex items-center justify-center border border-blue-500/30">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-base text-white">Inference Engine</CardTitle>
                <p className="text-[11px] text-gray-400">Target Node & Model Config</p>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-4 pt-4">
            {/* Target Worker Selector */}
            <div>
              <label className="text-xs font-semibold text-gray-300 block mb-1.5">
                Target Worker Node
              </label>
              <select
                value={targetWorkerId}
                onChange={(e) => setTargetWorkerId(e.target.value)}
                className="w-full bg-[#0d131f] border border-[#1f2937] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">⚡ Auto-Assign (Fastest Online Node)</option>
                {eligibleWorkers.map((w) => (
                  <option key={w.worker_id} value={w.worker_id}>
                    {w.display_name} ({w.platform} • {w.cpu_utilization?.toFixed(0)}% CPU)
                  </option>
                ))}
              </select>

              <div className="mt-1 flex items-center justify-between text-[11px] text-gray-400">
                <span>
                  {eligibleWorkers.length} online worker{eligibleWorkers.length === 1 ? '' : 's'}
                </span>
                {eligibleWorkers.length === 0 && (
                  <span className="text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> No active workers
                  </span>
                )}
              </div>
            </div>

            {/* AI Model Selector */}
            <div>
              <label className="text-xs font-semibold text-gray-300 block mb-1.5">
                Inference Model
              </label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full bg-[#0d131f] border border-[#1f2937] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              >
                {availableModels.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
                <option value="custom">✏️ Custom Model Identifier...</option>
              </select>

              {selectedModel === 'custom' && (
                <input
                  type="text"
                  placeholder="e.g. gemma4:31b, mistral:7b"
                  value={customModel}
                  onChange={(e) => setCustomModel(e.target.value)}
                  className="mt-2 w-full bg-[#0d131f] border border-[#1f2937] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              )}
            </div>

            {/* Advanced Settings Toggle */}
            <div className="pt-2 border-t border-[#1f2937]/70">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center justify-between w-full text-xs text-gray-400 hover:text-white transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Settings2 className="w-3.5 h-3.5" /> Parameters
                </span>
                {showAdvanced ? (
                  <ChevronUp className="w-3.5 h-3.5" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
              </button>

              {showAdvanced && (
                <div className="mt-3 space-y-3">
                  <div>
                    <div className="flex justify-between text-[11px] text-gray-300 mb-1">
                      <span>Temperature</span>
                      <span className="font-mono text-blue-400">{temperature}</span>
                    </div>
                    <input
                      type="range"
                      min="0.0"
                      max="1.5"
                      step="0.1"
                      value={temperature}
                      onChange={(e) => setTemperature(parseFloat(e.target.value))}
                      className="w-full accent-blue-500 h-1.5 bg-[#0d131f] rounded-lg"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] text-gray-300 block mb-1">
                      System Prompt (Optional)
                    </label>
                    <textarea
                      rows={2}
                      placeholder="You are an expert distributed systems engineer."
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      className="w-full bg-[#0d131f] border border-[#1f2937] rounded-lg p-2 text-xs text-white resize-none focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Example Prompt Starters */}
        <Card className="border-[#1f2937] bg-[#111827]/70 hidden md:block">
          <CardHeader className="py-2.5 px-4 border-b border-[#1f2937]">
            <span className="text-xs font-semibold text-gray-300 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" /> Prompt Ideas
            </span>
          </CardHeader>
          <CardContent className="p-3 space-y-2">
            {SAMPLE_PROMPTS.map((sample, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setPromptInput(sample)}
                className="w-full text-left text-[11px] text-gray-400 hover:text-white bg-[#0d131f] hover:bg-[#162035] p-2 rounded border border-[#1f2937] transition-all line-clamp-2"
              >
                "{sample}"
              </button>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Main Chat Feed Stage */}
      <div className="flex-1 flex flex-col bg-[#0b101b] border border-[#1f2937] rounded-xl overflow-hidden shadow-2xl">
        {/* Chat Feed Header */}
        <div className="h-14 px-5 border-b border-[#1f2937] bg-[#111827]/80 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                Remote AI Prompt Session
                <Badge variant="info" className="text-[10px] py-0 px-1.5">
                  llm_prompt
                </Badge>
              </h2>
            </div>
          </div>

          <div className="flex items-center space-x-3 text-xs text-gray-400">
            <span className="hidden sm:inline-flex items-center gap-1">
              <Bot className="w-3.5 h-3.5 text-blue-400" />
              Model: <strong className="text-white font-mono">{selectedModel}</strong>
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                refreshJobs();
                refreshEvents();
              }}
              className="h-7 px-2 text-xs"
            >
              <RefreshCw className="w-3 h-3" />
            </Button>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {llmJobs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-500">
              <div className="w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center mb-4 text-blue-400 shadow-inner">
                <Bot className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-white mb-1">WebSync AI Prompt Studio</h3>
              <p className="text-xs text-gray-400 max-w-md mb-6 leading-relaxed">
                Submit natural-language prompts to execute securely on connected distributed nodes.
                Inference runs locally on the node using Ollama or configured inference engines.
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {SAMPLE_PROMPTS.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => setPromptInput(p)}
                    className="text-xs bg-[#111827] hover:bg-[#1f2937] text-gray-300 px-3 py-1.5 rounded-full border border-[#1f2937] transition-all"
                  >
                    "{p.slice(0, 42)}..."
                  </button>
                ))}
              </div>
            </div>
          ) : (
            llmJobs.map((job) => {
              const res = jobResults[job.job_id];
              const parsed = parseAiResponse(res?.result_output);
              const promptText = job.input_payload?.prompt || job.name;
              const assignedWorker = workers.find((w) => w.worker_id === job.assigned_worker_id);

              return (
                <div key={job.job_id} className="space-y-3">
                  {/* User Question Bubble */}
                  <div className="flex justify-end items-start gap-3 pl-8">
                    <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-2xl shadow-lg">
                      <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">
                        {promptText}
                      </p>
                      <div className="mt-1.5 flex items-center justify-end text-[10px] text-blue-200/80 gap-1.5">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(job.created_at).toLocaleTimeString()}</span>
                      </div>
                    </div>
                    <div className="w-8 h-8 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
                      <User className="w-4 h-4" />
                    </div>
                  </div>

                  {/* AI Worker Response Bubble */}
                  <div className="flex items-start gap-3 pr-8">
                    <div className="w-8 h-8 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 mt-1">
                      <Bot className="w-4 h-4" />
                    </div>

                    <div className="flex-1 bg-[#111827] border border-[#1f2937] rounded-2xl rounded-tl-sm p-4 max-w-3xl shadow-lg">
                      {/* Worker Header Info */}
                      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 mb-2.5 border-b border-[#1f2937]/70 text-[11px]">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white flex items-center gap-1.5">
                            <Server className="w-3.5 h-3.5 text-blue-400" />
                            {assignedWorker?.display_name || job.assigned_worker_id || 'Worker Node'}
                          </span>
                          <span className="text-gray-500 font-mono">
                            ({job.input_payload?.model || 'model'})
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          {job.status === 'RUNNING' && (
                            <Badge variant="info" className="animate-pulse">
                              RUNNING
                            </Badge>
                          )}
                          {job.status === 'QUEUED' && (
                            <Badge variant="neutral">QUEUED</Badge>
                          )}
                          {job.status === 'SCHEDULED' && (
                            <Badge variant="warning">SCHEDULED</Badge>
                          )}
                          {job.status === 'COMPLETED' && (
                            <Badge variant="success">COMPLETED</Badge>
                          )}
                          {job.status === 'FAILED' && (
                            <Badge variant="danger">FAILED</Badge>
                          )}
                        </div>
                      </div>

                      {/* Response Body */}
                      {job.status === 'RUNNING' && (
                        <div className="py-4 flex items-center space-x-3 text-xs text-blue-400">
                          <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                          <span>Generating AI response on worker node...</span>
                        </div>
                      )}

                      {job.status === 'QUEUED' && (
                        <p className="text-xs text-gray-400 italic py-2">
                          Job queued. Waiting for resource-aware scheduler assignment...
                        </p>
                      )}

                      {job.status === 'SCHEDULED' && (
                        <p className="text-xs text-amber-400 italic py-2">
                          Dispatched to target worker node. Initializing inference engine...
                        </p>
                      )}

                      {job.status === 'COMPLETED' && parsed?.response && (
                        <div className="space-y-3">
                          <div className="text-xs sm:text-sm text-gray-100 leading-relaxed whitespace-pre-wrap font-sans">
                            {parsed.response}
                          </div>

                          {/* Metadata Footer */}
                          <div className="pt-2.5 mt-2.5 border-t border-[#1f2937]/50 flex flex-wrap items-center justify-between gap-2 text-[10px] text-gray-400">
                            <div className="flex items-center gap-3 font-mono">
                              {res?.result_duration_seconds !== undefined && (
                                <span>⏱️ {res.result_duration_seconds?.toFixed(2)}s</span>
                              )}
                              {parsed.evalCount && (
                                <span>📊 {parsed.evalCount} tokens</span>
                              )}
                              <span>⚡ exit: {res?.result_exit_code ?? 0}</span>
                            </div>

                            <button
                              type="button"
                              onClick={() => copyToClipboard(job.job_id, parsed.response || '')}
                              className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#162035] hover:bg-[#1e2c49] text-gray-300 hover:text-white transition-colors"
                            >
                              {copiedJobId === job.job_id ? (
                                <>
                                  <Check className="w-3 h-3 text-emerald-400" /> Copied
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3" /> Copy Output
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      )}

                      {job.status === 'FAILED' && (
                        <div className="bg-rose-950/20 border border-rose-900/30 rounded-lg p-3 text-xs text-rose-300 space-y-1">
                          <div className="font-semibold flex items-center gap-1.5 text-rose-200">
                            <XCircle className="w-4 h-4 text-rose-400" /> Execution Failed
                          </div>
                          <p className="font-mono text-[11px] whitespace-pre-wrap">
                            {res?.result_error || 'Execution terminated with error'}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3 sm:p-4 bg-[#111827] border-t border-[#1f2937] shrink-0">
          <div className="relative flex items-end bg-[#0d131f] border border-[#1f2937] rounded-xl focus-within:border-blue-500 shadow-inner">
            <textarea
              ref={textareaRef}
              rows={2}
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter your prompt... (Press Enter to send, Shift+Enter for newline)"
              disabled={isSubmitting}
              className="w-full bg-transparent px-4 py-3 text-xs sm:text-sm text-white resize-none focus:outline-none placeholder:text-gray-500 disabled:opacity-50"
            />

            <div className="p-2 flex items-center space-x-2">
              <span className="text-[10px] font-mono text-gray-500 hidden sm:inline">
                {promptInput.length}/32768
              </span>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSendPrompt}
                disabled={isSubmitting || !promptInput.trim()}
                className="h-8 px-3 rounded-lg flex items-center gap-1.5"
              >
                {isSubmitting ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Send</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
