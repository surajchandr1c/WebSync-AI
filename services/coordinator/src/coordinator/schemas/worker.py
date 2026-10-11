from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class GPUInfo(BaseModel):
    name: str
    memory_total_bytes: int


class GPUMetrics(BaseModel):
    utilization_percent: float
    memory_used_bytes: int


class WorkerRegistrationRequest(BaseModel):
    worker_id: str = Field(..., description="Unique worker identifier")
    hostname: str = Field(..., description="Worker machine hostname")
    platform: str = Field(..., description="Operating system platform")
    platform_version: str = Field(..., description="OS release/kernel version")
    cpu_count_logical: int = Field(gt=0, description="Logical CPU core count")
    cpu_count_physical: int = Field(gt=0, description="Physical CPU core count")
    total_memory_bytes: int = Field(gt=0, description="Total installed RAM in bytes")
    gpu_info: Optional[List[GPUInfo]] = Field(default_factory=list, description="Available GPU devices")
    supported_runtimes: List[str] = Field(default=["python"], description="Supported workload runtimes")


class WorkerHeartbeatRequest(BaseModel):
    timestamp: datetime = Field(..., description="Heartbeat generation timestamp")
    cpu_percent: float = Field(ge=0.0, le=100.0, description="Instantaneous CPU utilization percentage")
    memory_used_bytes: int = Field(ge=0, description="Current memory consumed in bytes")
    memory_available_bytes: int = Field(ge=0, description="Remaining available memory in bytes")
    disk_free_bytes: int = Field(ge=0, description="Free disk storage in bytes")
    active_jobs_count: int = Field(default=0, ge=0, description="Number of currently running jobs")
    gpu_metrics: Optional[List[GPUMetrics]] = Field(default_factory=list, description="GPU utilization metrics")


class WorkerResponse(BaseModel):
    worker_id: str
    hostname: str
    platform: str
    status: str = "registered"
    last_seen: Optional[datetime] = None
