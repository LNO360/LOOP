"""
OpenRouter model routing with per-task strengths and automatic fallback.

Each profile uses models suited to that job (DeepSeek, MiniMax, Qwen, GLM, Kimi).
If a model fails (quota, timeout, provider error), the next in chain is tried.
`openrouter/free` is the last-resort safety net for interactive routes, and the
**only** model for background/cron profiles (digest, task, knowledge).

Haiku / Claude models are intentionally excluded — use Chinese/open models instead.
"""

from __future__ import annotations

from openai import OpenAI
from core.config import settings
from typing import Any
import logging

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def _is_billing_error(exc: Exception) -> bool:
    """
    OpenRouter 402 / insufficient credits — do not walk the fallback chain;
    every model will fail the same way and starve API workers.
    """
    code = getattr(exc, "status_code", None)
    if code == 402:
        return True
    msg = str(exc).lower()
    if "error code: 402" in msg or "requires more credits" in msg:
        return True
    if "402" in msg and "credit" in msg:
        return True
    return False


# Profiles used by schedulers / background jobs — never walk paid model chains.
BACKGROUND_PROFILES: frozenset[str] = frozenset({
    "digest",
    "task",
    "knowledge",
    "cron",
})

# Models we never route to (user preference)
BLOCKED_MODELS: set[str] = {
    "anthropic/claude-3.5-haiku",
    "anthropic/claude-3-haiku",
    "anthropic/claude-haiku-4.5",
}

# Profile -> ordered model chain (best first; openrouter/free appended last in code)
MODEL_PROFILES: dict[str, dict[str, Any]] = {
    # Tool-calling: create/update tasks & projects
    "agent_tools": {
        "strength": "Agentic tool use, ops workflows (DeepSeek + MiniMax)",
        "models": [
            "deepseek/deepseek-v4-flash",   # fast agentic, cheap, strong tool loops
            "minimax/minimax-m2.1",         # coding/agent workflows, tool use
            "qwen/qwen3-coder-next",        # structured coding & task output
            "openrouter/owl-alpha",         # reliable free router model
        ],
    },
    # Workspace chat (tools + natural language)
    "agent_chat": {
        "strength": "Conversational assistant + light reasoning",
        "models": [
            "deepseek/deepseek-v4-flash",
            "moonshotai/kimi-k2.5",         # strong general reasoning (Moonshot)
            "minimax/minimax-m2.1",
            "openrouter/owl-alpha",
        ],
    },
    # Extract tasks from message (JSON)
    "extract_tasks": {
        "strength": "Structured JSON extraction",
        "models": [
            "qwen/qwen3.5-flash-02-23",     # fast, good instruction following
            "deepseek/deepseek-v4-flash",
            "z-ai/glm-4.7-flash",           # Zhipu GLM — cheap, capable
            "openrouter/owl-alpha",
        ],
    },
    # Background task extraction from messages
    "task": {
        "strength": "Quick action-item detection",
        "models": [
            "qwen/qwen3.5-flash-02-23",
            "deepseek/deepseek-v4-flash",
            "openrouter/owl-alpha",
        ],
    },
    # Project analysis / PM insights
    "project_manager": {
        "strength": "Planning, risks, multi-task analysis",
        "models": [
            "moonshotai/kimi-k2.5",         # long-context reasoning
            "deepseek/deepseek-v4-flash",
            "minimax/minimax-m2.1",
            "z-ai/glm-5-turbo",             # stronger GLM for analysis
        ],
    },
    # Daily digest / summaries
    "digest": {
        "strength": "Concise operational summaries",
        "models": [
            "qwen/qwen3.5-flash-02-23",
            "z-ai/glm-4.7-flash",
            "deepseek/deepseek-v4-flash",
            "openrouter/owl-alpha",
        ],
    },
    # Doc writing / editing
    "docs": {
        "strength": "Long-form writing, SOPs, documentation",
        "models": [
            "moonshotai/kimi-k2.5",
            "minimax/minimax-m2.5",         # office/productivity tuned (paid)
            "deepseek/deepseek-v4-flash",
            "qwen/qwen3.6-plus",
        ],
    },
    # Knowledge / memory extraction
    "knowledge": {
        "strength": "Fact extraction, recall, multilingual",
        "models": [
            "qwen/qwen3.6-plus",
            "deepseek/deepseek-v4-flash",
            "z-ai/glm-4.7",
            "moonshotai/kimi-k2.5",
        ],
    },
}

AGENT_TYPE_TO_PROFILE: dict[str, str] = {
    "task": "task",
    "project_manager": "project_manager",
    "docs": "docs",
    "digest": "digest",
    "knowledge": "knowledge",
    "memory": "knowledge",
    "chat": "agent_chat",
}


def get_openrouter_client() -> OpenAI:
    return OpenAI(
        base_url=OPENROUTER_BASE,
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": "https://lno-os.app",
            "X-Title": "LNO OS",
        },
    )


def _dedupe(models: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in models:
        m = (m or "").strip()
        if not m or m in seen or m in BLOCKED_MODELS:
            continue
        seen.add(m)
        out.append(m)
    return out


def is_background_profile(profile: str) -> bool:
    return profile in BACKGROUND_PROFILES


def models_for_profile(profile: str) -> list[str]:
    """Return ordered model chain for a profile, with env overrides applied."""
    if is_background_profile(profile):
        model = (settings.openrouter_cron_model or "openrouter/free").strip()
        return [model or "openrouter/free"]

    spec = MODEL_PROFILES.get(profile, MODEL_PROFILES["agent_chat"])
    chain: list[str] = list(spec["models"])

    # User overrides from .env (inserted first if not blocked)
    if profile in ("agent_tools", "agent_chat", "extract_tasks"):
        if settings.openrouter_agent_model:
            chain.insert(0, settings.openrouter_agent_model)
    if settings.openrouter_model:
        chain.insert(0, settings.openrouter_model)

    fallback = settings.openrouter_fallback_model or "openrouter/free"
    chain.append(fallback)

    return _dedupe(chain)


def profile_for_agent_type(agent_type: str) -> str:
    return AGENT_TYPE_TO_PROFILE.get(agent_type, "agent_chat")


def chat_with_fallback(
    *,
    profile: str,
    messages: list[dict],
    max_tokens: int = 1024,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    client: OpenAI | None = None,
) -> tuple[Any, str]:
    """
    Try models in profile order until one succeeds.
    Returns (completion_response, model_used).
    """
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    client = client or get_openrouter_client()
    models = models_for_profile(profile)
    last_error: Exception | None = None

    for model in models:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        try:
            response = client.chat.completions.create(**kwargs)
            if model != models[0]:
                logger.info(f"[model_router] profile={profile} succeeded with fallback model={model}")
            return response, model
        except Exception as e:
            last_error = e
            logger.warning(f"[model_router] profile={profile} model={model} failed: {e}")
            if _is_billing_error(e):
                raise
            continue

    raise last_error or RuntimeError(f"All models failed for profile={profile}")


def create_stream_with_fallback(
    *,
    profile: str,
    messages: list[dict],
    max_tokens: int = 1024,
    client: OpenAI | None = None,
) -> tuple[Any, str]:
    """
    Open a streaming chat completion, trying models in profile order until one
    accepts the request. Returns (stream_iterator, model_used).

    Fallback only covers connection/creation failures — once a model starts
    streaming we commit to it. Caller iterates the returned object for chunks.
    """
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    client = client or get_openrouter_client()
    models = models_for_profile(profile)
    last_error: Exception | None = None

    for model in models:
        try:
            stream = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
                stream=True,
            )
            if model != models[0]:
                logger.info(f"[model_router] profile={profile} streaming via fallback model={model}")
            return stream, model
        except Exception as e:
            last_error = e
            logger.warning(f"[model_router] profile={profile} stream model={model} failed: {e}")
            if _is_billing_error(e):
                raise
            continue

    raise last_error or RuntimeError(f"All models failed for profile={profile}")


def get_profile_info() -> list[dict[str, Any]]:
    """For /agents/status — expose routing plan to the UI."""
    out = []
    for profile, spec in MODEL_PROFILES.items():
        out.append({
            "profile": profile,
            "strength": spec["strength"],
            "chain": models_for_profile(profile),
        })
    return out
