import asyncio
import logging
from pathlib import Path
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
            "cpu_count_logical": specs.get("cpu_count_logical", 1),
            "cpu_count_physical": specs.get("cpu_count_physical", 1),
            "total_ram_bytes": specs["total_ram_bytes"],
            "available_ram_bytes": metrics["available_ram_bytes"],
            "used_ram_bytes": specs.get("used_ram_bytes", 0),
            "websync_available_ram_bytes": specs.get("websync_available_ram_bytes", metrics["available_ram_bytes"]),
            "disk_total_bytes": specs.get("disk_total_bytes", 0),
            "disk_used_bytes": specs.get("disk_used_bytes", 0),
            "disk_free_bytes": specs.get("disk_free_bytes", 0),
            "disk_percent": specs.get("disk_percent", 0.0),
            "supported_workloads": specs["supported_workloads"],
            "supported_models": specs.get("supported_models", []),
            "ollama_status": specs.get("ollama_status", "not_installed"),
            "last_model_check": specs.get("last_model_check"),
            "gpu_available": specs["gpu_available"],
            "gpu_metadata": specs["gpu_metadata"],
            "max_concurrent_jobs": self.settings.WEB_SYNC_MAX_CONCURRENT_JOBS,
        }

    def _get_token_path(self) -> Path:
        cache_dir = Path.home() / ".websync" / "tokens"
        cache_dir.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in self.settings.WEB_SYNC_WORKER_ID)
        return cache_dir / f"{safe_id}.token"

    def _read_cached_token(self) -> Optional[str]:
        p = self._get_token_path()
        if p.exists():
            try:
                token = p.read_text(encoding="utf-8").strip()
                if token:
                    return token
            except Exception:
                pass
        return None

    def _save_cached_token(self, token: str) -> None:
        try:
            p = self._get_token_path()
            p.write_text(token, encoding="utf-8")
        except Exception as e:
            logger.warning("Could not persist worker enrollment token: %s", e)

    async def register_with_retry(self, max_retries: int = 5) -> str:
        """Register worker with coordinator using bounded exponential backoff on transient errors."""
        # 1. Attempt session resumption if valid cached token exists
        cached_token = self._read_cached_token()
        if cached_token:
            try:
                metrics = sample_system_metrics()
                await self.transport.send_heartbeat(payload=metrics, worker_jwt=cached_token)
                self.assigned_token = cached_token
                logger.info(
                    "Resumed active enrollment session for worker '%s' using cached credentials.",
                    self.settings.WEB_SYNC_WORKER_ID,
                )
                return cached_token
            except Exception as e:
                logger.info("Cached enrollment token invalid or expired (%s). Re-enrolling with coordinator...", e)
                try:
                    self._get_token_path().unlink(missing_ok=True)
                except Exception:
                    pass

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
                self._save_cached_token(self.assigned_token)
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
