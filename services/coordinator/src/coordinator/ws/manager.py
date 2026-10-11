import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Set, Dict, Any, Optional
import uuid
from fastapi import WebSocket

logger = logging.getLogger("coordinator.ws")


class WebSocketManager:
    """Manages connected dashboard WebSocket clients and structured event broadcasting."""

    def __init__(self):
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info("Dashboard WebSocket client connected. Active clients: %d", len(self._active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket connection."""
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info("Dashboard WebSocket client disconnected. Active clients: %d", len(self._active_connections))

    async def broadcast(
        self,
        event_name: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None,
        job_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Broadcast standardized versioned event envelope to all active dashboard clients."""
        now_iso = datetime.now(timezone.utc).isoformat()
        msg_id = message_id or str(uuid.uuid4())
        payload = {
            "type": event_name,
            "event": event_name,
            "message_id": msg_id,
            "timestamp": now_iso,
            "correlation_id": correlation_id,
            "job_id": job_id or data.get("job_id"),
            "worker_id": worker_id or data.get("worker_id"),
            "data": data,
            "payload": data,
        }
        text_data = json.dumps(payload)

        async with self._lock:
            current_connections = list(self._active_connections)

        if not current_connections:
            return

        dead_connections: Set[WebSocket] = set()
        for connection in current_connections:
            try:
                await connection.send_text(text_data)
            except Exception as e:
                logger.debug("Failed to deliver message to WebSocket client: %s", str(e))
                dead_connections.add(connection)

        if dead_connections:
            async with self._lock:
                for dead in dead_connections:
                    self._active_connections.discard(dead)


# Global singleton manager for in-memory single-coordinator setup
ws_manager = WebSocketManager()


class WorkerConnectionManager:
    """Manages authenticated live WebSocket connections to worker agents for real-time dispatch."""

    def __init__(self):
        self._worker_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def register_worker(self, worker_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._worker_connections[worker_id] = websocket
        logger.info("Worker '%s' connected via WebSocket. Active workers: %d", worker_id, len(self._worker_connections))

    async def unregister_worker(self, worker_id: str) -> None:
        async with self._lock:
            self._worker_connections.pop(worker_id, None)
        logger.info("Worker '%s' disconnected from WebSocket. Active workers: %d", worker_id, len(self._worker_connections))

    def is_worker_connected(self, worker_id: str) -> bool:
        return worker_id in self._worker_connections

    async def dispatch_job_to_worker(self, worker_id: str, message: Dict[str, Any]) -> bool:
        async with self._lock:
            ws = self._worker_connections.get(worker_id)
        if not ws:
            return False
        try:
            await ws.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.error("Failed to dispatch job to worker '%s': %s", worker_id, str(e))
            await self.unregister_worker(worker_id)
            return False

    async def cancel_job_on_worker(
        self, worker_id: str, job_id: str, reason: Optional[str] = None
    ) -> bool:
        """Send job.cancel envelope to assigned worker node."""
        envelope = {
            "type": "job.cancel",
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "worker_id": worker_id,
            "payload": {"job_id": job_id, "reason": reason or "Cancelled by operator"},
        }
        return await self.dispatch_job_to_worker(worker_id, envelope)


# Global singleton worker WebSocket manager
worker_ws_manager = WorkerConnectionManager()
