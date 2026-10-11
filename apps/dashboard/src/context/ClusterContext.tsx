'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { WebSyncClient } from '@websync/api-client';
import {
  HealthResponse,
  WorkerResponse,
  JobResponse,
  JobEventResponse,
  BaseMessageEnvelope,
} from '@websync/shared-types';

export interface TelemetryPoint {
  timestamp: string;
  timeLabel: string;
  avgCpu: number;
  totalRamUsedGb: number;
  totalRamMaxGb: number;
  onlineCount: number;
}

interface ClusterContextType {
  coordinatorUrl: string;
  wsUrl: string;
  wsStatus: 'connected' | 'connecting' | 'disconnected';
  isStale: boolean;
  client: WebSyncClient;
  health: HealthResponse | null;
  healthError: string | null;
  workers: WorkerResponse[];
  jobs: JobResponse[];
  events: JobEventResponse[];
  telemetryHistory: TelemetryPoint[];
  isLoading: boolean;
  lastSync: Date | null;
  refreshAll: () => Promise<void>;
  refreshWorkers: () => Promise<void>;
  refreshJobs: () => Promise<void>;
  refreshEvents: () => Promise<void>;
  setCoordinatorUrl: (url: string) => void;
}

const ClusterContext = createContext<ClusterContextType | null>(null);

const DEFAULT_COORDINATOR_URL =
  process.env.NEXT_PUBLIC_COORDINATOR_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'http://localhost:8000';

const DEFAULT_WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/dashboard';

const TERMINAL_STATES = new Set(['COMPLETED', 'FAILED', 'CANCELLED']);

export function ClusterProvider({ children }: { children: React.ReactNode }) {
  const [coordinatorUrl, setCoordinatorUrlState] = useState<string>(DEFAULT_COORDINATOR_URL);
  const [wsUrl, setWsUrl] = useState<string>(DEFAULT_WS_URL);
  const [wsStatus, setWsStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [workers, setWorkers] = useState<WorkerResponse[]>([]);
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [events, setEvents] = useState<JobEventResponse[]>([]);
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryPoint[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [lastSync, setLastSync] = useState<Date | null>(null);

  const clientRef = useRef<WebSyncClient>(new WebSyncClient({ baseUrl: coordinatorUrl }));
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const processedMessageIdsRef = useRef<Set<string>>(new Set());

  // Determine if data is potentially stale (> 20s without sync when disconnected)
  const isStale =
    wsStatus !== 'connected' &&
    (!lastSync || Date.now() - lastSync.getTime() > 20000);

  const setCoordinatorUrl = (url: string) => {
    setCoordinatorUrlState(url);
    clientRef.current = new WebSyncClient({ baseUrl: url });
    const wsTarget = url.replace(/^http/, 'ws') + '/ws/dashboard';
    setWsUrl(wsTarget);
  };

  // Record a telemetry point based on current workers
  const recordTelemetry = useCallback((currentWorkers: WorkerResponse[]) => {
    const online = currentWorkers.filter(
      (w) => w.connection_status === 'online' || w.connection_status === 'busy'
    );
    const avgCpu =
      online.length > 0
        ? Math.round(
            (online.reduce((acc, w) => acc + (w.cpu_utilization || 0), 0) / online.length) * 10
          ) / 10
        : 0;
    const totalRamMax = currentWorkers.reduce((acc, w) => acc + (w.total_ram_bytes || 0), 0);
    const totalRamAvail = currentWorkers.reduce((acc, w) => acc + (w.available_ram_bytes || 0), 0);
    const totalRamUsed = Math.max(0, totalRamMax - totalRamAvail);

    const now = new Date();
    const point: TelemetryPoint = {
      timestamp: now.toISOString(),
      timeLabel: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      avgCpu,
      totalRamUsedGb: Math.round((totalRamUsed / (1024 * 1024 * 1024)) * 10) / 10,
      totalRamMaxGb: Math.round((totalRamMax / (1024 * 1024 * 1024)) * 10) / 10,
      onlineCount: online.length,
    };

    setTelemetryHistory((prev) => {
      const next = [...prev, point];
      return next.length > 30 ? next.slice(next.length - 30) : next;
    });
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await clientRef.current.getHealth();
      setHealth(h);
      setHealthError(null);
    } catch (err: unknown) {
      setHealth(null);
      setHealthError(err instanceof Error ? err.message : 'Coordinator connection failed');
    }
  }, []);

  const refreshWorkers = useCallback(async () => {
    try {
      const res = await clientRef.current.listWorkers({ page_size: 100 });
      setWorkers(res.items);
      recordTelemetry(res.items);
    } catch (err) {
      console.warn('Failed to refresh workers:', err);
    }
  }, [recordTelemetry]);

  const refreshJobs = useCallback(async () => {
    try {
      const res = await clientRef.current.listJobs({ page_size: 100 });
      setJobs(res.items);
    } catch (err) {
      console.warn('Failed to refresh jobs:', err);
    }
  }, []);

  const refreshEvents = useCallback(async () => {
    try {
      const res = await clientRef.current.listEvents({ page_size: 100 });
      setEvents(res.items);
    } catch (err) {
      console.warn('Failed to refresh events:', err);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setIsLoading(true);
    await Promise.allSettled([
      refreshHealth(),
      refreshWorkers(),
      refreshJobs(),
      refreshEvents(),
    ]);
    setLastSync(new Date());
    setIsLoading(false);
  }, [refreshHealth, refreshWorkers, refreshJobs, refreshEvents]);

  // Initial authoritative baseline load
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Adaptive background polling: 30s when WebSocket connected, 6s when disconnected fallback
  useEffect(() => {
    const pollInterval = wsStatus === 'connected' ? 30000 : 6000;
    const interval = setInterval(() => {
      refreshHealth();
      refreshWorkers();
      refreshJobs();
      refreshEvents();
      setLastSync(new Date());
    }, pollInterval);

    return () => clearInterval(interval);
  }, [wsStatus, refreshHealth, refreshWorkers, refreshJobs, refreshEvents]);

  // WebSocket Connection & Real-Time Event Dispatcher with Envelope Handling & Deduplication
  useEffect(() => {
    let isCancelled = false;

    const connectWs = () => {
      if (isCancelled) return;
      try {
        setWsStatus('connecting');
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isCancelled) return;
          setWsStatus('connected');
          reconnectAttemptsRef.current = 0;
          // Authoritative synchronization upon connecting/reconnecting
          refreshAll();
        };

        ws.onmessage = (event) => {
          if (isCancelled) return;
          try {
            const parsed = JSON.parse(event.data);
            const msgId = parsed.message_id || parsed.id;

            // Deduplication guard: ignore previously processed messages
            if (msgId) {
              if (processedMessageIdsRef.current.has(msgId)) {
                return;
              }
              processedMessageIdsRef.current.add(msgId);
              // Cap memory size of tracked IDs to 300
              if (processedMessageIdsRef.current.size > 300) {
                const first = processedMessageIdsRef.current.values().next().value;
                if (first) processedMessageIdsRef.current.delete(first);
              }
            }

            const eventName = parsed.event || parsed.type;
            const data = parsed.data || parsed.payload || {};

            // Instant updates based on event type
            if (eventName.startsWith('worker.')) {
              refreshWorkers();
            } else if (eventName.startsWith('job.')) {
              const jobId = data.job_id || parsed.job_id;
              const newStatus = data.status;

              // Terminal state overwrite guard
              if (jobId && newStatus) {
                setJobs((currentJobs) =>
                  currentJobs.map((j) => {
                    if (j.job_id === jobId) {
                      // Do not overwrite terminal states with older non-terminal events
                      if (TERMINAL_STATES.has(j.status) && !TERMINAL_STATES.has(newStatus)) {
                        return j;
                      }
                      return { ...j, status: newStatus };
                    }
                    return j;
                  })
                );
              }

              refreshJobs();
              refreshEvents();
            }

            // Append audit event
            if (eventName && data) {
              const syntheticEvent: JobEventResponse = {
                id: msgId || `ws-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                job_id: data.job_id || parsed.job_id || 'system',
                event_type: eventName.toUpperCase().replace('.', '_'),
                details: data,
                created_at: parsed.timestamp || new Date().toISOString(),
              };
              setEvents((prev) => [syntheticEvent, ...prev.slice(0, 99)]);
            }

            setLastSync(new Date());
          } catch (e) {
            console.debug('WS message parse error:', e);
          }
        };

        ws.onerror = () => {
          if (isCancelled) return;
          setWsStatus('disconnected');
        };

        ws.onclose = () => {
          if (isCancelled) return;
          setWsStatus('disconnected');
          // Exponential backoff with random jitter (max 15s)
          reconnectAttemptsRef.current += 1;
          const exp = Math.min(15000, 1000 * Math.pow(1.4, reconnectAttemptsRef.current));
          const jitter = Math.random() * 1000;
          const delay = Math.round(exp + jitter);

          reconnectTimerRef.current = setTimeout(connectWs, delay);
        };
      } catch (err) {
        setWsStatus('disconnected');
        const delay = Math.min(10000, 1000 * Math.pow(1.4, reconnectAttemptsRef.current++));
        reconnectTimerRef.current = setTimeout(connectWs, delay);
      }
    };

    connectWs();

    return () => {
      isCancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [wsUrl, refreshAll, refreshWorkers, refreshJobs, refreshEvents]);

  return (
    <ClusterContext.Provider
      value={{
        coordinatorUrl,
        wsUrl,
        wsStatus,
        isStale,
        client: clientRef.current,
        health,
        healthError,
        workers,
        jobs,
        events,
        telemetryHistory,
        isLoading,
        lastSync,
        refreshAll,
        refreshWorkers,
        refreshJobs,
        refreshEvents,
        setCoordinatorUrl,
      }}
    >
      {children}
    </ClusterContext.Provider>
  );
}

export function useCluster() {
  const context = useContext(ClusterContext);
  if (!context) {
    throw new Error('useCluster must be used within a ClusterProvider');
  }
  return context;
}
