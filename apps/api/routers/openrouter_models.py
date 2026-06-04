from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user
from core.config import settings
from core.model_router import OPENROUTER_BASE
from models import User


router = APIRouter(prefix="/openrouter", tags=["openrouter"])


class OpenRouterModelOut(BaseModel):
    id: str
    name: str


_CACHE_TTL_S = 300
_cache: dict[str, tuple[float, list[OpenRouterModelOut]]] = {}


def _is_free_model(m: dict[str, Any]) -> bool:
    model_id = (m.get("id") or "").strip()
    if model_id.endswith(":free"):
        return True
    pricing = m.get("pricing") or {}
    prompt = str(pricing.get("prompt") or "").strip()
    completion = str(pricing.get("completion") or "").strip()
    return prompt in ("0", "0.0", "0.00") and completion in ("0", "0.0", "0.00")


@router.get("/models", response_model=list[OpenRouterModelOut])
async def list_openrouter_models(
    free: bool = True,
    _: User = Depends(get_current_user),
):
    """
    Proxy OpenRouter's models list for the UI.

    We keep this server-side so the browser never needs to hold OPENROUTER_API_KEY.
    """
    cache_key = "free" if free else "all"
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL_S:
        return cached[1]

    if not settings.openrouter_api_key:
        raise HTTPException(503, "AI not configured — set OPENROUTER_API_KEY in .env")

    url = f"{OPENROUTER_BASE}/models"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://lno-os.app",
        "X-Title": "Loop",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as e:
        raise HTTPException(502, f"OpenRouter models fetch failed: {e}")

    models = payload.get("data") or payload.get("models") or []
    out: list[OpenRouterModelOut] = []
    for m in models:
        if not isinstance(m, dict):
            continue
        if free and not _is_free_model(m):
            continue
        model_id = (m.get("id") or "").strip()
        name = (m.get("name") or model_id).strip()
        if not model_id:
            continue
        out.append(OpenRouterModelOut(id=model_id, name=name))

    out.sort(key=lambda x: (x.name.lower(), x.id.lower()))
    _cache[cache_key] = (now, out)
    return out

