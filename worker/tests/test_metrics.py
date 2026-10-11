import pytest
from worker.agent.metrics import get_static_hardware_specs, sample_system_metrics


def test_static_hardware_specs_collection():
    """Verify static hardware collection returns non-empty, genuine machine specs."""
    specs = get_static_hardware_specs()

    assert isinstance(specs["hostname"], str) and len(specs["hostname"]) > 0
    assert specs["platform"] in ("Windows", "Linux", "Darwin")
    assert isinstance(specs["architecture"], str) and len(specs["architecture"]) > 0
    assert specs["cpu_count_logical"] >= 1
    assert specs["cpu_count_physical"] >= 1
    assert specs["total_ram_bytes"] > 0
    assert specs["available_ram_bytes"] > 0
    assert specs["available_ram_bytes"] <= specs["total_ram_bytes"]
    assert 0.0 <= specs["ram_percent"] <= 100.0
    assert isinstance(specs["gpu_available"], bool)
    assert isinstance(specs["gpu_metadata"], list)
    assert len(specs["supported_workloads"]) >= 2
    assert "matrix_multiply" in specs["supported_workloads"]
    assert "data_processing" in specs["supported_workloads"]


def test_instantaneous_metrics_sampling():
    """Verify instantaneous telemetry sampling returns valid numbers within bounds."""
    metrics = sample_system_metrics(active_jobs_count=0)

    # CPU utilization must be bounded between 0 and 100
    assert 0.0 <= metrics["cpu_utilization"] <= 100.0
    assert metrics["total_ram_bytes"] > 0
    assert metrics["available_ram_bytes"] > 0
    assert metrics["available_ram_bytes"] <= metrics["total_ram_bytes"]
    assert 0.0 <= metrics["ram_percent"] <= 100.0
    assert metrics["disk_free_bytes"] >= 0
    assert metrics["active_job_count"] == 0
    assert isinstance(metrics["gpu_metadata"], list)
