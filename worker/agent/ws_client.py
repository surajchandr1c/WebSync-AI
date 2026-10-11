"""Persistent authenticated WebSocket client for WebSync AI Worker Agent."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import random
from typing import Dict, Any, List, Optional, Callable
import uuid
import websockets
from websockets.exceptions import ConnectionClosed

from worker.agent.executor import ModularJobExecutor, WorkloadExecutionResult

logger = logging.getLogger("websync-worker.ws")


class WorkerWebSocketClient:
    """Manages persistent authenticated WebSocket connection, dispatch reception, and result streaming."""

    def __init__(
        self,
        coordinator_url: str,
        worker_id: str,
        worker_jwt: str,
        executor: ModularJobExecutor,
        supported_workloads: List[str],
        on_job_completed: Optional[Callable[[str, WorkloadExecutionResult], None]] = None,
    ):
        self.coordinator_url = coordinator_url.rstrip("/")
        self.worker_id = worker_id
        self.worker_jwt = worker_jwt
        self.executor = executor
        self.supported_workloads = supported_workloads
        self.on_job_completed = on_job_completed

        # WebSocket URL
        ws_base = self.coordinator_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{ws_base}/ws/worker?token={self.worker_jwt}"

        self._running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected_event = asyncio.Event()
        self._active_job_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._reconnect_attempts = 0

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._connected_event.is_set()

    def _create_envelope(
        self,
        msg_type: str,
        payload: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """Formulate a standard versioned JSON envelope."""
        envelope = {
            "type": msg_type,
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "worker_id": self.worker_id,
            "payload": payload or {},
        }
        return json.dumps(envelope)

    async def send_envelope(
        self,
        msg_type: str,
        payload: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Send a standardized JSON envelope over the WebSocket."""
        if not self._ws:
            return False
        try:
            raw = self._create_envelope(msg_type, payload, job_id, correlation_id)
            await self._ws.send(raw)
            return True
        except Exception as e:
            logger.debug("Failed to send WebSocket envelope '%s': %s", msg_type, str(e))
            return False

    async def run(self) -> None:
        """Run persistent connection loop with bounded exponential backoff with jitter."""
        self._running = True
        logger.info("WorkerWebSocketClient started for worker '%s'", self.worker_id)

        while self._running:
            try:
                logger.info("Connecting to coordinator WebSocket at %s...", self.coordinator_url)
                # websockets 12+ API compatible
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=15,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    self._connected_event.set()
                    self._reconnect_attempts = 0
                    logger.info("Authenticated WebSocket connection established with coordinator.")

                    # Run incoming message processing loop
                    await self._process_messages(ws)

            except (ConnectionClosed, ConnectionRefusedError, OSError) as e:
                logger.warning("WebSocket connection dropped (%s)", str(e))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unexpected WebSocket transport exception: %s", str(e), exc_info=True)
            finally:
                self._connected_event.clear()
                self._ws = None

            if not self._running:
                break

            # Calculate bounded exponential backoff with jitter
            self._reconnect_attempts += 1
            cap = min(30.0, 1.0 * (2 ** min(self._reconnect_attempts, 5)))
            jitter = random.uniform(0.1, 1.5)
            delay = round(cap + jitter, 2)
            logger.info("Reconnecting WebSocket in %.2fs (attempt #%d)...", delay, self._reconnect_attempts)

            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break

        logger.info("WorkerWebSocketClient event loop terminated.")

    async def _process_messages(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Read and route incoming WebSocket messages."""
        async for raw_msg in ws:
            if not self._running:
                break
            if raw_msg == "ping":
                await ws.send("pong")
                continue
            if raw_msg == "pong":
                continue

            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON message over WebSocket: %s", raw_msg[:80])
                continue

            msg_type = data.get("type")
            job_id = data.get("job_id")
            payload = data.get("payload", {})
            corr_id = data.get("correlation_id")

            # Route by message type
            if msg_type == "worker.conn_ack":
                logger.info(
                    "Received connection acknowledgement from coordinator (server_time: %s)",
                    payload.get("server_time") or data.get("timestamp"),
                )
            elif msg_type == "job.dispatch":
                # Handle job dispatch directly
                asyncio.create_task(self._handle_job_dispatch(data))
            elif msg_type == "job.cancel":
                # Handle remote cancellation
                asyncio.create_task(self._handle_job_cancel(job_id, payload))
            elif msg_type == "protocol.error":
                logger.warning("Coordinator returned protocol error: %s", payload.get("message") or data)
            else:
                logger.debug("Received unhandled WebSocket message type '%s'", msg_type)

    async def _handle_job_dispatch(self, data: Dict[str, Any]) -> None:
        """Validate, acknowledge, and execute a dispatched job over WebSocket."""
        payload = data.get("payload") or {}
        job_id = data.get("job_id") or payload.get("job_id")
        job_type = data.get("job_type") or payload.get("job_type")
        input_payload = data.get("input_payload") or payload.get("input_payload") or {}
        timeout_seconds = int(data.get("timeout_seconds") or payload.get("timeout_seconds") or 300)
        corr_id = data.get("correlation_id")

        if not job_id or not job_type:
            logger.warning("Malformed job.dispatch message: %s", data)
            return

        async with self._lock:
            if job_id in self._active_job_tasks:
                logger.debug("Job '%s' is already executing. Ignoring duplicate dispatch.", job_id)
                return

        # 1. Verify workload compatibility
        if job_type not in self.supported_workloads:
            rejection_reason = f"Workload '{job_type}' not supported on this node."
            logger.warning("Rejecting job '%s': %s", job_id, rejection_reason)
            await self.send_envelope(
                msg_type="job.ack",
                payload={"job_id": job_id, "accepted": False, "rejection_reason": rejection_reason},
                job_id=job_id,
                correlation_id=corr_id,
            )
            return

        # 2. Verify concurrency
        active_count = self.executor.get_active_jobs_count()
        if active_count >= self.executor.max_concurrent_jobs:
            rejection_reason = f"Concurrency capacity full ({active_count}/{self.executor.max_concurrent_jobs})."
            logger.warning("Rejecting job '%s': %s", job_id, rejection_reason)
            await self.send_envelope(
                msg_type="job.ack",
                payload={"job_id": job_id, "accepted": False, "rejection_reason": rejection_reason},
                job_id=job_id,
                correlation_id=corr_id,
            )
            return

        # 3. Acknowledge acceptance
        logger.info("Acknowledging acceptance of job '%s' (%s)", job_id, job_type)
        await self.send_envelope(
            msg_type="job.ack",
            payload={"job_id": job_id, "accepted": True},
            job_id=job_id,
            correlation_id=corr_id,
        )

        # 4. Report started
        await self.send_envelope(
            msg_type="job.started",
            payload={"job_id": job_id},
            job_id=job_id,
            correlation_id=corr_id,
        )

        # 5. Execute in tracked task
        task = asyncio.create_task(
            self._execute_and_stream_result(
                job_id=job_id,
                job_type=job_type,
                input_payload=input_payload,
                timeout_seconds=timeout_seconds,
                corr_id=corr_id,
            )
        )
        async with self._lock:
            self._active_job_tasks[job_id] = task

    async def _execute_and_stream_result(
        self,
        job_id: str,
        job_type: str,
        input_payload: Dict[str, Any],
        timeout_seconds: int,
        corr_id: Optional[str],
    ) -> None:
        try:
            logger.info("Executing job '%s' via ModularJobExecutor...", job_id)
            result = await self.executor.execute_job(
                job_id=job_id,
                job_type=job_type,
                input_payload=input_payload,
                timeout_seconds=timeout_seconds,
            )

            # Send final job.result
            logger.info(
                "Job '%s' finished (exit_code=%d, duration=%.4fs). Streaming result to coordinator...",
                job_id,
                result.exit_code,
                result.duration_seconds,
            )
            await self.send_envelope(
                msg_type="job.result",
                payload={
                    "job_id": job_id,
                    "exit_code": result.exit_code,
                    "output": result.output,
                    "duration_seconds": result.duration_seconds,
                    "error": result.error,
                },
                job_id=job_id,
                correlation_id=corr_id,
            )

            if self.on_job_completed:
                self.on_job_completed(job_id, result)

        except asyncio.CancelledError:
            logger.info("Job '%s' execution task cancelled.", job_id)
        except Exception as e:
            logger.error("Error executing job '%s': %s", job_id, str(e), exc_info=True)
            await self.send_envelope(
                msg_type="job.result",
                payload={
                    "job_id": job_id,
                    "exit_code": -1,
                    "output": "",
                    "duration_seconds": 0.0,
                    "error": str(e),
                },
                job_id=job_id,
                correlation_id=corr_id,
            )
        finally:
            async with self._lock:
                self._active_job_tasks.pop(job_id, None)

    async def _handle_job_cancel(self, job_id: Optional[str], payload: Dict[str, Any]) -> None:
        """Cancel an active in-flight execution upon coordinator request."""
        target_job_id = job_id or payload.get("job_id")
        if not target_job_id:
            return

        logger.info("Received cancellation request for job '%s'", target_job_id)
        cancelled = await self.executor.cancel_job(target_job_id)
        if cancelled:
            logger.info("Job '%s' execution task successfully cancelled.", target_job_id)
            await self.send_envelope(
                msg_type="job.cancelled",
                payload={"job_id": target_job_id, "success": True},
                job_id=target_job_id,
            )

    async def send_heartbeat(self, metrics_payload: Dict[str, Any]) -> bool:
        """Send real-time telemetry heartbeat over WebSocket."""
        return await self.send_envelope(
            msg_type="heartbeat",
            payload=metrics_payload,
        )

    async def close(self) -> None:
        """Close connection cleanly and cancel in-flight tasks."""
        self._running = False
        self._connected_event.clear()

        # Send graceful disconnection notice
        if self._ws:
            try:
                await self.send_envelope(
                    msg_type="worker.disconnected",
                    payload={"worker_id": self.worker_id, "reason": "Worker process shutdown"},
                )
                await self._ws.close()
            except Exception:
                pass
            finally:
                self._ws = None

        # Cancel any pending execution tasks
        async with self._lock:
            for job_id, task in list(self._active_job_tasks.items()):
                if not task.done():
                    task.cancel()
            self._active_job_tasks.clear()
