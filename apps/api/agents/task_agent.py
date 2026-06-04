from .base import BaseAgent
import json

class TaskAgent(BaseAgent):
    agent_type = "task"
    system_prompt = (
        "You are a task extraction agent for LNO OS. "
        "Your only job is to identify clear, actionable tasks from messages. "
        "Be strict — only extract real action items, not general statements. "
        "Infer priority from urgency language: 'urgent/asap/critical' → urgent, 'important/soon' → high, default → medium."
    )

    def extract(self, message: str) -> list[dict]:
        prompt = (
            "Extract actionable tasks from this message. Return ONLY a JSON array.\n"
            'Each task: {"title": string (max 80 chars), "description": string|null, "priority": "low"|"medium"|"high"|"urgent"}\n'
            "Return [] if no clear tasks exist.\n\n"
            f"Message: {message}\n\n"
            "Respond with ONLY the JSON array."
        )
        try:
            text = self._chat([{"role": "user", "content": prompt}], max_tokens=512)
            text = text.strip()
            start, end = text.find("["), text.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])[:5]
        except Exception:
            pass
        return []
