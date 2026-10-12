import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from worker.agent.metrics import sample_system_metrics
from worker.agent.transport import (
    CoordinatorTransport,
    TransportError,
    AuthenticationError,
    RegistrationError,
    calculate_backoff,
)

logger = logging.getLogger("websync-worker.heartbeat")


class HeartbeatLoop:
    """Schedules and dispatches periodic hardware telemetry heartbeats to the coordinator."""

    def __init__(
        self,
        transport: CoordinatorTransport,
        auth_token: str,
        interval_seconds: int = 10,
        active_jobs_provider: Optional[Callable[[], int]] = None,
    ):
        self.transport = transport
        self.auth_token = auth_token
        self.interval_seconds = interval_seconds
        self.active_jobs_provider = active_jobs_provider or (lambda: 0)
        self._running = False
        self._consecutive_failures = 0

    def build_heartbeat_payload(self) -> Dict[str, Any]:
        """Collect instantaneous measurements for WorkerHeartbeatRequest."""
        active_jobs = self.active_jobs_provider()
        metrics = sample_system_metrics(active_jobs_count=active_jobs)

        return {
            "cpu_utilization": metrics["cpu_utilization"],
            "cpu_count_logical": metrics.get("cpu_count_logical"),
            "cpu_count_physical": metrics.get("cpu_count_physical"),
            "available_ram_bytes": metrics["available_ram_bytes"],
            "total_ram_bytes": metrics["total_ram_bytes"],
            "used_ram_bytes": metrics.get("used_ram_bytes"),
            "websync_available_ram_bytes": metrics.get("websync_available_ram_bytes"),
            "disk_total_bytes": metrics.get("disk_total_bytes"),
            "disk_used_bytes": metrics.get("disk_used_bytes"),
            "disk_free_bytes": metrics.get("disk_free_bytes"),
            "disk_percent": metrics.get("disk_percent"),
            "configured_max_concurrent_jobs": metrics.get("configured_max_concurrent_jobs"),
            "configured_max_cpu_percent": metrics.get("configured_max_cpu_percent"),
            "configured_min_available_ram_mb": metrics.get("configured_min_available_ram_mb"),
            "active_job_count": active_jobs,
            "gpu_metadata": metrics["gpu_metadata"],
            "supported_models": metrics.get("supported_models", []),
            "ollama_status": metrics.get("ollama_status", "not_installed"),
            "last_model_check": metrics.get("last_model_check"),
        }

    async def send_single_heartbeat(self) -> Dict[str, Any]:
        """Sample metrics and deliver single heartbeat frame."""
        payload = self.build_heartbeat_payload()
        response = await self.transport.send_heartbeat(
            payload=payload, worker_jwt=self.auth_token
        )
        logger.debug(
            "Heartbeat dispatched: CPU %.1f%%, Avail RAM %.1f GB, Active Jobs: %d. Status: %s",
            payload["cpu_utilization"],
            payload["available_ram_bytes"] / (1024 ** 3),
            payload["active_job_count"],
            response.get("connection_status", "unknown"),
        )
        return response

    async def run(self) -> None:
        """Continuous heartbeat execution loop."""
        self._running = True
        logger.info("Heartbeat loop started. Reporting interval: %ds.", self.interval_seconds)

        while self._running:
            try:
                await self.send_single_heartbeat()
                self._consecutive_failures = 0
                await asyncio.sleep(self.interval_seconds)

            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancellation received.")
                self._running = False
                break

            except AuthenticationError as e:
                logger.error("Authentication expired or revoked during heartbeat: %s", str(e))
                self._running = False
                raise

            except RegistrationError as e:
                logger.error("Worker registration invalid on coordinator: %s", str(e))
                self._running = False
                raise

            except TransportError as e:
                self._consecutive_failures += 1
                delay = calculate_backoff(attempt=min(self._consecutive_failures, 5), base=2.0)
                logger.warning(
                    "Heartbeat failed (%s). Retrying in %.1fs (failures: %d)...",
                    str(e),
                    delay,
                    self._consecutive_failures,
                )
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    self._running = False
                    break

    def stop(self) -> None:
        """Stop heartbeat loop."""
        self._running = False
