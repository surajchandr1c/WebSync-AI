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


from coordinator.ws.manager import worker_ws_manager
from coordinator.db.session import async_session_factory
from coordinator.services.dispatcher_service import DispatcherService
from coordinator.scheduler.engine import scheduler_engine
from coordinator.models.job import Job
from coordinator.schemas.job import JobState, JobDispatchEnvelope
from sqlalchemy import select
import json


@router.websocket("/worker")
async def websocket_worker(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Bidirectional dispatch channel for authenticated WebSync worker agents."""
    if not token:
        await websocket.close(code=1008, reason="Missing worker auth token")
        return

    try:
        payload = decode_token(token)
        worker_id = payload.get("sub")
        if not worker_id:
            await websocket.close(code=1008, reason="Invalid token subject")
            return
    except Exception:
        await websocket.close(code=1008, reason="Invalid worker authentication token")
        return

    await websocket.accept()
    await worker_ws_manager.register_worker(worker_id, websocket)

    # Immediately check for scheduled jobs assigned to this worker
    try:
        async with async_session_factory() as db:
            stmt = select(Job).where(
                Job.assigned_worker_id == worker_id,
                Job.status == JobState.SCHEDULED.value,
            )
            pending = (await db.execute(stmt)).scalars().all()
            for j in pending:
                timeout_sec = 300
                if j.requirements and "timeout_seconds" in j.requirements:
                    timeout_sec = int(j.requirements["timeout_seconds"])
                envelope = {
                    "type": "job.dispatch",
                    "job_id": j.job_id,
                    "job_type": j.job_type,
                    "input_payload": j.input_payload,
                    "timeout_seconds": timeout_sec,
                    "correlation_id": f"conn-{j.job_id}",
                }
                await websocket.send_text(json.dumps(envelope))
    except Exception as e:
        logger.error("Error dispatching pending jobs to worker '%s': %s", worker_id, str(e))

    try:
        while True:
            raw_msg = await websocket.receive_text()
            if raw_msg == "ping":
                await websocket.send_text("pong")
                continue

            try:
                data = json.loads(raw_msg)
            except Exception:
                continue

            msg_type = data.get("type")
            job_id = data.get("job_id")

            async with async_session_factory() as db:
                if msg_type == "job.ack":
                    await DispatcherService.process_job_ack(
                        db=db,
                        worker_id=worker_id,
                        job_id=job_id,
                        accepted=data.get("accepted", False),
                        rejection_reason=data.get("rejection_reason"),
                    )
                elif msg_type == "job.started":
                    await DispatcherService.process_job_started(
                        db=db,
                        worker_id=worker_id,
                        job_id=job_id,
                    )
                elif msg_type == "job.progress":
                    await ws_manager.broadcast("job.progress", data)
                elif msg_type == "job.result":
                    await DispatcherService.process_job_result(
                        db=db,
                        worker_id=worker_id,
                        job_id=job_id,
                        exit_code=int(data.get("exit_code", 0)),
                        output=str(data.get("output", "")),
                        duration_seconds=float(data.get("duration_seconds", 0.0)),
                        error=data.get("error"),
                    )
                    # When a job completes, check if other queued jobs can now be scheduled
                    await DispatcherService.dispatch_pending_queued_jobs(db)

    except WebSocketDisconnect:
        logger.info("Worker '%s' disconnected from WebSocket", worker_id)
        await worker_ws_manager.unregister_worker(worker_id)
        async with async_session_factory() as db:
            await scheduler_engine.handle_worker_disconnect_cleanup(db, worker_id)
    except Exception as e:
        logger.error("Worker WebSocket exception for '%s': %s", worker_id, str(e))
        await worker_ws_manager.unregister_worker(worker_id)
        async with async_session_factory() as db:
            await scheduler_engine.handle_worker_disconnect_cleanup(db, worker_id)
