import React, { useState } from 'react';
import { DesktopSettings } from '../../types';
import { validateCoordinatorUrl } from '../../services/api';
import {
  Settings2,
  ShieldCheck,
  ShieldAlert,
  Save,
  CheckCircle2,
  Lock,
  Eye,
  EyeOff,
  Zap,
} from 'lucide-react';

interface SettingsTabProps {
  settings: DesktopSettings;
  onSaveSettings: (settings: DesktopSettings) => void;
  onTestConnection: () => Promise<void>;
  isTesting: boolean;
  testResult: { ok: boolean; status: string; latencyMs: number; error?: string } | null;
}

export const SettingsTab: React.FC<SettingsTabProps> = ({
  settings,
  onSaveSettings,
  onTestConnection,
  isTesting,
  testResult,
}) => {
  const [form, setForm] = useState<DesktopSettings>({ ...settings });
  const [showToken, setShowToken] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const httpValidation = validateCoordinatorUrl(form.coordinatorHttpUrl);
  const wsValidation = validateCoordinatorUrl(form.coordinatorWsUrl);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!httpValidation.isValid || !wsValidation.isValid) {
      alert('Please correct URL security policy errors before saving.');
      return;
    }
    onSaveSettings(form);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight">Application Settings</h2>
        <p className="text-xs text-slate-400 mt-1">
          Configure connection endpoints, security credentials, and synchronization behavior.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Connection Endpoints */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
            <Settings2 className="w-4 h-4 text-cyan-400" />
            <span>Coordinator Endpoints</span>
          </h3>

          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Coordinator HTTP API URL
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={form.coordinatorHttpUrl}
                  onChange={(e) => setForm({ ...form, coordinatorHttpUrl: e.target.value })}
                  placeholder="http://localhost:8000 or https://coordinator.domain.com"
                  className={`w-full px-3 py-2 bg-slate-950 border rounded-lg font-mono text-slate-200 focus:outline-none ${
                    httpValidation.isValid
                      ? 'border-slate-800 focus:border-cyan-500'
                      : 'border-rose-600 focus:border-rose-500'
                  }`}
                  required
                />
              </div>

              {!httpValidation.isValid && (
                <div className="mt-1.5 text-[11px] text-rose-400 flex items-center space-x-1">
                  <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                  <span>{httpValidation.errorMessage}</span>
                </div>
              )}

              {httpValidation.isValid && (
                <div className="mt-1.5 text-[11px] text-slate-400 flex items-center space-x-1">
                  {httpValidation.isSecure ? (
                    <span className="text-emerald-400 flex items-center space-x-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>Encrypted TLS connection (HTTPS)</span>
                    </span>
                  ) : (
                    <span className="text-amber-400">
                      Local development URL (HTTP permitted for localhost only)
                    </span>
                  )}
                </div>
              )}
            </div>

            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Coordinator WebSocket (WS) URL
              </label>
              <input
                type="text"
                value={form.coordinatorWsUrl}
                onChange={(e) => setForm({ ...form, coordinatorWsUrl: e.target.value })}
                placeholder="ws://localhost:8000/ws or wss://coordinator.domain.com/ws"
                className={`w-full px-3 py-2 bg-slate-950 border rounded-lg font-mono text-slate-200 focus:outline-none ${
                  wsValidation.isValid
                    ? 'border-slate-800 focus:border-cyan-500'
                    : 'border-rose-600 focus:border-rose-500'
                }`}
                required
              />

              {!wsValidation.isValid && (
                <div className="mt-1.5 text-[11px] text-rose-400 flex items-center space-x-1">
                  <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                  <span>{wsValidation.errorMessage}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Security & Authentication */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
            <Lock className="w-4 h-4 text-emerald-400" />
            <span>Authentication Credentials</span>
          </h3>

          <div className="text-xs space-y-3">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Worker Enrollment / Coordinator API Bearer Token
              </label>
              <div className="relative">
                <input
                  type={showToken ? 'text' : 'password'}
                  value={form.authToken}
                  onChange={(e) => setForm({ ...form, authToken: e.target.value })}
                  placeholder="Optional coordinator secret or worker authentication token"
                  className="w-full pl-3 pr-10 py-2 bg-slate-950 border border-slate-800 rounded-lg font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                />
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200"
                >
                  {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Provided to coordinator in Authorization header and passed to local worker processes.
              </p>
            </div>
          </div>
        </div>

        {/* Connection Diagnostics Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                <Zap className="w-4 h-4 text-cyan-400" />
                <span>Connection Health Diagnostics</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Probe the coordinator health endpoint to test latency and reachability.
              </p>
            </div>

            <button
              type="button"
              onClick={onTestConnection}
              disabled={isTesting || !httpValidation.isValid}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center space-x-1.5 transition disabled:opacity-50"
            >
              <span>{isTesting ? 'Pinging...' : 'Test Connection'}</span>
            </button>
          </div>

          {testResult && (
            <div
              className={`p-3 rounded-lg border text-xs font-mono flex items-start space-x-2.5 ${
                testResult.ok
                  ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
                  : 'bg-rose-950/60 border-rose-800 text-rose-300'
              }`}
            >
              {testResult.ok ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              )}
              <div>
                <div className="font-bold">
                  {testResult.ok ? `Coordinator Reachable (${testResult.latencyMs}ms)` : 'Connection Test Failed'}
                </div>
                <div className="text-[11px] opacity-90 mt-0.5">
                  Status: {testResult.status} {testResult.error && `— ${testResult.error}`}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Save Bar */}
        <div className="flex items-center justify-between pt-2">
          {savedSuccess && (
            <div className="text-xs text-emerald-400 flex items-center space-x-1.5 font-medium">
              <CheckCircle2 className="w-4 h-4" />
              <span>Settings saved successfully!</span>
            </div>
          )}
          {!savedSuccess && <div />}

          <button
            type="submit"
            className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-cyan-600/20 flex items-center space-x-2 transition"
          >
            <Save className="w-4 h-4" />
            <span>Save Configuration</span>
          </button>
        </div>
      </form>
    </div>
  );
};
