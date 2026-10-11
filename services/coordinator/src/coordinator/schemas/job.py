from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator


class ApprovedJobType(str, Enum):
    MATRIX_MULTIPLY = "matrix_multiply"
    DATA_PROCESSING = "data_processing"
    IMAGE_PROCESSING = "image_processing"


class JobState(str, Enum):
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Allowed transitions map: Current State -> Set of Allowed Next States
VALID_JOB_TRANSITIONS = {
    JobState.QUEUED: {JobState.SCHEDULED, JobState.CANCELLED},
    JobState.SCHEDULED: {JobState.RUNNING, JobState.CANCELLED},
    JobState.RUNNING: {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED},
    JobState.COMPLETED: set(),  # Terminal
    JobState.FAILED: set(),     # Terminal
    JobState.CANCELLED: set(),  # Terminal
}


class JobRequirements(BaseModel):
    min_cpu_cores: int = Field(default=1, ge=1, description="Minimum required CPU cores")
    min_ram_mb: int = Field(default=512, ge=128, description="Minimum RAM in Megabytes")
    gpu_required: bool = Field(default=False, description="Whether workload requires GPU hardware")


class JobCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Descriptive job name")
    job_type: str = Field(..., description="Approved job type (matrix_multiply, data_processing, image_processing)")
    input_payload: Dict[str, Any] = Field(..., description="Job execution input parameters")
    requirements: Optional[JobRequirements] = Field(default_factory=JobRequirements)

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        valid_types = [t.value for t in ApprovedJobType]
        if v not in valid_types:
            raise ValueError(f"Job type '{v}' is not supported. Approved types: {', '.join(valid_types)}")
        return v

    @field_validator("input_payload")
    @classmethod
    def validate_input_payload(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("input_payload must not be empty.")
        return v


class JobResponse(BaseModel):
    job_id: str
    name: str
    job_type: str
    status: str
    created_by_user_id: Optional[str] = None
    assigned_worker_id: Optional[str] = None
    input_payload: Dict[str, Any]
    requirements: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    result_exit_code: Optional[int] = None
    result_output: Optional[str] = None
    result_duration_seconds: Optional[float] = None
    result_error: Optional[str] = None
    completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    page_size: int


class JobStatusUpdateRequest(BaseModel):
    status: str
    assigned_worker_id: Optional[str] = None
    result_exit_code: Optional[int] = None
    result_output: Optional[str] = None
    result_duration_seconds: Optional[float] = None
    result_error: Optional[str] = None
