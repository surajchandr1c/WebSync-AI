import math
from pydantic import BaseModel, Field, model_validator


class SchedulerWeights(BaseModel):
    """Configurable scoring weights for worker selection.
    
    Weights determine the importance of each metric in the overall placement score.
    The sum of weights must equal 1.0 (with a small floating-point tolerance).
    Lower total score indicates a better placement candidate.
    """

    w_cpu: float = Field(
        default=0.35, ge=0.0, le=1.0, description="Weight for CPU utilization percentage"
    )
    w_ram: float = Field(
        default=0.35, ge=0.0, le=1.0, description="Weight for RAM pressure (used / total RAM)"
    )
    w_load: float = Field(
        default=0.30, ge=0.0, le=1.0, description="Weight for active concurrent job load"
    )
    w_lat: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Weight for measured dispatch/network latency"
    )

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "SchedulerWeights":
        total = self.w_cpu + self.w_ram + self.w_load + self.w_lat
        if not math.isclose(total, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError(
                f"Scheduler weights must sum to 1.0 (got sum={total:.5f}: "
                f"w_cpu={self.w_cpu}, w_ram={self.w_ram}, w_load={self.w_load}, w_lat={self.w_lat})"
            )
        return self


# Default scheduler weights configuration
default_weights = SchedulerWeights()
