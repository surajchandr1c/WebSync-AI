import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path for direct script execution
_root_dir = Path(__file__).resolve().parent.parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))
_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

from worker.agent.config import settings, WorkerSettings
from worker.agent.logging_config import configure_logging
from worker.agent.metrics import get_static_hardware_specs, sample_system_metrics
from worker.agent.transport import CoordinatorTransport
from worker.agent.registration import RegistrationManager
from worker.agent.heartbeat import HeartbeatLoop
from worker.agent.executor import ModularJobExecutor

logger = configure_logging(settings.WEB_SYNC_LOG_LEVEL)


def inspect_node() -> None:
    """Print complete genuine system telemetry, capabilities, and GPU hardware."""
    specs = get_static_hardware_specs()
    metrics = sample_system_metrics()

    print("\n" + "=" * 56)
    print("      WebSync AI Worker Agent - Node Telemetry")
    print("=" * 56)
    print(f"Worker ID:         {settings.WEB_SYNC_WORKER_ID}")
    print(f"Display Name:      {settings.WEB_SYNC_WORKER_NAME}")
    print(f"Platform:          {specs['platform']} {specs['platform_version']} ({specs['architecture']})")
    print(f"Hostname:          {specs['hostname']}")
    print(f"CPU Cores:         {specs['cpu_count_physical']} physical / {specs['cpu_count_logical']} logical")
    print(f"Instantaneous CPU: {metrics['cpu_utilization']:.1f}%")
    print(f"Total RAM:         {specs['total_ram_bytes'] / (1024**3):.2f} GB ({specs['total_ram_bytes']} bytes)")
    print(f"Available RAM:     {metrics['available_ram_bytes'] / (1024**3):.2f} GB ({metrics['available_ram_bytes']} bytes)")
    print(f"RAM Utilization:   {metrics['ram_percent']:.1f}%")
    print(f"Disk Free:         {metrics['disk_free_bytes'] / (1024**3):.2f} GB")
    print(f"System Uptime:     {specs['system_uptime_seconds']}s" if specs['system_uptime_seconds'] else "System Uptime:     N/A")
    print(f"Agent Version:     {specs['agent_version']}")
    print(f"Supported Tasks:   {', '.join(specs['supported_workloads'])}")

    if specs["gpu_available"]:
        print(f"GPU Hardware:      Available ({len(specs['gpu_metadata'])} device(s))")
        for i, dev in enumerate(specs["gpu_metadata"]):
            vram_gb = dev['memory_total_bytes'] / (1024**3)
            print(f"  [{i}] {dev['name']} - {vram_gb:.2f} GB VRAM")
    else:
        print("GPU Hardware:      Not detected or driver unavailable")
    print("=" * 56 + "\n")


class WorkerDaemon:
    """Core worker background agent daemon."""

    def __init__(self, cfg: WorkerSettings):
        self.cfg = cfg
        self.executor = ModularJobExecutor(max_concurrent_jobs=cfg.WEB_SYNC_MAX_CONCURRENT_JOBS)
        self._stop_event = asyncio.Event()

    async def run(self, single_heartbeat_only: bool = False) -> None:
        """Run registration and periodic heartbeat loop."""
        logger.info("Initializing WebSync AI Worker Agent (ID: %s)", self.cfg.WEB_SYNC_WORKER_ID)
        logger.info("Target Coordinator URL: %s", self.cfg.WEB_SYNC_COORDINATOR_URL)

        async with CoordinatorTransport(
            base_url=self.cfg.WEB_SYNC_COORDINATOR_URL,
            timeout_seconds=self.cfg.WEB_SYNC_CONNECT_TIMEOUT_SECONDS,
            verify_tls=self.cfg.WORKER_VERIFY_TLS,
        ) as transport:
            # 1. Register with coordinator
            reg_manager = RegistrationManager(settings=self.cfg, transport=transport)
            auth_token = await reg_manager.register_with_retry()

            # 2. Setup heartbeat loop
            heartbeat = HeartbeatLoop(
                transport=transport,
                auth_token=auth_token,
                interval_seconds=reg_manager.heartbeat_interval,
                active_jobs_provider=self.executor.get_active_jobs_count,
            )

            # 3. Setup job dispatcher (HTTP fallback)
            from worker.agent.capabilities import get_supported_workloads
            from worker.agent.dispatcher import WorkerDispatcher
            from worker.agent.ws_client import WorkerWebSocketClient

            supported_workloads = get_supported_workloads()

            dispatcher = WorkerDispatcher(
                transport=transport,
                executor=self.executor,
                worker_id=self.cfg.WEB_SYNC_WORKER_ID,
                worker_jwt=auth_token,
                supported_workloads=supported_workloads,
                poll_interval_seconds=3.0,
            )

            # 4. Setup real-time WebSocket client
            ws_client = WorkerWebSocketClient(
                coordinator_url=self.cfg.WEB_SYNC_COORDINATOR_URL,
                worker_id=self.cfg.WEB_SYNC_WORKER_ID,
                worker_jwt=auth_token,
                executor=self.executor,
                supported_workloads=supported_workloads,
            )

            if single_heartbeat_only:
                logger.info("Single heartbeat verification mode requested. Dispatching heartbeat...")
                await heartbeat.send_single_heartbeat()
                logger.info("Single heartbeat completed successfully.")
                await transport.disconnect(
                    worker_id=self.cfg.WEB_SYNC_WORKER_ID, worker_jwt=auth_token
                )
                return

            heartbeat_task = asyncio.create_task(heartbeat.run())
            dispatcher_task = asyncio.create_task(dispatcher.run())
            ws_task = asyncio.create_task(ws_client.run())

            try:
                # Wait until stop requested
                await self._stop_event.wait()
            finally:
                logger.info("Shutdown signal received. Stopping worker services...")
                await ws_client.close()
                dispatcher.stop()
                heartbeat.stop()
                ws_task.cancel()
                dispatcher_task.cancel()
                heartbeat_task.cancel()
                try:
                    await asyncio.gather(heartbeat_task, dispatcher_task, ws_task, return_exceptions=True)
                except Exception:
                    pass

                # Clean disconnection notice
                await transport.disconnect(
                    worker_id=self.cfg.WEB_SYNC_WORKER_ID, worker_jwt=auth_token
                )
                logger.info("Worker agent shut down cleanly.")

    def stop(self) -> None:
        self._stop_event.set()


def main():
    parser = argparse.ArgumentParser(description="WebSync AI Distributed Worker Agent")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect real host hardware telemetry and exit.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run single registration and single heartbeat then exit cleanly (smoke test).",
    )
    parser.add_argument(
        "--coordinator-url",
        "--coordinator",
        type=str,
        default=None,
        dest="coordinator_url",
        help="Override coordinator base URL (e.g. https://coordinator.example.com or http://localhost:8000)",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        dest="worker_id",
        help="Override unique worker node identifier",
    )
    parser.add_argument(
        "--worker-name",
        "--display-name",
        type=str,
        default=None,
        dest="worker_name",
        help="Override worker node display name",
    )
    args = parser.parse_args()

    if args.inspect:
        inspect_node()
        sys.exit(0)

    # Dynamic CLI overrides
    if args.coordinator_url:
        settings.WEB_SYNC_COORDINATOR_URL = args.coordinator_url
    if args.worker_id:
        settings.WEB_SYNC_WORKER_ID = args.worker_id
    if args.worker_name:
        settings.WEB_SYNC_WORKER_NAME = args.worker_name

    daemon = WorkerDaemon(settings)

    # Graceful signal handling
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _handle_exit(sig, frame):
        logger.info("Interrupt signal received (%s). Initiating graceful exit...", sig)
        daemon.stop()

    signal.signal(signal.SIGINT, _handle_exit)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_exit)

    try:
        loop.run_until_complete(daemon.run(single_heartbeat_only=args.once))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
