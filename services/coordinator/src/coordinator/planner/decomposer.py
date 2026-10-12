import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    subtask_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    job_type: str
    input_payload: Dict[str, Any]
    dependencies: List[str] = Field(default_factory=list)
    status: str = "PENDING"
    result: Optional[Any] = None


class TaskPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_job_name: str
    subtasks: List[SubTask]
    strategy: str = "independent_parallel"


def decompose_workload(
    job_name: str,
    workload_type: str,
    input_payload: Dict[str, Any],
) -> TaskPlan:
    """Decompose large complex workloads into independent or staged subtasks.
    
    If the workload is a single atomic task, returns a 1-subtask plan.
    """
    # 1. Multi-prompt batch query decomposition
    if workload_type == "llm_prompt" and "prompts" in input_payload:
        raw_prompts = input_payload["prompts"]
        model = input_payload.get("model", "llama3.2:latest")
        system_msg = input_payload.get("system")

        if isinstance(raw_prompts, list) and len(raw_prompts) > 1:
            subtasks = []
            for idx, p in enumerate(raw_prompts, 1):
                subtasks.append(
                    SubTask(
                        name=f"{job_name} - Prompt {idx}",
                        job_type="llm_prompt",
                        input_payload={
                            "prompt": p,
                            "model": model,
                            "system": system_msg,
                        },
                        dependencies=[],
                    )
                )
            return TaskPlan(
                original_job_name=job_name,
                subtasks=subtasks,
                strategy="parallel_batch",
            )

    # 2. Large dataset chunk decomposition
    if workload_type == "data_processing" and "records" in input_payload:
        records = input_payload["records"]
        chunk_size = input_payload.get("chunk_size", 10000)
        if isinstance(records, list) and len(records) > chunk_size:
            subtasks = []
            for i in range(0, len(records), chunk_size):
                chunk = records[i : i + chunk_size]
                idx = (i // chunk_size) + 1
                subtasks.append(
                    SubTask(
                        name=f"{job_name} - Chunk {idx}",
                        job_type="data_processing",
                        input_payload={"records": chunk},
                        dependencies=[],
                    )
                )
            return TaskPlan(
                original_job_name=job_name,
                subtasks=subtasks,
                strategy="chunked_pipeline",
            )

    # Default atomic single task plan
    return TaskPlan(
        original_job_name=job_name,
        subtasks=[
            SubTask(
                name=job_name,
                job_type=workload_type,
                input_payload=input_payload,
                dependencies=[],
            )
        ],
        strategy="atomic",
    )


def aggregate_subtask_results(
    plan: TaskPlan,
    subtask_results: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate and aggregate outputs across completed subtasks."""
    completed = []
    failed = []

    for st in plan.subtasks:
        res = subtask_results.get(st.subtask_id)
        if res and res.get("success"):
            completed.append(res)
        else:
            err = res.get("error", "No result recorded") if res else "Subtask missing"
            failed.append({"subtask_id": st.subtask_id, "name": st.name, "error": err})

    return {
        "plan_id": plan.plan_id,
        "strategy": plan.strategy,
        "total_subtasks": len(plan.subtasks),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "all_succeeded": (len(failed) == 0 and len(completed) == len(plan.subtasks)),
        "partial_results": completed,
        "failures": failed,
    }
