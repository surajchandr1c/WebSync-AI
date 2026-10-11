import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import jwt
from coordinator.ws.manager import ws_manager
from coordinator.core.security import decode_token

logger = logging.getLogger("coordinator.ws.routes")
router = APIRouter(prefix="/ws", tags=["WebSockets"])


@router.websocket("/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Real-time event feed for the WebSync AI dashboard."""
    # Optional token verification
    if token:
        try:
            decode_token(token)
        except jwt.PyJWTError:
            await websocket.close(code=1008, reason="Invalid token")
            return

    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive heartbeat listener
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug("WebSocket connection error: %s", str(e))
        await ws_manager.disconnect(websocket)
