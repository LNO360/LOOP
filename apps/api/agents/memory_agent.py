"""
MemoryAgent — extracts learnable facts from AI conversations and formats them for context injection.
Facts are stored as workspace memories and recalled in future queries.
"""
from .base import BaseAgent
import json
import logging

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    agent_type = "memory"
    system_prompt = (
        "You are a memory extraction assistant for LNO OS.\n"
        "Your job is to identify facts worth remembering from conversations — "
        "team decisions, deadlines, preferences, company facts, and operational patterns.\n"
        "Be selective: extract only genuinely useful, durable facts. Skip pleasantries and generic statements.\n"
        "Keys use dot notation: team.person.fact, project.name.status, company.area.detail."
    )

    def extract(self, conversation: str, existing_keys: list[str]) -> list[dict]:
        """
        Extract learnable facts from a conversation.
        Returns list of {key, content, importance} — max 5 per call.
        existing_keys: already stored keys (to avoid near-duplicates).
        """
        existing_str = ", ".join(existing_keys[:50]) if existing_keys else "none"
        prompt = (
            "Extract up to 5 facts worth remembering from this conversation.\n"
            "Return ONLY a JSON array. Each item: {\"key\": \"dot.notation.key\", \"content\": \"fact string\", \"importance\": 1-5}\n"
            "importance: 5=critical deadline/decision, 4=important preference, 3=useful context, 2=minor detail, 1=trivial\n"
            f"Already stored keys (avoid near-duplicates): {existing_str}\n"
            "If nothing is worth storing, return []\n\n"
            f"Conversation:\n{conversation[:3000]}\n\n"
            "Return ONLY the JSON array, no explanation."
        )
        try:
            text = self._chat([{"role": "user", "content": prompt}], max_tokens=512)
            text = text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end > start:
                items = json.loads(text[start:end])
                valid = []
                for item in items[:5]:
                    if isinstance(item, dict) and "key" in item and "content" in item:
                        valid.append({
                            "key": str(item["key"])[:120],
                            "content": str(item["content"])[:500],
                            "importance": max(1, min(5, int(item.get("importance", 3)))),
                        })
                return valid
        except Exception as e:
            logger.warning(f"[memory] extract failed: {e}")
        return []

    def format_for_context(self, memories: list[dict]) -> str:
        """Format memories as a system prompt section."""
        if not memories:
            return ""
        lines = []
        for m in sorted(memories, key=lambda x: -x.get("importance", 3)):
            lines.append(f"- [{m['key']}] {m['content']}")
        return "## Workspace Memory (recalled facts)\n" + "\n".join(lines)
