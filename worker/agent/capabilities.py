import abc
import importlib.util
import logging
import platform
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("websync-worker.capabilities")


class BaseGPUProvider(abc.ABC):
    """Abstract interface for vendor-specific GPU detection and telemetry."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if GPU hardware and driver are operational."""
        pass

    @abc.abstractmethod
    def get_static_devices(self) -> List[Dict[str, Any]]:
        """Return static specifications for installed GPU devices."""
        pass

    @abc.abstractmethod
    def sample_metrics(self) -> List[Dict[str, Any]]:
        """Sample instantaneous GPU utilization and memory consumption."""
        pass


class NvidiaGPUProvider(BaseGPUProvider):
    """NVIDIA GPU provider using maintained nvidia-ml-py / pynvml."""

    def __init__(self):
        self._initialized = False
        self._init_error = None
        self._pynvml = None
        self._try_initialize()

    def _try_initialize(self) -> None:
        try:
            import pynvml
            pynvml.nvmlInit()
            self._pynvml = pynvml
            self._initialized = True
            logger.info("NVIDIA NVML successfully initialized.")
        except ImportError:
            self._init_error = "pynvml (nvidia-ml-py) not installed"
            logger.debug("NVIDIA GPU detection: %s", self._init_error)
        except Exception as e:
            self._init_error = f"NVML init failed: {str(e)}"
            logger.debug("NVIDIA GPU detection: %s", self._init_error)

    def is_available(self) -> bool:
        if not self._initialized or not self._pynvml:
            return False
        try:
            count = self._pynvml.nvmlDeviceGetCount()
            return count > 0
        except Exception:
            return False

    def get_static_devices(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        devices = []
        try:
            count = self._pynvml.nvmlDeviceGetCount()
            for i in range(count):
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(i)
                raw_name = self._pynvml.nvmlDeviceGetName(handle)
                name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else str(raw_name)
                mem = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                devices.append({
                    "name": name,
                    "memory_total_bytes": int(mem.total),
                })
        except Exception as e:
            logger.warning("Error inspecting NVIDIA static devices: %s", str(e))
        return devices

    def sample_metrics(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        samples = []
        try:
            count = self._pynvml.nvmlDeviceGetCount()
            for i in range(count):
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(i)
                mem = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
                raw_name = self._pynvml.nvmlDeviceGetName(handle)
                name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else str(raw_name)
                samples.append({
                    "name": name,
                    "memory_total_bytes": int(mem.total),
                    "memory_used_bytes": int(mem.used),
                    "memory_free_bytes": int(mem.free),
                    "utilization_percent": float(util.gpu),
                })
        except Exception as e:
            logger.warning("Error sampling NVIDIA GPU telemetry: %s", str(e))
        return samples

    def shutdown(self) -> None:
        if self._initialized and self._pynvml:
            try:
                self._pynvml.nvmlShutdown()
            except Exception:
                pass
            self._initialized = False


class AppleSiliconGPUProvider(BaseGPUProvider):
    """Extension point for Apple Silicon Metal GPU telemetry."""

    def is_available(self) -> bool:
        return platform.system() == "Darwin" and platform.machine() == "arm64"

    def get_static_devices(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        return [{"name": "Apple Silicon Unified GPU", "memory_total_bytes": 0}]

    def sample_metrics(self) -> List[Dict[str, Any]]:
        return []


def get_gpu_provider() -> BaseGPUProvider:
    """Resolve the appropriate GPU provider for the current host."""
    nvidia = NvidiaGPUProvider()
    if nvidia.is_available():
        return nvidia

    if platform.system() == "Darwin":
        apple = AppleSiliconGPUProvider()
        if apple.is_available():
            return apple

    return nvidia  # Returns inactive nvidia provider gracefully


# Model normalization and matching helpers
def normalize_model_name(name: str) -> str:
    """Normalize model identifier into canonical form (lowercase, stripped, :latest default tag)."""
    if not name or not isinstance(name, str):
        return ""
    cleaned = name.strip().lower()
    if not cleaned:
        return ""
    if ":" not in cleaned:
        return f"{cleaned}:latest"
    return cleaned


def model_matches(requested: str, installed: str) -> bool:
    """Return True if installed model matches requested model tag.

    - If requested has no tag (e.g. 'llama3.2'), it matches 'llama3.2', 'llama3.2:latest', or any model whose canonical name is 'llama3.2:latest'.
    - If requested has an explicit tag (e.g. 'llama3.2:3b'), it must strictly match 'llama3.2:3b'.
    - Tag 'llama3.2:3b' will NEVER match 'llama3.2:1b'.
    """
    if not requested or not installed:
        return False
    req = requested.strip().lower()
    inst = installed.strip().lower()

    if req == inst:
        return True

    # If requested has no tag, check canonical :latest match
    if ":" not in req:
        return inst == f"{req}:latest" or inst == req

    # If requested has an explicit tag (e.g. "llama3.2:3b" or "llama3.2:latest")
    inst_canonical = inst if ":" in inst else f"{inst}:latest"
    return req == inst_canonical


# Workload capability inspection
_cached_ollama_time: float = 0.0
_cached_ollama_status: Dict[str, Any] = {
    "status": "not_installed",
    "is_available": False,
    "installed_models": [],
    "last_checked": None,
    "error": None,
}


def detect_ollama_status(
    ollama_url: Optional[str] = None,
    timeout: float = 1.0,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Inspect local Ollama daemon and retrieve locally downloaded models.

    Accurately queries the local Ollama instance (GET /api/tags) and never fabricates
    or advertises cloud catalog models as locally available.

    Returns:
        Dict with keys:
            status: "ready" | "stopped" | "not_installed" | "unreachable"
            is_available: bool
            installed_models: List[str]
            last_checked: str (ISO 8601 UTC)
            error: Optional[str]
    """
    global _cached_ollama_time, _cached_ollama_status
    import time

    now = time.time()
    if not force_refresh and (now - _cached_ollama_time) < 10.0 and _cached_ollama_status.get("last_checked"):
        return _cached_ollama_status

    if ollama_url is None:
        try:
            from worker.agent.config import settings
            ollama_url = getattr(settings, "WEB_SYNC_OLLAMA_URL", "http://localhost:11434")
        except Exception:
            ollama_url = "http://localhost:11434"

    ollama_url = ollama_url.rstrip("/")
    tags_url = f"{ollama_url}/api/tags"

    # Check whether ollama binary is installed on system PATH
    has_binary = shutil.which("ollama") is not None

    models: List[str] = []
    is_available = False
    status_str = "not_installed" if not has_binary else "stopped"
    error_msg: Optional[str] = None

    try:
        import httpx
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(tags_url)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("models", [])
                for item in raw_models:
                    name = item.get("name") or item.get("model")
                    if name and isinstance(name, str):
                        models.append(name.strip())
                is_available = True
                status_str = "ready"
            else:
                status_str = "unreachable"
                error_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        error_msg = str(e)
        if has_binary:
            status_str = "stopped"
        else:
            status_str = "not_installed"
        logger.debug("Local Ollama check at %s: %s (%s)", tags_url, status_str, error_msg)

    deduped = list(dict.fromkeys(models))
    now_iso = datetime.now(timezone.utc).isoformat()

    result = {
        "status": status_str,
        "is_available": is_available,
        "installed_models": deduped,
        "last_checked": now_iso,
        "error": error_msg,
    }

    _cached_ollama_time = now
    _cached_ollama_status = result
    return result


def detect_ollama_models(
    ollama_url: Optional[str] = None,
    timeout: float = 1.0,
    force_refresh: bool = False,
) -> Tuple[bool, List[str]]:
    """Check if local Ollama API is reachable and retrieve available models.

    Returns:
        (is_available, list_of_model_names)
    """
    status_info = detect_ollama_status(
        ollama_url=ollama_url,
        timeout=timeout,
        force_refresh=force_refresh,
    )
    return status_info["is_available"], status_info["installed_models"]


def get_supported_workloads() -> List[str]:
    """Inspect local environment to return only workloads the node can execute."""
    supported = ["matrix_multiply", "data_processing"]

    # Check if PIL (Pillow) is available for image_processing
    if importlib.util.find_spec("PIL") is not None:
        supported.append("image_processing")

    # Check if Ollama is reachable for llm_prompt workload
    status_info = detect_ollama_status(timeout=0.5)
    if status_info["is_available"]:
        supported.append("llm_prompt")

    return supported
