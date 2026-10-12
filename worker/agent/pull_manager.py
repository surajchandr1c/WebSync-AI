"""Manager for safe, tracked, user-approved local Ollama model downloads."""

import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Dict, Any, List, Optional, Callable
import httpx

from worker.agent.config import settings
from worker.agent.capabilities import detect_ollama_status, normalize_model_name, model_matches

logger = logging.getLogger("websync-worker.pull_manager")

# Sanitization regex: allows model tags like llama3.2, llama3.2:3b, library/model:tag
MODEL_NAME_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.:/]{0,127}$")

_active_pulls: Dict[str, Dict[str, Any]] = {}
_pull_lock = asyncio.Lock()


def validate_model_name(model_name: str) -> str:
    """Validate model identifier to prevent command injection or malformed parameters."""
    if not model_name or not isinstance(model_name, str):
        raise ValueError("Model name must be a non-empty string.")
    
    cleaned = model_name.strip()
    if not MODEL_NAME_REGEX.match(cleaned):
        raise ValueError(
            f"Invalid model name '{model_name}'. Model names may only contain alphanumeric characters, "
            f"dots, colons, underscores, slashes, and hyphens (e.g. 'llama3.2', 'mistral:latest')."
        )
    return cleaned


def get_active_pulls() -> List[Dict[str, Any]]:
    """Return status of all in-flight model downloads on this node."""
    results = []
    for model_name, data in _active_pulls.items():
        results.append({
            "model": model_name,
            "status": data.get("status", "downloading"),
            "progress_percent": data.get("progress_percent", 0.0),
            "status_message": data.get("status_message", "Downloading model layers..."),
            "started_at": data.get("started_at"),
        })
    return results


def is_model_pulling(model_name: str) -> bool:
    """Return True if model is currently being pulled on this node."""
    norm = normalize_model_name(model_name)
    for active in _active_pulls.keys():
        if model_matches(model_name, active) or model_matches(active, model_name):
            return True
    return False


async def execute_model_pull(
    model_name: str,
    ollama_url: Optional[str] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Execute Ollama model pull with deduplication and progress tracking."""
    valid_name = validate_model_name(model_name)

    if ollama_url is None:
        ollama_url = getattr(settings, "WEB_SYNC_OLLAMA_URL", "http://localhost:11434")
    ollama_url = ollama_url.rstrip("/")

    # Check if already in-flight
    async with _pull_lock:
        if valid_name in _active_pulls:
            return {
                "status": "in_progress",
                "model": valid_name,
                "message": f"Model '{valid_name}' download is already in progress on this node.",
                "progress_percent": _active_pulls[valid_name].get("progress_percent", 0.0),
            }

        # Check if already installed
        status_info = detect_ollama_status(ollama_url=ollama_url, force_refresh=True)
        installed = status_info.get("installed_models", [])
        if any(model_matches(valid_name, m) for m in installed):
            return {
                "status": "already_installed",
                "model": valid_name,
                "message": f"Model '{valid_name}' is already installed on this node.",
                "installed_models": installed,
            }

        start_time_iso = datetime.now(timezone.utc).isoformat()
        _active_pulls[valid_name] = {
            "status": "downloading",
            "progress_percent": 0.0,
            "status_message": "Initiating pull request with Ollama daemon...",
            "started_at": start_time_iso,
        }

    logger.info("Initiated model pull for '%s' against %s", valid_name, ollama_url)

    pull_url = f"{ollama_url}/api/pull"
    try:
        # Stream response from Ollama daemon
        timeout = httpx.Timeout(connect=10.0, read=900.0, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", pull_url, json={"name": valid_name, "stream": True}) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {err_text.decode('utf-8', errors='replace')}")

                import json
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    status_msg = chunk.get("status", "")
                    total = chunk.get("total")
                    completed = chunk.get("completed")

                    pct = 0.0
                    if total and completed and total > 0:
                        pct = round((completed / total) * 100.0, 1)

                    _active_pulls[valid_name]["status_message"] = status_msg
                    _active_pulls[valid_name]["progress_percent"] = pct

                    if progress_callback:
                        try:
                            progress_callback({
                                "model": valid_name,
                                "status": status_msg,
                                "progress_percent": pct,
                                "completed_bytes": completed,
                                "total_bytes": total,
                            })
                        except Exception:
                            pass

        # Pull complete - force refresh cache
        updated_status = detect_ollama_status(ollama_url=ollama_url, force_refresh=True)
        logger.info(
            "Model pull for '%s' completed successfully. Installed models: %s",
            valid_name,
            updated_status.get("installed_models"),
        )

        return {
            "status": "completed",
            "model": valid_name,
            "message": f"Model '{valid_name}' pulled successfully.",
            "installed_models": updated_status.get("installed_models", []),
        }

    except Exception as e:
        logger.error("Failed to pull model '%s': %s", valid_name, str(e))
        return {
            "status": "failed",
            "model": valid_name,
            "error": str(e),
            "message": f"Failed to pull model '{valid_name}': {str(e)}",
        }

    finally:
        async with _pull_lock:
            _active_pulls.pop(valid_name, None)
