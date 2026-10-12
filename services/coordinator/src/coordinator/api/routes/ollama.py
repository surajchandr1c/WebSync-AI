"""Server-side route for Ollama Cloud API integration.

Never exposes the OLLAMA_API_KEY to the client or browser.
"""

import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from ollama import Client
from coordinator.config import settings

router = APIRouter(prefix="/ollama", tags=["Ollama Cloud"])


class OllamaChatMessage(BaseModel):
    role: str = "user"
    content: str


class OllamaChatRequest(BaseModel):
    model: str = Field(default="gemma4:31b", description="Model identifier (e.g. gemma4:31b)")
    prompt: Optional[str] = Field(default=None, description="Convenience single prompt string")
    messages: Optional[List[OllamaChatMessage]] = Field(default=None, description="Full chat conversation history")
    system: Optional[str] = Field(default=None, description="System instructions")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)


class OllamaChatResponse(BaseModel):
    model: str
    reply: str
    eval_count: Optional[int] = None
    total_duration_ms: Optional[float] = None


@router.post(
    "/chat",
    response_model=OllamaChatResponse,
    summary="Call Ollama Cloud API from coordinator server",
    description="Invokes Ollama Cloud API (https://ollama.com) with gemma4:31b using the server-side OLLAMA_API_KEY.",
)
async def chat_with_ollama(payload: OllamaChatRequest) -> OllamaChatResponse:
    """Execute chat request against Ollama Cloud API."""
    api_key = os.environ.get("OLLAMA_API_KEY") or settings.OLLAMA_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OLLAMA_API_KEY is not configured on the server.",
        )

    # Formulate messages list
    chat_messages: List[Dict[str, str]] = []
    if payload.system and payload.system.strip():
        chat_messages.append({"role": "system", "content": payload.system.strip()})

    if payload.messages:
        for m in payload.messages:
            chat_messages.append({"role": m.role, "content": m.content})
    elif payload.prompt:
        chat_messages.append({"role": "user", "content": payload.prompt.strip()})
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'prompt' or 'messages' must be provided.",
        )

    options: Dict[str, Any] = {}
    if payload.temperature is not None:
        options["temperature"] = payload.temperature

    host = getattr(settings, "OLLAMA_HOST", "https://ollama.com")
    try:
        client = Client(host=host, headers={"Authorization": f"Bearer {api_key}"})
        res = client.chat(
            model=payload.model.strip(),
            messages=chat_messages,
            options=options if options else None,
        )
        content = res.get("message", {}).get("content", "")
        return OllamaChatResponse(
            model=res.get("model", payload.model),
            reply=content,
            eval_count=res.get("eval_count"),
            total_duration_ms=round(res.get("total_duration", 0) / 1e6, 2) if res.get("total_duration") else None,
        )
    except Exception as e:
        err_msg = str(e)
        if "401" in err_msg:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Ollama Cloud API Key invalid or expired: {err_msg}")
        elif "402" in err_msg:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=f"Model '{payload.model}' requires paid Ollama plan: {err_msg}")
        elif "404" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{payload.model}' not found in Ollama: {err_msg}")
        elif "429" in err_msg:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Ollama Cloud rate limit exceeded: {err_msg}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ollama Cloud API error: {err_msg}")
