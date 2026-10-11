import platform
import psutil
from typing import Dict, Any, List


def get_static_capabilities() -> Dict[str, Any]:
    """Inspect and return static hardware capabilities of this machine."""
    mem = psutil.virtual_memory()
    
    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_version": platform.release(),
        "architecture": platform.machine(),
        "cpu_count_logical": psutil.cpu_count(logical=True) or 1,
        "cpu_count_physical": psutil.cpu_count(logical=False) or 1,
        "total_memory_bytes": mem.total,
        "gpu_info": [],  # Vendor-specific GPU telemetry will be added in later phase
        "supported_runtimes": ["python"],
    }


def sample_system_metrics() -> Dict[str, Any]:
    """Sample instantaneous real-world resource metrics using psutil."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/") if platform.system() != "Windows" else psutil.disk_usage("C:\\")

    # Sample non-blocking CPU percentage (or short interval if first call)
    cpu_percent = psutil.cpu_percent(interval=None)

    return {
        "cpu_percent": float(cpu_percent),
        "memory_used_bytes": int(mem.used),
        "memory_available_bytes": int(mem.available),
        "memory_percent": float(mem.percent),
        "disk_free_bytes": int(disk.free),
        "disk_percent": float(disk.percent),
    }
