import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Set, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("coordinator.ws")


class WebSocketManager:
    """Manages connected WebSocket clients and event broadcasting."""

    def __init__(self):
        self._active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._active_connections.add(websocket)
        logger.info("WebSocket client connected. Active clients: %d", len(self._active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket connection."""
        async with self._lock:
            self._active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Active clients: %d", len(self._active_connections))

    async def broadcast(self, event_name: str, data: Dict[str, Any]) -> None:
        """Broadcast structured event to all active dashboard clients."""
        payload = {
            "event": event_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
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
