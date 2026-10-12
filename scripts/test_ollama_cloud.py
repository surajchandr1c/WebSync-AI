"""Test script invoking the WebSync AI worker agent execution engine with Ollama Cloud API.

Sends a prompt to model 'gemma4:31b' through the application's ModularJobExecutor
and prints the authentic reply received from Ollama Cloud.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure repo root and worker are in sys.path
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "worker"))

# Load environment configuration (.env)
from dotenv import load_dotenv
load_dotenv(_repo_root / ".env")

from worker.agent.executor import ModularJobExecutor


async def main():
    prompt_text = "Why is the sky blue? Explain in two clear sentences."
    model_name = "gemma4:31b"

    executor = ModularJobExecutor(max_concurrent_jobs=2)
    payload = {
        "prompt": prompt_text,
        "model": model_name,
    }

    result = await executor.execute_job(
        job_id="test-ollama-cloud-job",
        job_type="llm_prompt",
        input_payload=payload,
        timeout_seconds=60,
    )

    if result.exit_code != 0:
        print(f"ERROR: Execution failed (exit_code={result.exit_code}): {result.error}")
        sys.exit(1)

    try:
        data = json.loads(result.output)
        reply = data.get("response", "")
        print(reply)
    except Exception:
        print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
