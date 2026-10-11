import sys
from unittest.mock import patch, MagicMock
import pytest
from worker.agent.capabilities import (
    NvidiaGPUProvider,
    AppleSiliconGPUProvider,
    get_gpu_provider,
    get_supported_workloads,
)


def test_gpu_provider_fallback_when_pynvml_missing():
    """Verify NvidiaGPUProvider handles missing pynvml library gracefully without crashing."""
    with patch.dict(sys.modules, {"pynvml": None}):
        provider = NvidiaGPUProvider()
        # Must report false and return empty lists without raising
        assert provider.is_available() is False
        assert provider.get_static_devices() == []
        assert provider.sample_metrics() == []


def test_gpu_provider_handles_driver_init_failure():
    """Verify NvidiaGPUProvider handles driver initialization error gracefully."""
    mock_pynvml = MagicMock()
    mock_pynvml.nvmlInit.side_effect = Exception("Driver not loaded")

    with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
        provider = NvidiaGPUProvider()
        assert provider.is_available() is False
        assert provider.get_static_devices() == []
        assert provider.sample_metrics() == []


def test_gpu_provider_with_mocked_device():
    """Verify NvidiaGPUProvider formats device info correctly when NVML returns valid device."""
    mock_pynvml = MagicMock()
    mock_pynvml.nvmlDeviceGetCount.return_value = 1
    mock_handle = MagicMock()
    mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
    mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA RTX 4090"

    mock_mem = MagicMock()
    mock_mem.total = 25769803776
    mock_mem.used = 2147483648
    mock_mem.free = 23622320128
    mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_mem

    mock_util = MagicMock()
    mock_util.gpu = 42
    mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_util

    with patch.dict(sys.modules, {"pynvml": mock_pynvml}):
        provider = NvidiaGPUProvider()
        assert provider.is_available() is True

        devices = provider.get_static_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "NVIDIA RTX 4090"
        assert devices[0]["memory_total_bytes"] == 25769803776

        metrics = provider.sample_metrics()
        assert len(metrics) == 1
        assert metrics[0]["utilization_percent"] == 42.0
        assert metrics[0]["memory_used_bytes"] == 2147483648


def test_workload_capabilities_reporting():
    """Verify workload reporting advertises approved workloads and omits arbitrary shell/python execution."""
    workloads = get_supported_workloads()
    assert "matrix_multiply" in workloads
    assert "data_processing" in workloads
    # Must NOT report arbitrary execution
    assert "shell" not in workloads
    assert "eval" not in workloads
    assert "arbitrary_python" not in workloads
