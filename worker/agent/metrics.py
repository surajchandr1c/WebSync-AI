import platform
import time
from typing import Dict, Any, Optional
import psutil
from worker.agent.capabilities import get_gpu_provider, get_supported_workloads, detect_ollama_models

WORKER_AGENT_VERSION = "0.3.0"

# Prime non-blocking CPU measurement
psutil.cpu_percent(interval=None)


def get_static_hardware_specs() -> Dict[str, Any]:
    """Inspect and return static hardware specifications and capabilities."""
    mem = psutil.virtual_memory()
    gpu_provider = get_gpu_provider()
    gpu_available = gpu_provider.is_available()
    gpu_devices = gpu_provider.get_static_devices() if gpu_available else []
    _, models = detect_ollama_models()

    # Uptime in seconds
    uptime_seconds = None
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = round(time.time() - boot_time, 1)
    except Exception:
        pass

    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_version": platform.release(),
        "architecture": platform.machine(),
        "cpu_count_logical": psutil.cpu_count(logical=True) or 1,
        "cpu_count_physical": psutil.cpu_count(logical=False) or 1,
        "total_ram_bytes": int(mem.total),
        "available_ram_bytes": int(mem.available),
        "ram_percent": float(mem.percent),
        "system_uptime_seconds": uptime_seconds,
        "agent_version": WORKER_AGENT_VERSION,
        "gpu_available": gpu_available,
        "gpu_metadata": gpu_devices,
        "supported_workloads": get_supported_workloads(),
        "supported_models": models,
    }


def sample_system_metrics(active_jobs_count: int = 0) -> Dict[str, Any]:
    """Sample instantaneous real-world resource telemetry using psutil and GPU providers.
    
    Uses non-blocking CPU sampling (interval=None) so the worker agent does not block
    or become unresponsive.
    """
    mem = psutil.virtual_memory()

    # CPU percent sampled non-blocking since last invocation
    cpu_percent = psutil.cpu_percent(interval=None)

    # Disk usage
    disk_free_bytes = 0
    try:
        path = "C:\\" if platform.system() == "Windows" else "/"
        disk = psutil.disk_usage(path)
        disk_free_bytes = int(disk.free)
    except Exception:
        pass

    # GPU telemetry
    gpu_provider = get_gpu_provider()
    gpu_metrics = gpu_provider.sample_metrics() if gpu_provider.is_available() else []

    # Local LLM models discovery
    _, models = detect_ollama_models()

    return {
        "cpu_utilization": float(cpu_percent),
        "total_ram_bytes": int(mem.total),
        "available_ram_bytes": int(mem.available),
        "ram_percent": float(mem.percent),
        "disk_free_bytes": disk_free_bytes,
        "active_job_count": active_jobs_count,
        "gpu_metadata": gpu_metrics,
        "supported_models": models,
    }
