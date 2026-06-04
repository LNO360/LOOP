from core.model_router import (
    chat_with_fallback,
    profile_for_agent_type,
    models_for_profile,
)
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class BaseAgent:
    agent_type: str
    system_prompt: str

    def _profile(self) -> str:
        return profile_for_agent_type(self.agent_type)

    def _primary_model(self) -> str:
        chain = models_for_profile(self._profile())
        return chain[0] if chain else (settings.openrouter_model or "openrouter/free")

    def _chat(self, messages: list[dict], max_tokens: int = 1024) -> str:
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")

        response, _model_used = chat_with_fallback(
            profile=self._profile(),
            messages=[{"role": "system", "content": self.system_prompt}, *messages],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
