import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TabId,
  ConnectionStatus,
  Worker,
  Job,
  ClusterStats,
  SystemLogEntry,
  LocalWorkerStatus,
  WorkerBinaryInfo,
  DesktopSettings,
} from './types';
import { CoordinatorApiClient } from './services/api';
import {
  getWorkerBinaryStatus,
  getLocalWorkerStatus,
  startLocalWorker,
  stopLocalWorker,
  getLocalWorkerLogs,
} from './services/tauri';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { OverviewTab } from './components/tabs/OverviewTab';
import { WorkersTab } from './components/tabs/WorkersTab';
import { JobsTab } from './components/tabs/JobsTab';
import { ResourceMonitorTab } from './components/tabs/ResourceMonitorTab';
import { ActivityLogsTab } from './components/tabs/ActivityLogsTab';
import { LocalWorkerDaemonTab } from './components/tabs/LocalWorkerDaemonTab';
import { SettingsTab } from './components/tabs/SettingsTab';

const DEFAULT_SETTINGS: DesktopSettings = {
  coordinatorHttpUrl: 'http://localhost:8000',
  coordinatorWsUrl: 'ws://localhost:8000/ws',
  authToken: '',
  workerId: 'worker-local-desktop',
  workerName: 'Local Desktop Worker',
  autoReconnect: true,
  pollIntervalMs: 4000,
};

export default function App() {
  // Load settings from localStorage
  const [settings, setSettings] = useState<DesktopSettings>(() => {
    try {
      const saved = localStorage.getItem('websync_desktop_settings');
      if (saved) return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
    } catch {
      // fallback
    }
    return DEFAULT_SETTINGS;
  });

  const [currentTab, setCurrentTab] = useState<TabId>('overview');
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [latencyMs, setLatencyMs] = useState(0);

  // Cluster data
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [logs, setLogs] = useState<SystemLogEntry[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    status: string;
    latencyMs: number;
    error?: string;
  } | null>(null);

  // Local Worker Daemon state
  const [binaryInfo, setBinaryInfo] = useState<WorkerBinaryInfo>({
    found: false,
    path: null,
    version: null,
  });
  const [daemonStatus, setDaemonStatus] = useState<LocalWorkerStatus>({
    running: false,
    pid: null,
    coordinator_url: null,
    worker_id: null,
    exit_code: null,
    binary_path: null,
  });
  const [daemonLogs, setDaemonLogs] = useState<string[]>([]);
  const [isOperatingDaemon, setIsOperatingDaemon] = useState(false);

  // Jobs modal state
  const [isSubmittingJob, setIsSubmittingJob] = useState(false);
  const [isOpenSubmitModal, setIsOpenSubmitModal] = useState(false);

  // Coordinator API Client instance
  const apiClient = useMemo(
    () => new CoordinatorApiClient(settings.coordinatorHttpUrl, settings.authToken),
    [settings.coordinatorHttpUrl, settings.authToken]
  );

  const addLog = useCallback(
    (level: 'info' | 'warn' | 'error' | 'success', component: SystemLogEntry['component'], message: string) => {
      setLogs((prev) => [
        {
          id: Math.random().toString(36).substring(2, 9),
          timestamp: new Date().toLocaleTimeString(),
          level,
          component,
          message,
        },
        ...prev.slice(0, 400),
      ]);
    },
    []
  );

  // Calculate cluster stats dynamically from real worker telemetry
  const clusterStats: ClusterStats = useMemo(() => {
    const totalWorkers = workers.length;
    const onlineWorkers = workers.filter((w) => w.status === 'online' || w.status === 'busy').length;
    const busyWorkers = workers.filter((w) => w.status === 'busy').length;
    const offlineWorkers = workers.filter((w) => w.status === 'offline' || w.status === 'revoked').length;

    const totalJobs = jobs.length;
    const activeJobs = jobs.filter((j) => j.status === 'running' || j.status === 'scheduled').length;
    const completedJobs = jobs.filter((j) => j.status === 'completed').length;
    const failedJobs = jobs.filter((j) => j.status === 'failed').length;

    let totalCores = 0;
    let totalMemBytes = 0;
    let totalGpus = 0;
    let totalCpuPercent = 0;
    let totalMemPercent = 0;
    let telemetryCount = 0;

    for (const w of workers) {
      totalCores += w.cpu_cores_logical || 0;
      totalMemBytes += w.total_memory_bytes || 0;
      if (w.gpu_info) totalGpus += 1;
      if (w.telemetry) {
        totalCpuPercent += w.telemetry.cpu_percent || 0;
        totalMemPercent += w.telemetry.memory_percent || 0;
        telemetryCount += 1;
      }
    }

    return {
      total_workers: totalWorkers,
      online_workers: onlineWorkers,
      busy_workers: busyWorkers,
      offline_workers: offlineWorkers,
      total_jobs: totalJobs,
      active_jobs: activeJobs,
      completed_jobs: completedJobs,
      failed_jobs: failedJobs,
      total_cpu_cores: totalCores,
      total_memory_gb: Math.round(totalMemBytes / 1024 ** 3),
      total_gpus: totalGpus,
      avg_cpu_percent: telemetryCount > 0 ? Math.round(totalCpuPercent / telemetryCount) : 0,
      avg_memory_percent: telemetryCount > 0 ? Math.round(totalMemPercent / telemetryCount) : 0,
    };
  }, [workers, jobs]);

  // Check coordinator health and refresh data
  const refreshData = useCallback(async () => {
    setIsRefreshing(true);
    const health = await apiClient.testHealth();
    setLatencyMs(health.latencyMs);

    if (health.ok) {
      setConnectionStatus('connected');
      const [fetchedWorkers, fetchedJobs] = await Promise.all([
        apiClient.getWorkers(),
        apiClient.getJobs(),
      ]);
      setWorkers(fetchedWorkers);
      setJobs(fetchedJobs);
    } else {
      setConnectionStatus('error');
    }
    setIsRefreshing(false);
  }, [apiClient]);

  // Test Connection trigger
  const handleTestConnection = useCallback(async () => {
    setIsTesting(true);
    const res = await apiClient.testHealth();
    setTestResult(res);
    setLatencyMs(res.latencyMs);
    setConnectionStatus(res.ok ? 'connected' : 'error');
    setIsTesting(false);
    addLog(
      res.ok ? 'success' : 'error',
      'coordinator',
      res.ok
        ? `Ping success: ${res.status} (${res.latencyMs}ms)`
        : `Ping failed: ${res.error || res.status}`
    );
  }, [apiClient, addLog]);

  // Refresh binary status & daemon status
  const refreshDaemonStatus = useCallback(async () => {
    const bin = await getWorkerBinaryStatus();
    setBinaryInfo(bin);
    const status = await getLocalWorkerStatus();
    setDaemonStatus(status);
    const recentLogs = await getLocalWorkerLogs(200);
    setDaemonLogs(recentLogs);
  }, []);

  // Daemon Start
  const handleStartDaemon = async (params: { workerId: string; workerName: string }) => {
    setIsOperatingDaemon(true);
    try {
      const res = await startLocalWorker({
        coordinatorUrl: settings.coordinatorHttpUrl,
        workerId: params.workerId,
        workerName: params.workerName,
        authToken: settings.authToken,
      });
      setDaemonStatus(res);
      addLog('info', 'daemon', `Spawned local worker agent (PID: ${res.pid})`);
      await refreshDaemonStatus();
    } catch (err: any) {
      addLog('error', 'daemon', `Failed to launch local worker: ${err.message || err}`);
      alert(`Failed to start worker daemon: ${err.message || err}`);
    } finally {
      setIsOperatingDaemon(false);
    }
  };

  // Daemon Stop
  const handleStopDaemon = async () => {
    setIsOperatingDaemon(true);
    try {
      const res = await stopLocalWorker();
      setDaemonStatus(res);
      addLog('warn', 'daemon', 'Local worker agent process stopped');
      await refreshDaemonStatus();
    } catch (err: any) {
      addLog('error', 'daemon', `Failed to stop worker: ${err.message || err}`);
    } finally {
      setIsOperatingDaemon(false);
    }
  };

  const handleToggleDaemon = async () => {
    if (daemonStatus.running) {
      await handleStopDaemon();
    } else {
      await handleStartDaemon({
        workerId: settings.workerId,
        workerName: settings.workerName,
      });
    }
  };

  // Submit Job
  const handleSubmitJob = async (payload: {
    task_type: string;
    payload?: Record<string, any>;
    requirements?: Record<string, any>;
    priority?: number;
    timeout_seconds?: number;
  }) => {
    setIsSubmittingJob(true);
    try {
      const newJob = await apiClient.createJob(payload);
      addLog('success', 'scheduler', `Job submitted: ${newJob.id} (${newJob.task_type})`);
      await refreshData();
    } catch (err: any) {
      addLog('error', 'scheduler', `Failed to submit job: ${err.message || err}`);
      alert(`Job submission failed: ${err.message || err}`);
    } finally {
      setIsSubmittingJob(false);
    }
  };

  // Cancel Job
  const handleCancelJob = async (jobId: string) => {
    const ok = await apiClient.cancelJob(jobId);
    if (ok) {
      addLog('warn', 'scheduler', `Job cancelled: ${jobId}`);
      await refreshData();
    } else {
      alert(`Failed to cancel job ${jobId}`);
    }
  };

  // Revoke Worker
  const handleRevokeWorker = async (workerId: string) => {
    if (confirm(`Are you sure you want to revoke worker ${workerId}?`)) {
      const ok = await apiClient.revokeWorker(workerId);
      if (ok) {
        addLog('warn', 'coordinator', `Worker revoked: ${workerId}`);
        await refreshData();
      } else {
        alert(`Failed to revoke worker ${workerId}`);
      }
    }
  };

  // Save Settings
  const handleSaveSettings = (newSettings: DesktopSettings) => {
    setSettings(newSettings);
    localStorage.setItem('websync_desktop_settings', JSON.stringify(newSettings));
    addLog('info', 'desktop', 'Settings saved.');
    refreshData();
  };

  // Periodic polling interval
  useEffect(() => {
    refreshData();
    refreshDaemonStatus();

    const interval = setInterval(() => {
      refreshData();
      refreshDaemonStatus();
    }, settings.pollIntervalMs);

    return () => clearInterval(interval);
  }, [refreshData, refreshDaemonStatus, settings.pollIntervalMs]);

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 font-sans overflow-hidden">
      {/* Top Header */}
      <Header
        coordinatorUrl={settings.coordinatorHttpUrl}
        connectionStatus={connectionStatus}
        latencyMs={latencyMs}
        stats={clusterStats}
        isRefreshing={isRefreshing}
        onRefresh={refreshData}
        onTestConnection={handleTestConnection}
        isTesting={isTesting}
      />

      {/* Main Layout Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Navigation Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          workerCount={workers.length}
          jobCount={jobs.length}
          daemonStatus={daemonStatus}
          onToggleDaemon={handleToggleDaemon}
        />

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-slate-950">
          <div className="max-w-7xl mx-auto">
            {currentTab === 'overview' && (
              <OverviewTab
                stats={clusterStats}
                workers={workers}
                jobs={jobs}
                onSelectTab={setCurrentTab}
                onOpenNewJob={() => setIsOpenSubmitModal(true)}
                daemonStatus={daemonStatus}
                onToggleDaemon={handleToggleDaemon}
              />
            )}

            {currentTab === 'workers' && (
              <WorkersTab
                workers={workers}
                onRevokeWorker={handleRevokeWorker}
                onOpenLocalDaemon={() => setCurrentTab('daemon')}
              />
            )}

            {currentTab === 'jobs' && (
              <JobsTab
                jobs={jobs}
                workers={workers}
                onSubmitJob={handleSubmitJob}
                onCancelJob={handleCancelJob}
                isSubmitting={isSubmittingJob}
                isOpenSubmitModal={isOpenSubmitModal}
                setIsOpenSubmitModal={setIsOpenSubmitModal}
              />
            )}

            {currentTab === 'resources' && (
              <ResourceMonitorTab stats={clusterStats} workers={workers} />
            )}

            {currentTab === 'logs' && (
              <ActivityLogsTab logs={logs} onClearLogs={() => setLogs([])} />
            )}

            {currentTab === 'daemon' && (
              <LocalWorkerDaemonTab
                binaryInfo={binaryInfo}
                daemonStatus={daemonStatus}
                logs={daemonLogs}
                coordinatorUrl={settings.coordinatorHttpUrl}
                authToken={settings.authToken}
                onStartDaemon={handleStartDaemon}
                onStopDaemon={handleStopDaemon}
                onRefreshBinaryStatus={refreshDaemonStatus}
                onClearLogs={() => setDaemonLogs([])}
                isOperating={isOperatingDaemon}
              />
            )}

            {currentTab === 'settings' && (
              <SettingsTab
                settings={settings}
                onSaveSettings={handleSaveSettings}
                onTestConnection={handleTestConnection}
                isTesting={isTesting}
                testResult={testResult}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
