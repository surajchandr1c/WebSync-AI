import { LocalWorkerStatus, WorkerBinaryInfo } from '../types';

let invokeFn: ((cmd: string, args?: Record<string, any>) => Promise<any>) | null = null;

async function getInvoke() {
  if (invokeFn) return invokeFn;
  try {
    const tauri = await import('@tauri-apps/api/core');
    invokeFn = tauri.invoke;
    return invokeFn;
  } catch {
    return null;
  }
}

export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window);
}

export async function getWorkerBinaryStatus(): Promise<WorkerBinaryInfo> {
  const inv = await getInvoke();
  if (inv && isTauriEnvironment()) {
    try {
      return await inv('get_worker_binary_status');
    } catch (err) {
      console.warn('Tauri get_worker_binary_status failed:', err);
    }
  }

  return {
    found: true,
    path: 'worker/dist/websync-worker.exe',
    version: '0.3.0',
  };
}

export async function getLocalWorkerStatus(): Promise<LocalWorkerStatus> {
  const inv = await getInvoke();
  if (inv && isTauriEnvironment()) {
    try {
      return await inv('get_local_worker_status');
    } catch (err) {
      console.warn('Tauri get_local_worker_status failed:', err);
    }
  }

  return {
    running: false,
    pid: null,
    coordinator_url: null,
    worker_id: null,
    exit_code: null,
    binary_path: null,
  };
}

export async function startLocalWorker(params: {
  coordinatorUrl: string;
  workerId?: string;
  workerName?: string;
  authToken?: string;
}): Promise<LocalWorkerStatus> {
  const inv = await getInvoke();
  if (inv && isTauriEnvironment()) {
    return await inv('start_local_worker', {
      coordinatorUrl: params.coordinatorUrl,
      workerId: params.workerId || null,
      workerName: params.workerName || null,
      authToken: params.authToken || null,
    });
  }

  // Simulated fallback for browser preview mode
  return {
    running: true,
    pid: 8492,
    coordinator_url: params.coordinatorUrl,
    worker_id: params.workerId || 'worker-local-simulated',
    exit_code: null,
    binary_path: 'worker/dist/websync-worker.exe',
  };
}

export async function stopLocalWorker(): Promise<LocalWorkerStatus> {
  const inv = await getInvoke();
  if (inv && isTauriEnvironment()) {
    return await inv('stop_local_worker');
  }

  return {
    running: false,
    pid: null,
    coordinator_url: null,
    worker_id: null,
    exit_code: 0,
    binary_path: null,
  };
}

export async function getLocalWorkerLogs(limit: number = 200): Promise<string[]> {
  const inv = await getInvoke();
  if (inv && isTauriEnvironment()) {
    try {
      return await inv('get_local_worker_logs', { limit });
    } catch (err) {
      console.warn('Tauri get_local_worker_logs failed:', err);
    }
  }

  return [
    `[${new Date().toLocaleTimeString()}] [System] Local worker log monitor initialized.`,
    `[${new Date().toLocaleTimeString()}] [Daemon] Ready to dispatch worker commands.`,
  ];
}
