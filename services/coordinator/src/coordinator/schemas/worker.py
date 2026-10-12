from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class GPUInfo(BaseModel):
    name: str = Field(..., min_length=1)
    memory_total_bytes: int = Field(ge=0)


class WorkerRegistrationRequest(BaseModel):
    worker_id: str = Field(..., min_length=1, max_length=128, description="Unique worker node identifier")
    display_name: str = Field(..., min_length=1, max_length=128, description="Human-friendly node name")
    hostname: str = Field(..., min_length=1, max_length=128, description="Host system hostname")
    platform: str = Field(..., min_length=1, max_length=64, description="Operating system platform (Linux, Windows, macOS)")
    platform_version: str = Field(default="", max_length=128, description="Kernel or OS release version")
    cpu_utilization: float = Field(default=0.0, ge=0.0, le=100.0, description="Current CPU utilization %")
    total_ram_bytes: int = Field(..., ge=0, description="Total installed physical RAM in bytes")
    available_ram_bytes: int = Field(..., ge=0, description="Currently free/available RAM in bytes")
    supported_workloads: List[str] = Field(
        default=["matrix_multiply", "data_processing", "image_processing"],
        description="List of supported workload identifiers",
    )
    supported_models: List[str] = Field(
        default_factory=list,
        description="List of local LLM models advertised by worker (e.g. from Ollama)",
    )
    gpu_available: bool = Field(default=False, description="Whether supported GPU hardware is present")
    gpu_metadata: List[Dict[str, Any]] = Field(default_factory=list, description="GPU hardware details")
    max_concurrent_jobs: int = Field(default=2, ge=1, le=64, description="Maximum concurrent tasks this node can execute")

    @field_validator("available_ram_bytes")
    @classmethod
    def validate_ram(cls, v: int, info) -> int:
        total = info.data.get("total_ram_bytes")
        if total is not None and v > total:
            raise ValueError("Available RAM cannot exceed total physical RAM")
        return v


class WorkerRegistrationResponse(BaseModel):
    worker_id: str
    display_name: str
    hostname: str
    platform: str
    connection_status: str
    auth_token: str
    heartbeat_interval_seconds: int


class WorkerHeartbeatRequest(BaseModel):
    cpu_utilization: float = Field(..., ge=0.0, le=100.0, description="Current CPU utilization percentage (0-100)")
    available_ram_bytes: int = Field(..., ge=0, description="Remaining available memory in bytes")
    total_ram_bytes: Optional[int] = Field(None, ge=0, description="Updated total physical memory if changed")
    active_job_count: int = Field(default=0, ge=0, description="Currently executing job count")
    gpu_metadata: Optional[List[Dict[str, Any]]] = Field(None, description="Optional GPU telemetry samples")
    supported_models: Optional[List[str]] = Field(None, description="Optional updated list of local LLM models")


class WorkerResponse(BaseModel):
    worker_id: str
    display_name: str
    hostname: str
    platform: str
    platform_version: str
    cpu_utilization: float
    total_ram_bytes: int
    available_ram_bytes: int
    supported_workloads: List[str]
    supported_models: List[str] = Field(default_factory=list)
    gpu_available: bool
    gpu_metadata: List[Dict[str, Any]]
    active_job_count: int
    max_concurrent_jobs: int = 2
    connection_status: str
    last_heartbeat: Optional[datetime] = None
    registered_at: datetime
    is_revoked: bool


class WorkerListResponse(BaseModel):
    items: List[WorkerResponse]
    total: int
    page: int
    page_size: int
