import abc
import asyncio
import os
import subprocess
import time
from typing import Dict, Any, Optional


class WorkloadResult:
    """Represents the execution outcome of a workload."""

    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_seconds: float,
        success: bool,
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.success = success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
        }


class BaseExecutor(abc.ABC):
    """Abstract base class for workload execution strategies."""

    @abc.abstractmethod
    async def execute(
        self,
        job_id: str,
        script_content: str,
        timeout_seconds: int = 300,
        env: Optional[Dict[str, str]] = None,
    ) -> WorkloadResult:
        """Execute a computational workload within isolation boundaries."""
        pass


class PythonSubprocessExecutor(BaseExecutor):
    """Executes Python workloads in an isolated subprocess with timeout handling."""

    def __init__(self, working_dir: str = "tmp/workloads"):
        self.working_dir = working_dir
        os.makedirs(self.working_dir, exist_ok=True)

    async def execute(
        self,
        job_id: str,
        script_content: str,
        timeout_seconds: int = 300,
        env: Optional[Dict[str, str]] = None,
    ) -> WorkloadResult:
        job_file = os.path.join(self.working_dir, f"{job_id}.py")
        with open(job_file, "w", encoding="utf-8") as f:
            f.write(script_content)

        start_time = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                job_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **(env or {})},
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
            duration = time.time() - start_time
            exit_code = proc.returncode or 0

            return WorkloadResult(
                exit_code=exit_code,
                stdout=stdout_bytes.decode(errors="replace"),
                stderr=stderr_bytes.decode(errors="replace"),
                duration_seconds=round(duration, 3),
                success=(exit_code == 0),
            )
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return WorkloadResult(
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {timeout_seconds} seconds.",
                duration_seconds=round(duration, 3),
                success=False,
            )
        except Exception as e:
            duration = time.time() - start_time
            return WorkloadResult(
                exit_code=-1,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                duration_seconds=round(duration, 3),
                success=False,
            )
        finally:
            if os.path.exists(job_file):
                try:
                    os.remove(job_file)
                except OSError:
                    pass
