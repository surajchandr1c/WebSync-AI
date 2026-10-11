import asyncio
import anyio
from datetime import datetime, timezone
import json
import logging
from typing import Optional
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import jwt
from sqlalchemy import select

from coordinator.config import settings
from coordinator.ws.manager import ws_manager, worker_ws_manager
from coordinator.core.security import decode_token
from coordinator.db.session import async_session_factory
from coordinator.services.dispatcher_service import DispatcherService
from coordinator.scheduler.engine import scheduler_engine
from coordinator.models.worker import Worker
from coordinator.models.job import Job
from coordinator.models.job_event import JobEvent
from coordinator.schemas.job import JobState
from coordinator.schemas.protocol import (
    ProtocolMessageType,
    BaseMessageEnvelope,
)

logger = logging.getLogger("coordinator.ws.routes")
router = APIRouter(prefix="/ws", tags=["WebSockets"])


@router.websocket("/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Real-time event feed for the WebSync AI dashboard."""
    # Optional token verification for authorized dashboard clients
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") != "user":
                await websocket.close(code=1008, reason="Dashboard requires user token")
                return
        except jwt.PyJWTError:
            await websocket.close(code=1008, reason="Invalid token")
            return

    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive heartbeat listener
            msg = await websocket.receive_text()
            if len(msg) > settings.MAX_WS_MESSAGE_SIZE_BYTES:
                continue
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug("Dashboard WebSocket connection error: %s", str(e))
        await ws_manager.disconnect(websocket)


@router.websocket("/worker")
async def websocket_worker(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Bidirectional dispatch and telemetry channel for authenticated WebSync worker agents."""
    if not token:
        await websocket.close(code=1008, reason="Missing worker auth token")
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "worker":
            await websocket.close(code=1008, reason="Invalid token type for worker channel")
            return
        worker_id = payload.get("sub")
        if not worker_id:
            await websocket.close(code=1008, reason="Invalid token subject")
            return
    except Exception:
        await websocket.close(code=1008, reason="Invalid worker authentication token")
        return

    # Check worker existence and revocation before accepting connection
    try:
        async with async_session_factory() as db:
            stmt = select(Worker).where(Worker.worker_id == worker_id)
            worker = (await db.execute(stmt)).scalar_one_or_none()
            if not worker:
                await websocket.close(code=1008, reason="Worker not registered")
                return
            if worker.is_revoked:
                await websocket.close(code=1008, reason="Worker credentials revoked")
                return
    except Exception as e:
        logger.error("DB error validating worker '%s': %s", worker_id, str(e))
        await websocket.close(code=1011, reason="Database error")
        return

    await websocket.accept()
    await worker_ws_manager.register_worker(worker_id, websocket)

    now = datetime.now(timezone.utc)

    # 1. Update worker record in database to online
    try:
        async with async_session_factory() as db:
            stmt = select(Worker).where(Worker.worker_id == worker_id)
            worker = (await db.execute(stmt)).scalar_one_or_none()
            if worker:
                worker.connection_status = "busy" if worker.active_job_count > 0 else "online"
                worker.last_heartbeat = now
                await db.commit()
                await db.refresh(worker)

                # Broadcast worker online event to dashboard
                await ws_manager.broadcast(
                    ProtocolMessageType.WORKER_CONNECTED.value,
                    {
                        "worker_id": worker.worker_id,
                        "display_name": worker.display_name,
                        "platform": worker.platform,
                        "status": worker.connection_status,
                    },
                )
    except Exception as e:
        logger.error("Error updating worker '%s' on connection: %s", worker_id, str(e))

    # 2. Send connection acknowledgement handshake envelope
    conn_ack_env = BaseMessageEnvelope.create(
        msg_type=ProtocolMessageType.WORKER_CONN_ACK.value,
        worker_id=worker_id,
        payload={
            "worker_id": worker_id,
            "heartbeat_interval_seconds": 10,
            "coordinator_version": "0.3.0",
            "server_time": now.isoformat(),
        },
    )
    await websocket.send_text(conn_ack_env.to_json())

    # 3. Immediately check for pending scheduled jobs assigned to this worker
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
                dispatch_env = BaseMessageEnvelope.create(
                    msg_type=ProtocolMessageType.JOB_DISPATCH.value,
                    job_id=j.job_id,
                    worker_id=worker_id,
                    correlation_id=f"conn-{j.job_id}",
                    payload={
                        "job_id": j.job_id,
                        "job_type": j.job_type,
                        "input_payload": j.input_payload,
                        "timeout_seconds": timeout_sec,
                    },
                )
                await websocket.send_text(dispatch_env.to_json())
    except Exception as e:
        logger.error("Error dispatching pending jobs to worker '%s': %s", worker_id, str(e))

    # 4. Inbound message loop
    try:
        while True:
            raw_msg = await websocket.receive_text()
            if len(raw_msg) > settings.MAX_WS_MESSAGE_SIZE_BYTES:
                err_env = BaseMessageEnvelope.create(
                    msg_type=ProtocolMessageType.PROTOCOL_ERROR.value,
                    worker_id=worker_id,
                    payload={
                        "error_code": "MESSAGE_TOO_LARGE",
                        "message": f"Message exceeded maximum allowed size of {settings.MAX_WS_MESSAGE_SIZE_BYTES} bytes.",
                    },
                )
                await websocket.send_text(err_env.to_json())
                continue

            if raw_msg == "ping":
                await websocket.send_text("pong")
                continue

            try:
                data = json.loads(raw_msg)
            except Exception:
                err_env = BaseMessageEnvelope.create(
                    msg_type=ProtocolMessageType.PROTOCOL_ERROR.value,
                    worker_id=worker_id,
                    payload={"error_code": "JSON_PARSE_ERROR", "message": "Malformed JSON payload."},
                )
                await websocket.send_text(err_env.to_json())
                continue

            msg_type = data.get("type")
            job_id = data.get("job_id") or data.get("payload", {}).get("job_id")
            payload = data.get("payload") or {}
            corr_id = data.get("correlation_id")

            async with async_session_factory() as db:
                if msg_type == ProtocolMessageType.JOB_ACK.value:
                    accepted = payload.get("accepted", data.get("accepted", False))
                    rejection_reason = payload.get("rejection_reason", data.get("rejection_reason"))
                    await DispatcherService.process_job_ack(
                        db=db,
                        worker_id=worker_id,
                        job_id=job_id,
                        accepted=accepted,
                        rejection_reason=rejection_reason,
                    )

                elif msg_type == ProtocolMessageType.JOB_STARTED.value:
                    await DispatcherService.process_job_started(
                        db=db,
                        worker_id=worker_id,
                        job_id=job_id,
                    )

                elif msg_type == ProtocolMessageType.JOB_PROGRESS.value:
                    prog_percent = float(payload.get("progress_percent", data.get("progress_percent", 0.0)))
                    prog_msg = payload.get("message", data.get("message"))
                    # Record audit event
                    event = JobEvent(
                        job_id=job_id,
                        event_type="PROGRESS",
                        details={"progress_percent": prog_percent, "message": prog_msg},
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(event)
                    await db.commit()
                    await ws_manager.broadcast("job.progress", {"job_id": job_id, "progress_percent": prog_percent, "message": prog_msg})

                elif msg_type in (ProtocolMessageType.JOB_RESULT.value, ProtocolMessageType.JOB_COMPLETED.value, ProtocolMessageType.JOB_FAILED.value):
                    exit_code = int(payload.get("exit_code", data.get("exit_code", 0)))
                    output = str(payload.get("output", data.get("output", "")))
                    duration_sec = float(payload.get("duration_seconds", data.get("duration_seconds", 0.0)))
                    error = payload.get("error", data.get("error"))
                    await DispatcherService.process_job_result(
                        db=db,
                        worker_id=worker_id,
                        job_id=job_id,
                        exit_code=exit_code,
                        output=output,
                        duration_seconds=duration_sec,
                        error=error,
                    )
                    # When a job completes, check if other queued jobs can now be scheduled
                    await DispatcherService.dispatch_pending_queued_jobs(db)

                    # Send acknowledgement back to worker over WebSocket
                    ack_env = BaseMessageEnvelope.create(
                        msg_type=ProtocolMessageType.JOB_RESULT_ACK.value,
                        job_id=job_id,
                        worker_id=worker_id,
                        correlation_id=corr_id,
                        payload={"job_id": job_id, "status": "recorded"},
                    )
                    await websocket.send_text(ack_env.to_json())

                elif msg_type == ProtocolMessageType.JOB_CANCELLED.value:
                    logger.info("Worker '%s' confirmed cancellation of job '%s'", worker_id, job_id)

                elif msg_type == ProtocolMessageType.HEARTBEAT.value:
                    # Ingest heartbeat over WebSocket
                    hb_now = datetime.now(timezone.utc)
                    stmt = select(Worker).where(Worker.worker_id == worker_id)
                    w = (await db.execute(stmt)).scalar_one_or_none()
                    if w and not w.is_revoked:
                        if "cpu_utilization" in payload:
                            w.cpu_utilization = float(payload["cpu_utilization"])
                        if "available_ram_bytes" in payload:
                            w.available_ram_bytes = int(payload["available_ram_bytes"])
                        if "total_ram_bytes" in payload and payload["total_ram_bytes"] is not None:
                            w.total_ram_bytes = int(payload["total_ram_bytes"])
                        if "active_job_count" in payload:
                            w.active_job_count = int(payload["active_job_count"])
                        w.last_heartbeat = hb_now
                        w.connection_status = "busy" if w.active_job_count > 0 else "online"
                        await db.commit()

                        # Send heartbeat ack
                        ack_env = BaseMessageEnvelope.create(
                            msg_type=ProtocolMessageType.HEARTBEAT_ACK.value,
                            worker_id=worker_id,
                            correlation_id=corr_id,
                            payload={"status": "acknowledged", "server_time": hb_now.isoformat()},
                        )
                        await websocket.send_text(ack_env.to_json())

                        # Broadcast update to dashboard
                        await ws_manager.broadcast(
                            ProtocolMessageType.WORKER_UPDATED.value,
                            {
                                "worker_id": w.worker_id,
                                "cpu_utilization": w.cpu_utilization,
                                "available_ram_bytes": w.available_ram_bytes,
                                "active_job_count": w.active_job_count,
                                "status": w.connection_status,
                            },
                        )

                elif msg_type == ProtocolMessageType.WORKER_DISCONNECTED.value:
                    logger.info("Worker '%s' notified intentional disconnect", worker_id)
                    break

                else:
                    logger.warning("Unrecognized message type '%s' from worker '%s'", msg_type, worker_id)
                    err_env = BaseMessageEnvelope.create(
                        msg_type=ProtocolMessageType.PROTOCOL_ERROR.value,
                        worker_id=worker_id,
                        correlation_id=corr_id,
                        payload={"error_code": "UNKNOWN_MESSAGE_TYPE", "message": f"Unsupported message type: '{msg_type}'"},
                    )
                    await websocket.send_text(err_env.to_json())

    except WebSocketDisconnect:
        logger.info("Worker '%s' disconnected from WebSocket", worker_id)
    except Exception as e:
        logger.error("Worker WebSocket exception for '%s': %s", worker_id, str(e), exc_info=True)
    finally:
        await worker_ws_manager.unregister_worker(worker_id)
        with anyio.CancelScope(shield=True):
            try:
                async with async_session_factory() as db:
                    await scheduler_engine.handle_worker_disconnect_cleanup(db, worker_id)
                    stmt = select(Worker).where(Worker.worker_id == worker_id)
                    w = (await db.execute(stmt)).scalar_one_or_none()
                    if w:
                        w.connection_status = "disconnected"
                        await db.commit()
                        await ws_manager.broadcast(
                            ProtocolMessageType.WORKER_DISCONNECTED.value,
                            {"worker_id": worker_id, "status": "disconnected"},
                        )
            except Exception as e:
                logger.error("Error during worker disconnect cleanup: %s", str(e))
