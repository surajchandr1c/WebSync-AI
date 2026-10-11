import abc
import importlib.util
import logging
import platform
from typing import List, Dict, Any, Tuple

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
def get_supported_workloads() -> List[str]:
    """Inspect local environment to return only workloads the node can execute."""
    supported = ["matrix_multiply", "data_processing"]

    # Check if PIL (Pillow) is available for image_processing
    if importlib.util.find_spec("PIL") is not None:
        supported.append("image_processing")

    return supported
