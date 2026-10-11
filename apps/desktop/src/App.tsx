export default function App() {
  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <header style={{ borderBottom: '1px solid #1f2937', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#60a5fa' }}>WebSync AI Desktop</h1>
        <p style={{ fontSize: '0.875rem', color: '#9ca3af' }}>Native Node Shell & Telemetry Monitor</p>
      </header>

      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '0.5rem', padding: '1rem' }}>
        <h2 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>Phase 1 Desktop Scaffold</h2>
        <p style={{ fontSize: '0.875rem', color: '#9ca3af', lineHeight: '1.5' }}>
          This desktop shell runs as a Tauri 2 wrapper for Windows, macOS, and Linux. In Phase 6, it will package
          the background worker agent daemon and system tray monitoring.
        </p>
      </div>
    </div>
  );
}
