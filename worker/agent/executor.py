import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional

import psutil
import httpx

from worker.agent.config import settings

logger = logging.getLogger("websync-worker.executor")


class WorkloadExecutionResult:
    """Outcome and telemetry of a completed workload execution."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        exit_code: int,
        output: str,
        duration_seconds: float,
        error: Optional[str] = None,
    ):
        self.job_id = job_id
        self.job_type = job_type
        self.exit_code = exit_code
        self.output = output
        self.duration_seconds = duration_seconds
        self.error = error
        self.success = (exit_code == 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "exit_code": self.exit_code,
            "output": self.output,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "success": self.success,
        }


class ModularJobExecutor:
    """Safe, modular workload executor enforcing strict handler isolation without eval.
    
    IMPORTANT SECURITY NOTICE:
    Pure Python handlers enforce deterministic input bounds validation and algorithmic safety,
    but do NOT provide kernel-level containerization or a virtualized sandbox (such as Docker,
    Firecracker, or gVisor). Handlers execute within the worker Python process with the permissions
    of the running OS user. Never execute arbitrary code or shell strings without container isolation.
    """

    def __init__(self, max_concurrent_jobs: int = 2):
        self.max_concurrent_jobs = max_concurrent_jobs
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def get_active_jobs_count(self) -> int:
        return len(self._active_jobs)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel an in-flight job execution task."""
        async with self._lock:
            task = self._active_jobs.get(job_id)
        if task and not task.done():
            logger.info("Cancelling execution task for job '%s'", job_id)
            task.cancel()
            return True
        return False

    async def execute_job(
        self,
        job_id: str,
        job_type: str,
        input_payload: Dict[str, Any],
        timeout_seconds: int = 300,
    ) -> WorkloadExecutionResult:
        """Execute validated workload adhering strictly to safe registered handlers."""
        # 1. Owner pause toggle check
        if getattr(settings, "WORKER_PAUSE_SHARING", False):
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=0.0,
                error="Node owner has paused workload sharing on this worker",
            )

        # 2. Concurrency limit check
        if len(self._active_jobs) >= self.max_concurrent_jobs:
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=0.0,
                error=f"Node concurrency limit reached (max: {self.max_concurrent_jobs})",
            )

        # 3. Payload size check
        try:
            serialized_input = json.dumps(input_payload)
            max_input = getattr(settings, "WORKER_MAX_INPUT_BYTES", 2 * 1024 * 1024)
            if len(serialized_input.encode("utf-8")) > max_input:
                return WorkloadExecutionResult(
                    job_id=job_id,
                    job_type=job_type,
                    exit_code=-1,
                    output="",
                    duration_seconds=0.0,
                    error=f"Input payload exceeds maximum allowed size ({max_input} bytes)",
                )
        except Exception as e:
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=0.0,
                error=f"Failed to validate input payload: {str(e)}",
            )

        # 4. Host resource threshold checks (CPU & RAM)
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            max_cpu = getattr(settings, "WORKER_MAX_CPU_PERCENT", 90.0)
            if cpu_pct > max_cpu:
                return WorkloadExecutionResult(
                    job_id=job_id,
                    job_type=job_type,
                    exit_code=-1,
                    output="",
                    duration_seconds=0.0,
                    error=f"Host CPU utilization too high ({cpu_pct:.1f}% > {max_cpu:.1f}%)",
                )

            avail_ram_mb = psutil.virtual_memory().available / (1024 * 1024)
            min_ram_mb = getattr(settings, "WORKER_MIN_AVAILABLE_RAM_MB", 512)
            if avail_ram_mb < min_ram_mb:
                return WorkloadExecutionResult(
                    job_id=job_id,
                    job_type=job_type,
                    exit_code=-1,
                    output="",
                    duration_seconds=0.0,
                    error=f"Insufficient available host RAM ({avail_ram_mb:.0f}MB < {min_ram_mb}MB)",
                )
        except Exception as e:
            logger.debug("Host telemetry threshold check skipped: %s", str(e))

        start_time = time.perf_counter()
        task = asyncio.current_task()
        if task:
            async with self._lock:
                self._active_jobs[job_id] = task

        try:
            handler = self._resolve_handler(job_type)
            output = await asyncio.wait_for(
                handler(input_payload),
                timeout=timeout_seconds,
            )
            elapsed = time.perf_counter() - start_time

            # Enforce output length limit
            max_output = getattr(settings, "WORKER_MAX_OUTPUT_BYTES", 100 * 1024)
            if len(output) > max_output:
                output = output[:max_output] + f"\n... [Output truncated at {max_output} bytes limit]"

            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=0,
                output=output,
                duration_seconds=round(elapsed, 4),
            )

        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - start_time
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=round(elapsed, 4),
                error=f"Job timed out after {timeout_seconds}s",
            )

        except asyncio.CancelledError:
            elapsed = time.perf_counter() - start_time
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=-1,
                output="",
                duration_seconds=round(elapsed, 4),
                error="Job execution cancelled by operator",
            )

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error("Job %s execution failed: %s", job_id, str(e))
            return WorkloadExecutionResult(
                job_id=job_id,
                job_type=job_type,
                exit_code=1,
                output="",
                duration_seconds=round(elapsed, 4),
                error=str(e),
            )

        finally:
            async with self._lock:
                self._active_jobs.pop(job_id, None)

    def _resolve_handler(self, job_type: str):
        """Map approved workload type to safe execution function."""
        handlers = {
            "matrix_multiply": self._run_matrix_multiply,
            "data_processing": self._run_data_processing,
            "image_processing": self._run_image_processing,
            "llm_prompt": self._run_llm_prompt,
        }
        if job_type not in handlers:
            raise ValueError(
                f"Unsupported workload '{job_type}'. Approved types: {list(handlers.keys())}"
            )
        return handlers[job_type]

    # --- Safe Pure Handlers ---

    @staticmethod
    async def _run_llm_prompt(payload: Dict[str, Any]) -> str:
        """Execute an authenticated LLM inference request via local Ollama API."""
        prompt = payload.get("prompt")
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("LLM workload requires a non-empty 'prompt' string")

        model = payload.get("model")
        if not model or not isinstance(model, str) or not model.strip():
            raise ValueError("LLM workload requires a non-empty 'model' string identifier")

        system_prompt = payload.get("system")
        temperature = payload.get("temperature")

        ollama_url = getattr(settings, "WEB_SYNC_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        timeout_seconds = getattr(settings, "OLLAMA_TIMEOUT_SECONDS", 300.0)

        # Prepare Ollama /api/generate request
        gen_url = f"{ollama_url}/api/generate"
        req_body: Dict[str, Any] = {
            "model": model.strip(),
            "prompt": prompt.strip(),
            "stream": False,
        }
        if system_prompt and isinstance(system_prompt, str) and system_prompt.strip():
            req_body["system"] = system_prompt.strip()

        options: Dict[str, Any] = {}
        if temperature is not None:
            try:
                options["temperature"] = float(temperature)
            except (ValueError, TypeError):
                pass
        if options:
            req_body["options"] = options

        import os
        api_key = os.environ.get("OLLAMA_API_KEY") or getattr(settings, "OLLAMA_API_KEY", None)

        # Direct Ollama Cloud API support if OLLAMA_API_KEY is configured and cloud model is requested
        use_cloud = (
            payload.get("use_cloud") is True
            or payload.get("provider") == "cloud"
            or model.strip() == "gemma4:31b"
            or model.strip().startswith("gemma4")
            or "cloud" in model.lower()
        )
        if api_key and use_cloud:
            cloud_host = getattr(settings, "OLLAMA_HOST", "https://ollama.com").rstrip("/")
            from ollama import Client

            client = Client(host=cloud_host, headers={"Authorization": f"Bearer {api_key}"})
            messages = []
            if system_prompt and isinstance(system_prompt, str) and system_prompt.strip():
                messages.append({"role": "system", "content": system_prompt.strip()})
            messages.append({"role": "user", "content": prompt.strip()})

            try:
                res = client.chat(
                    model=model.strip(),
                    messages=messages,
                    options=options if options else None,
                )
                msg_content = res.get("message", {}).get("content", "")
                output_payload = {
                    "model": res.get("model", model),
                    "response": msg_content,
                    "eval_count": res.get("eval_count"),
                    "eval_duration_ms": round(res.get("eval_duration", 0) / 1e6, 2) if res.get("eval_duration") else None,
                    "prompt_eval_count": res.get("prompt_eval_count"),
                    "total_duration_ms": round(res.get("total_duration", 0) / 1e6, 2) if res.get("total_duration") else None,
                    "done": res.get("done", True),
                }
                return json.dumps(output_payload, indent=2)
            except Exception as e:
                err_text = str(e)
                if "401" in err_text:
                    raise RuntimeError(f"Ollama Cloud authentication failed (401 Unauthorized): {err_text}") from e
                elif "402" in err_text:
                    raise RuntimeError(f"Ollama Cloud payment plan required (402 Payment Required): {err_text}") from e
                elif "404" in err_text:
                    raise RuntimeError(f"Ollama Cloud model '{model}' not found (404 Not Found): {err_text}") from e
                elif "429" in err_text:
                    raise RuntimeError(f"Ollama Cloud rate limit reached (429 Too Many Requests): {err_text}") from e
                raise RuntimeError(f"Ollama Cloud inference failed: {err_text}") from e

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(gen_url, json=req_body)

                if response.status_code == 404:
                    err_msg = ""
                    try:
                        err_msg = response.json().get("error", "")
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"Model '{model}' not found in local Ollama repository on this node. "
                        f"To download it, run: 'ollama pull {model}'. (Details: {err_msg or response.text})"
                    )

                if response.status_code != 200:
                    err_msg = ""
                    try:
                        err_msg = response.json().get("error", "")
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"Ollama API returned HTTP error {response.status_code}: {err_msg or response.text}"
                    )

                data = response.json()
                generated_text = data.get("response", "")

                output_payload = {
                    "model": data.get("model", model),
                    "response": generated_text,
                    "eval_count": data.get("eval_count"),
                    "eval_duration_ms": round(data.get("eval_duration", 0) / 1e6, 2) if data.get("eval_duration") else None,
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "total_duration_ms": round(data.get("total_duration", 0) / 1e6, 2) if data.get("total_duration") else None,
                    "done": data.get("done", True),
                }

                return json.dumps(output_payload, indent=2)

        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Ollama inference engine is not reachable on this node at '{ollama_url}'. "
                f"Please ensure Ollama is installed and running ('ollama serve'). (Error: {str(e)})"
            ) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Ollama inference timed out after {timeout_seconds}s for model '{model}'."
            ) from e

    @staticmethod
    async def _run_matrix_multiply(payload: Dict[str, Any]) -> str:
        """Execute linear algebra matrix multiplication with input bounds validation."""
        await asyncio.sleep(0.01)

        # Case 1: Custom explicit matrices provided
        if "matrix_a" in payload and "matrix_b" in payload:
            a = payload["matrix_a"]
            b = payload["matrix_b"]
            if not isinstance(a, list) or not isinstance(b, list) or not a or not b:
                raise ValueError("matrix_a and matrix_b must be non-empty 2D arrays")
            
            rows_a = len(a)
            cols_a = len(a[0])
            rows_b = len(b)
            cols_b = len(b[0])

            if cols_a != rows_b:
                raise ValueError(
                    f"Dimension mismatch for multiplication: matrix_a is {rows_a}x{cols_a}, "
                    f"matrix_b is {rows_b}x{cols_b} (cols_a {cols_a} != rows_b {rows_b})"
                )

            if rows_a > 500 or cols_a > 500 or cols_b > 500:
                raise ValueError("Matrix dimensions exceed allowed limit of 500x500")

            c = [[0.0] * cols_b for _ in range(rows_a)]
            for i in range(rows_a):
                for k in range(cols_a):
                    val_a = float(a[i][k])
                    for j in range(cols_b):
                        c[i][j] += val_a * float(b[k][j])

            # Verifiable trace checksum
            trace = sum(c[i][i] for i in range(min(rows_a, cols_b)))
            return (
                f"Multiplied {rows_a}x{cols_a} by {rows_b}x{cols_b} matrices. "
                f"Result dimension: {rows_a}x{cols_b}. Trace checksum: {round(trace, 4)}. "
                f"Sample element c[0][0]: {round(c[0][0], 4)}"
            )

        # Case 2: Generated dimension benchmark
        dim = payload.get("dimension", 100)
        if not isinstance(dim, int):
            raise ValueError(f"Matrix dimension must be an integer (got {type(dim).__name__})")
        if dim <= 0:
            raise ValueError("Matrix dimension must be positive")
        if dim > 500:
            raise ValueError("Matrix dimension exceeds maximum limit of 500")

        # Construct deterministic sample matrices
        a = [[(i + j) % 10 for j in range(dim)] for i in range(dim)]
        b = [[(i * j) % 10 for j in range(dim)] for i in range(dim)]

        c = [[0] * dim for _ in range(dim)]
        for i in range(dim):
            for k in range(dim):
                for j in range(dim):
                    c[i][j] += a[i][k] * b[k][j]

        checksum = sum(c[i][i] for i in range(dim))
        return f"Successfully multiplied {dim}x{dim} matrices. Trace checksum: {checksum}"

    @staticmethod
    async def _run_data_processing(payload: Dict[str, Any]) -> str:
        """Execute deterministic data transformation & aggregation with strict bounds."""
        await asyncio.sleep(0.01)

        records = payload.get("records")
        if records is not None:
            if not isinstance(records, list):
                raise ValueError("records field must be a list of records")
            if len(records) > 50000:
                raise ValueError(f"Record count ({len(records)}) exceeds maximum limit of 50,000")
            if not records:
                raise ValueError("records list must not be empty")
        else:
            # Fallback benchmark dataset
            records = [{"id": i, "val": i * 1.5, "tag": f"group-{i % 5}"} for i in range(1000)]

        values = []
        for r in records:
            if isinstance(r, dict) and "val" in r:
                try:
                    values.append(float(r["val"]))
                except (ValueError, TypeError):
                    pass

        if not values:
            raise ValueError("No valid numerical 'val' attributes found in records")

        total_sum = sum(values)
        count = len(values)
        avg = total_sum / count
        min_val = min(values)
        max_val = max(values)

        return (
            f"Processed {count} records. Aggregated sum: {total_sum:.2f}, "
            f"Mean: {avg:.2f}, Min: {min_val:.2f}, Max: {max_val:.2f}"
        )

    @staticmethod
    async def _run_image_processing(payload: Dict[str, Any]) -> str:
        """Execute image transform if Pillow is installed."""
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("PIL/Pillow library is not installed for image_processing.")

        width = payload.get("width", 256)
        height = payload.get("height", 256)
        if not isinstance(width, int) or not isinstance(height, int):
            raise ValueError("Width and height must be integers")
        if width <= 0 or height <= 0 or width > 4096 or height > 4096:
            raise ValueError("Width and height must be between 1 and 4096")

        img = Image.new("RGB", (width, height), color=(73, 109, 137))
        return f"Generated image buffer of dimensions {width}x{height} pixels ({img.mode})"
