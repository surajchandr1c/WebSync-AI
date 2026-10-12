import abc
import importlib.util
import logging
import platform
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


# Workload capability inspection
_cached_ollama_time: float = 0.0
_cached_ollama_result: Tuple[bool, List[str]] = (False, [])


def detect_ollama_models(
    ollama_url: Optional[str] = None,
    timeout: float = 1.0,
    force_refresh: bool = False,
) -> Tuple[bool, List[str]]:
    """Check if local Ollama API is reachable and retrieve available models.

    Returns:
        (is_available, list_of_model_names)
    """
    global _cached_ollama_time, _cached_ollama_result
    import time

    now = time.time()
    if not force_refresh and (now - _cached_ollama_time) < 15.0:
        return _cached_ollama_result

    check_cloud = (ollama_url is None)
    if ollama_url is None:
        try:
            from worker.agent.config import settings
            ollama_url = getattr(settings, "WEB_SYNC_OLLAMA_URL", "http://localhost:11434")
        except Exception:
            ollama_url = "http://localhost:11434"

    ollama_url = ollama_url.rstrip("/")
    tags_url = f"{ollama_url}/api/tags"

    models = []
    is_available = False

    # 1. Check local Ollama instance
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
                        models.append(name)
                is_available = True
    except Exception as e:
        logger.debug("Local Ollama is not reachable at %s: %s", tags_url, str(e))

    # 2. Check Ollama Cloud API if OLLAMA_API_KEY is configured and no specific local URL was passed
    if check_cloud:
        try:
            import os
            from worker.agent.config import settings
            api_key = os.environ.get("OLLAMA_API_KEY") or getattr(settings, "OLLAMA_API_KEY", None)
            if api_key:
                cloud_host = getattr(settings, "OLLAMA_HOST", "https://ollama.com").rstrip("/")
                from ollama import Client
                cloud_client = Client(host=cloud_host, headers={"Authorization": f"Bearer {api_key}"})
                cloud_list = cloud_client.list()
                cloud_models = [m.model for m in getattr(cloud_list, "models", []) if getattr(m, "model", None)]
                if cloud_models:
                    models.extend(cloud_models)
                    is_available = True
                elif "gemma4:31b" not in models:
                    models.append("gemma4:31b")
                    is_available = True
        except Exception as e:
            logger.debug("Ollama Cloud models check skipped: %s", str(e))

    deduped = list(dict.fromkeys(models))
    _cached_ollama_time = now
    _cached_ollama_result = (is_available, deduped)
    return is_available, deduped


def get_supported_workloads() -> List[str]:
    """Inspect local environment to return only workloads the node can execute."""
    supported = ["matrix_multiply", "data_processing"]

    # Check if PIL (Pillow) is available for image_processing
    if importlib.util.find_spec("PIL") is not None:
        supported.append("image_processing")

    # Check if Ollama is reachable for llm_prompt workload
    is_ollama_ok, _ = detect_ollama_models(timeout=0.5)
    if is_ollama_ok:
        supported.append("llm_prompt")

    return supported
