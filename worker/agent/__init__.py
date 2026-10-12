"""WebSync AI Worker Agent Package."""

from .metrics import get_static_hardware_specs, sample_system_metrics, WORKER_AGENT_VERSION
from .config import settings, WorkerSettings
from .capabilities import (
    get_gpu_provider,
    get_supported_workloads,
    detect_ollama_models,
    detect_ollama_status,
    normalize_model_name,
    model_matches,
)
from .pull_manager import execute_model_pull, get_active_pulls, is_model_pulling
from .executor import ModularJobExecutor

__version__ = WORKER_AGENT_VERSION

__all__ = [
    "settings",
    "WorkerSettings",
    "get_static_hardware_specs",
    "sample_system_metrics",
    "get_gpu_provider",
    "get_supported_workloads",
    "detect_ollama_models",
    "detect_ollama_status",
    "normalize_model_name",
    "model_matches",
    "execute_model_pull",
    "get_active_pulls",
    "is_model_pulling",
    "ModularJobExecutor",
    "WORKER_AGENT_VERSION",
]
