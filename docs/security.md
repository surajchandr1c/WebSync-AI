# WebSync AI — Security Architecture & Hardening Guide

## 1. Threat Model & Boundaries

WebSync AI coordinates execution across multiple physical computers. Because nodes execute foreign workloads, security boundaries must be strictly enforced at three critical junctures:

1. **Coordinator to Worker Transport**: Prevent man-in-the-middle attacks, eavesdropping, and node spoofing.
2. **Workload Execution on Worker**: Prevent malicious or runaway workloads from compromising the host operating system, accessing private files, or exhausting host resources.
3. **API & Dashboard Access**: Restrict job submission and worker cluster controls to authenticated operators.

---

## 2. Communication Security

### Transport Layer Security (TLS)
- All communication in production environments **must** run over TLS 1.3 (`https://` and `wss://`).
- Mutual TLS (mTLS) or preshared cryptographic registration tokens ensure only authorized worker nodes can join the cluster.

### Token Authentication
- Each worker node is provisioned with a secure registration key (`WORKER_AUTH_TOKEN`).
- Upon registration, the coordinator issues an ephemeral, scoped JWT used for subsequent heartbeats and WebSocket connections.
- Dashboard sessions authenticate via standard secure bearer tokens with refresh mechanics.

---

## 3. Workload Execution Hardening (Worker Nodes)

Workloads must **never** be executed as an unconstrained root/administrator process directly touching the host system.

### Execution Isolation Tiers
1. **Tier 1 (Subprocess with Restricted User / Sandbox)**:
   - Dedicated low-privilege system user account (e.g., `websync-runner`).
   - Strict working directory isolation (`scratch/workspace/{job_id}`).
   - Working directories wiped immediately post-execution.
2. **Tier 2 (OS Resource Quotas)**:
   - Linux: cgroups v2 memory, CPU, and pids limits.
   - Windows: Job Objects with memory limits and kill-on-close protection.
   - Timeout enforcement: Hard execution termination after `timeout_seconds`.
3. **Tier 3 (Containerized Isolation)**:
   - Workloads packaged as standard OCI containers executed via rootless Docker / Podman when container runtime is detected.

### Approved Task Restrictions
- Command whitelist: Arbitrary shell execution is disabled by default; only pre-approved runtimes (e.g., Python scripts within virtualized environments, validated binary entry points) are permissible.
- Network filtering: Restrict worker subprocesses from accessing local subnet private addresses (192.168.x.x, 10.x.x.x) during workload execution to prevent lateral movement.

---

## 4. Secret Management & Configuration Hygiene

- **No Secrets in Source Control**: `.gitignore` strictly rejects `.env`, `.pem`, `.key`, and local `.db` files.
- **Environment Isolation**: Default `.env.example` provides non-sensitive placeholders only.
- **Audit Logging**: All registration events, worker status transitions, and job submissions are appended to an immutable coordinator audit log.
