import asyncio
import logging
from typing import Dict, Any, Optional
from worker.agent.config import WorkerSettings
from worker.agent.metrics import get_static_hardware_specs, sample_system_metrics
from worker.agent.transport import (
    CoordinatorTransport,
    TransportError,
    AuthenticationError,
    RegistrationError,
    calculate_backoff,
)

logger = logging.getLogger("websync-worker.registration")


class RegistrationManager:
    """Manages worker enrollment with the WebSync AI Coordinator."""

    def __init__(self, settings: WorkerSettings, transport: CoordinatorTransport):
        self.settings = settings
        self.transport = transport
        self.assigned_token: Optional[str] = None
        self.heartbeat_interval: int = settings.WEB_SYNC_HEARTBEAT_INTERVAL

    def build_registration_payload(self) -> Dict[str, Any]:
        """Construct registration payload matching coordinator's WorkerRegistrationRequest schema."""
        specs = get_static_hardware_specs()
        metrics = sample_system_metrics()

        return {
            "worker_id": self.settings.WEB_SYNC_WORKER_ID,
            "display_name": self.settings.WEB_SYNC_WORKER_NAME,
            "hostname": specs["hostname"],
            "platform": specs["platform"],
            "platform_version": specs["platform_version"],
            "cpu_utilization": metrics["cpu_utilization"],
            "total_ram_bytes": specs["total_ram_bytes"],
            "available_ram_bytes": metrics["available_ram_bytes"],
            "supported_workloads": specs["supported_workloads"],
            "gpu_available": specs["gpu_available"],
            "gpu_metadata": specs["gpu_metadata"],
        }

    async def register_with_retry(self, max_retries: int = 5) -> str:
        """Register worker with coordinator using bounded exponential backoff on transient errors."""
        payload = self.build_registration_payload()

        logger.info(
            "Registering worker '%s' (%s %s, %d CPU cores, %.1f GB RAM, GPU: %s)...",
            payload["worker_id"],
            payload["platform"],
            payload["platform_version"],
            get_static_hardware_specs()["cpu_count_logical"],
            payload["total_ram_bytes"] / (1024 ** 3),
            "Available" if payload["gpu_available"] else "None",
        )

        for attempt in range(max_retries):
            try:
                response = await self.transport.register(
                    payload=payload,
                    pre_shared_token=self.settings.WEB_SYNC_WORKER_TOKEN,
                )
                self.assigned_token = response["auth_token"]
                self.heartbeat_interval = response.get(
                    "heartbeat_interval_seconds", self.settings.WEB_SYNC_HEARTBEAT_INTERVAL
                )
                worker_id = response.get("worker_id", self.settings.WEB_SYNC_WORKER_ID)
                status = response.get("connection_status", "online")
                logger.info(
                    "Successfully enrolled worker '%s'. Status: %s. Heartbeat interval: %ds.",
                    worker_id,
                    status,
                    self.heartbeat_interval,
                )
                return self.assigned_token

            except AuthenticationError as e:
                # Fatal: Bad credentials cannot be solved by retrying
                logger.error("Authentication failed during worker registration: %s", str(e))
                raise

            except RegistrationError as e:
                # Fatal: Validation error or ID conflict
                logger.error("Registration rejected by coordinator: %s", str(e))
                raise

            except TransportError as e:
                if attempt == max_retries - 1:
                    logger.error("Registration failed after %d attempts: %s", max_retries, str(e))
                    raise

                delay = calculate_backoff(
                    attempt=attempt,
                    base=1.5,
                    max_cap=self.settings.WEB_SYNC_MAX_RETRY_BACKOFF_SECONDS,
                )
                logger.warning(
                    "Coordinator unreachable (%s). Retrying registration in %.1f seconds (attempt %d/%d)...",
                    str(e),
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Registration failed unexpectedly.")
