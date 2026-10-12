from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator


import re
from coordinator.config import settings

class ApprovedJobType(str, Enum):
    MATRIX_MULTIPLY = "matrix_multiply"
    DATA_PROCESSING = "data_processing"
    IMAGE_PROCESSING = "image_processing"
    LLM_PROMPT = "llm_prompt"
    DISTRIBUTED_DATA_PROCESSING = "distributed_data_processing"


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
    min_ram_mb: int = Field(default=512, ge=0, description="Minimum RAM in Megabytes")
    min_ram_bytes: Optional[int] = Field(None, ge=0, description="Minimum RAM in exact bytes (overrides min_ram_mb if specified)")
    gpu_required: bool = Field(default=False, description="Whether workload requires GPU hardware")
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Maximum execution timeout in seconds (capped at 3600s)")
    target_worker_id: Optional[str] = Field(None, max_length=128, description="Target specific worker node for execution")
    model: Optional[str] = Field(None, max_length=128, description="Target AI model required on worker")

    def get_min_ram_bytes(self) -> int:
        if self.min_ram_bytes is not None:
            return self.min_ram_bytes
        return self.min_ram_mb * 1024 * 1024


class JobCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Descriptive job name")
    job_type: str = Field(..., description="Approved job type (matrix_multiply, data_processing, image_processing, llm_prompt, distributed_data_processing)")
    input_payload: Dict[str, Any] = Field(..., description="Job execution input parameters")
    requirements: Optional[JobRequirements] = Field(default_factory=JobRequirements)
    parent_job_id: Optional[str] = Field(None, max_length=36, description="Parent job ID for distributed child tasks")

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        valid_types = [t.value for t in ApprovedJobType]
        if v not in valid_types:
            raise ValueError(f"Job type '{v}' is not supported. Approved types: {', '.join(valid_types)}")
        return v

    @field_validator("input_payload")
    @classmethod
    def validate_input_payload(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        if not v:
            raise ValueError("input_payload must not be empty.")
        import json
        try:
            payload_bytes = len(json.dumps(v))
        except Exception as e:
            raise ValueError(f"input_payload must be JSON-serializable: {str(e)}")
        if payload_bytes > 2 * 1024 * 1024:
            raise ValueError(f"input_payload exceeds maximum size limit of 2MB ({payload_bytes} bytes).")

        # Specific validation for llm_prompt
        job_type = info.data.get("job_type")
        if job_type == ApprovedJobType.LLM_PROMPT.value:
            prompt = v.get("prompt")
            if not prompt or not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("input_payload for 'llm_prompt' must contain a non-empty 'prompt' string.")
            max_prompt = getattr(settings, "MAX_LLM_PROMPT_CHARS", 32768)
            if len(prompt) > max_prompt:
                raise ValueError(f"Prompt length ({len(prompt)} chars) exceeds maximum limit of {max_prompt} characters.")

            model = v.get("model")
            if not model or not isinstance(model, str) or not model.strip():
                raise ValueError("input_payload for 'llm_prompt' must specify a valid 'model' identifier.")
            # Sanitize model name: letters, digits, '.', ':', '-', '_', '/'
            if not re.match(r"^[a-zA-Z0-9_\-\.:/]+$", model.strip()):
                raise ValueError(f"Invalid model identifier '{model}'. Model names must contain only alphanumeric, colon, dash, underscore, and dot characters.")

            if "system" in v and v["system"] is not None:
                system_text = v["system"]
                if not isinstance(system_text, str):
                    raise ValueError("'system' prompt must be a string if provided.")
                max_sys = getattr(settings, "MAX_LLM_SYSTEM_CHARS", 8192)
                if len(system_text) > max_sys:
                    raise ValueError(f"System prompt length exceeds maximum limit of {max_sys} characters.")

            if "temperature" in v and v["temperature"] is not None:
                temp = v["temperature"]
                if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 2.0:
                    raise ValueError("Temperature must be a number between 0.0 and 2.0.")

        elif job_type == ApprovedJobType.DISTRIBUTED_DATA_PROCESSING.value:
            if "partitions" in v:
                partitions = v["partitions"]
                if not isinstance(partitions, int) or partitions < 2 or partitions > 16:
                    raise ValueError("Partitions for 'distributed_data_processing' must be an integer between 2 and 16.")
            if "records" in v and v["records"] is not None and not isinstance(v["records"], list):
                raise ValueError("records for 'distributed_data_processing' must be a list if provided.")

        return v


class JobResponse(BaseModel):
    job_id: str
    name: str
    job_type: str
    status: str
    created_by_user_id: Optional[str] = None
    assigned_worker_id: Optional[str] = None
    parent_job_id: Optional[str] = None
    child_count: Optional[int] = 0
    input_payload: Dict[str, Any]
    requirements: Dict[str, Any]
    placement_reason: Optional[Dict[str, Any]] = None
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


# --- Dispatch & Worker Communication Protocols ---

class JobDispatchEnvelope(BaseModel):
    type: str = "job.dispatch"
    job_id: str
    job_type: str
    input_payload: Dict[str, Any]
    timeout_seconds: int = 300
    correlation_id: str


class JobAckMessage(BaseModel):
    type: str = "job.ack"
    job_id: str
    worker_id: str
    accepted: bool
    rejection_reason: Optional[str] = None
    correlation_id: Optional[str] = None


class JobStartedMessage(BaseModel):
    type: str = "job.started"
    job_id: str
    worker_id: str


class JobProgressMessage(BaseModel):
    type: str = "job.progress"
    job_id: str
    worker_id: str
    progress_percent: float = Field(..., ge=0.0, le=100.0)
    message: Optional[str] = None


class JobResultMessage(BaseModel):
    type: str = "job.result"
    job_id: str
    worker_id: str
    exit_code: int
    output: str
    duration_seconds: float = Field(..., ge=0.0)
    error: Optional[str] = None


class JobEventResponse(BaseModel):
    id: str
    job_id: str
    event_type: str
    details: Dict[str, Any]
    created_at: datetime


class JobEventListResponse(BaseModel):
    items: List[JobEventResponse]
    total: int
    page: int
    page_size: int

