# WebSync AI — Security Audit & Threat Model Report

**Audit Date:** October 12, 2026  
**Auditor:** Application Security Reviewer & Distributed Systems Architect  
**Classification:** Internal Platform Security Assessment  
**Repository:** WebSync AI — Cross-Network Distributed Compute & AI Inference Mesh

---

## 1. Threat Model & Attack Surface Overview

WebSync AI coordinates distributed computational nodes across private networks, public cloud environments, and remote home workstations. This architecture presents five distinct security boundaries:

```mermaid
flowchart LR
    Operator[Operator / Browser UI] <-->|HTTPS / WSS| Coordinator[Central Coordinator API]
    Coordinator <-->|TLS & Binary Protocol| Postgres[(PostgreSQL DB)]
    Coordinator <-->|Authenticated WSS & REST| WorkerA[Worker Node Alpha]
    Coordinator <-->|Authenticated WSS & REST| WorkerB[Worker Node Beta]
    WorkerB <-->|Local Loopback HTTP Only| Ollama[Local Ollama API<br/>127.0.0.1:11434]
```

### Primary Attack Vectors Analyzed:
1. **Rogue Worker Injection:** An unauthorized node attempting to register and receive sensitive compute payloads or steal jobs.
2. **Privilege Escalation:** An unauthenticated caller or normal operator attempting to assign admin privileges.
3. **Arbitrary Code Execution (RCE):** Malicious workloads attempting to escape execution boundaries using shell escapes or Python `eval()`.
4. **Denial of Service (DoS):** Flooding the coordinator with oversized prompt payloads or rapid-fire registration requests.
5. **Credential Leakage in Logs:** Accidental emission of JWT bearer tokens, pre-shared secrets, or database passwords to centralized log aggregators.
6. **Cross-Worker Data Tampering:** Worker A attempting to acknowledge or submit results for jobs assigned to Worker B.

---

## 2. Authentication & Authorization Architecture

### 2.1 Cryptographic Token Segregation
WebSync AI strictly enforces role-typed JWT tokens signed via HMAC-SHA256 (`HS256`):

- **User Access Tokens:**
  - `type: "user"`
  - `role: "admin" | "operator"`
  - Expiry: 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
  - Validated by `get_current_user` dependency.
- **Worker Authentication Tokens:**
  - `type: "worker"`
  - `sub: <worker_id>`
  - Expiry: 24 hours (`WORKER_TOKEN_EXPIRE_MINUTES`)
  - Validated by `get_current_worker` dependency.

> **Security Verification:** If a worker node presents its worker JWT to an operator endpoint (such as `/api/v1/jobs` or `/api/v1/users`), the endpoint immediately raises `HTTP 403 Forbidden` (`"Token is not authorized for user access"`). User tokens are similarly rejected on worker channels.

### 2.2 Worker Enrollment Safeguards
- **Development Mode:** Allows pre-shared `WORKER_DEV_AUTH_TOKEN`.
- **Production Mode:**
  - The development token is strictly rejected at startup if `ENVIRONMENT=production`.
  - A cryptographically random `WORKER_ENROLLMENT_SECRET` (minimum 16 characters) or an active administrator JWT is required to register new worker nodes.
  - Stored tokens are hashed using SHA-256 (`_hash_token`) before database persistence.

### 2.3 Administrative Role Protection
- Public self-registration as `admin` is blocked once any user exists in the cluster (`auth.py`). Only an authenticated admin can grant the `admin` role to subsequent accounts.

---

## 3. Remote Execution Safety & Sandbox Analysis

### 3.1 Strict Prohibition of Arbitrary Code Execution
WebSync AI explicitly avoids executing arbitrary shell scripts, bash commands, or Python `eval()`/`exec()` calls:

```python
# executor.py: Deterministic handler resolution
handlers = {
    "matrix_multiply": self._run_matrix_multiply,
    "data_processing": self._run_data_processing,
    "image_processing": self._run_image_processing,
    "llm_prompt": self._run_llm_prompt,
}
```

Any job submitted with a workload type not present in the approved handler map is immediately rejected by the coordinator with `HTTP 422 Unprocessable Content` and rejected by the worker during the handshake.

### 3.2 Ollama Local Loopback Isolation
Remote AI inference (`llm_prompt`) interacts exclusively with Ollama running on the worker's local loopback interface:
- Target endpoint defaults to `http://localhost:11434/api/generate`.
- Ollama is **never** required to expose port 11434 publicly to the Internet.
- Requests pass securely through the existing coordinator-to-worker WebSocket/HTTP tunnel.

---

## 4. Input Validation & Bounds Enforcement

To prevent algorithmic complexity attacks, memory exhaustion, and JSON buffer overflows, the platform enforces hard ceilings at both API gateway and worker execution levels:

| Parameter | Limit | Enforcement Location | Consequence of Violation |
| :--- | :--- | :--- | :--- |
| **Job Input Payload** | 2 MB (`MAX_JOB_INPUT_BYTES`) | Coordinator `schemas/job.py` & Worker `executor.py` | Immediate 422 / Worker Rejection |
| **LLM Prompt Text** | 32,768 characters (`MAX_LLM_PROMPT_CHARS`) | Coordinator `schemas/job.py` | Immediate 422 Error |
| **LLM System Prompt** | 8,192 characters (`MAX_LLM_SYSTEM_CHARS`) | Coordinator `schemas/job.py` | Immediate 422 Error |
| **Matrix Dimension** | 500 × 500 elements | Worker `_run_matrix_multiply` | Immediate Execution Failure |
| **Data Processing Records** | 50,000 records | Worker `_run_data_processing` | Immediate Execution Failure |
| **Output Buffer Length** | 100 KB (`WORKER_MAX_OUTPUT_BYTES`) | Worker `executor.py` | Truncated with explicit warning |
| **WebSocket Frame Size** | 2 MB (`MAX_WS_MESSAGE_SIZE_BYTES`) | Coordinator `api/routes/ws.py` | Frame dropped, protocol error emitted |

---

## 5. Data Protection & Log Sanitization

The platform incorporates an automated logging filter (`SensitiveDataFilter` in `core/logging_config.py`) that attaches to all root log handlers. The filter applies regex substitutions before any log record is emitted to `stdout`, `stderr`, or disk:

```python
# Automatically masked fields:
1. Bearer JWTs                -> [REDACTED_JWT]
2. X-Worker-Auth-Token        -> [REDACTED_TOKEN]
3. Password fields            -> [REDACTED_PASSWORD]
4. Database connection URIs   -> postgresql://user:[REDACTED_SECRET]@host...
5. Coordinator secret keys    -> [REDACTED_SECRET]
```

This prevents accidental exposure of sensitive keys in container logs or log aggregators (such as CloudWatch or Datadog).

---

## 6. Denial of Service & Rate Limiting

### 6.1 Sliding-Window Rate Limiter
- User login (`/api/v1/auth/login`) is capped at `RATE_LIMIT_LOGIN_PER_MINUTE=10` per client IP.
- Registration (`/api/v1/auth/register`, `/api/v1/workers/register`) is capped at `RATE_LIMIT_REGISTER_PER_MINUTE=20` per client IP.
- Rate-limiting headers (`Retry-After`) are returned upon violation.

### 6.2 Memory-Bounded Eviction
In `coordinator/core/rate_limit.py`, the in-memory record store automatically prunes inactive IP queues whenever the tracking dictionary exceeds 250 records, completely mitigating long-term memory leak risks.

---

## 7. Distributed Execution Tampering Protection

### 7.1 Cross-Worker Assignment Verification
In `DispatcherService.process_job_result`, the coordinator validates that the submitting worker matches the assigned worker:

```python
if job.assigned_worker_id and job.assigned_worker_id != worker_id:
    logger.warning("Result rejected: Worker '%s' attempted to submit result for job '%s' assigned to '%s'", worker_id, job_id, job.assigned_worker_id)
    return
```

### 7.2 Terminal State Immutability
Once a job enters `COMPLETED`, `FAILED`, or `CANCELLED`, its state cannot be overwritten by delayed acknowledgements or out-of-order WebSocket packets.

---

## 8. Production Deployment Security Checklist

- [x] Set `ENVIRONMENT=production` in production environment variables.
- [x] Configure `COORDINATOR_SECRET_KEY` with a cryptographically secure random string (minimum 32 characters: `openssl rand -hex 32`).
- [x] Set `WORKER_ENROLLMENT_SECRET` with a secure passphrase (minimum 16 characters).
- [x] Configure `DATABASE_URL` pointing to PostgreSQL (`postgresql+asyncpg://...`). SQLite is blocked in production mode.
- [x] Set `COORDINATOR_ALLOWED_ORIGINS` to the exact frontend domain(s). Wildcard `*` origins are strictly forbidden in production mode.
- [x] Use TLS/HTTPS and WSS for all internet-facing endpoints.
