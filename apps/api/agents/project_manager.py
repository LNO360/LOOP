from .base import BaseAgent
from .company_context import COMPANY_CONTEXT_SHORT
import json

class ProjectManagerAgent(BaseAgent):
    agent_type = "project_manager"
    system_prompt = (
        "You are the Project Manager Agent for LNO Technology.\n"
        "You assess project health, identify blockers, and give direct actionable recommendations "
        "grounded in the company's real priorities and team structure.\n"
        "Key facts: OLT monitoring deadline is June 30 (Shaan only). "
        "Fibre mapping is July. PDOA registration is the next milestone.\n"
        "Be direct. Use bullet points. Prioritize by business impact.\n\n"
        f"## Company Context\n{COMPANY_CONTEXT_SHORT}"
    )

    def analyze(self, project_name: str, tasks: list[dict]) -> dict:
        task_summary = "\n".join([
            f"- [{t.get('status','?')}] [{t.get('priority','?')}] {t.get('title','?')}"
            + (f" (due: {t.get('due_date')})" if t.get('due_date') else "")
            for t in tasks
        ]) or "No tasks yet."

        prompt = (
            f"Project: {project_name}\n\n"
            f"Tasks:\n{task_summary}\n\n"
            "Analyze this project. Return a JSON object with:\n"
            '{"health": "on_track"|"at_risk"|"blocked", '
            '"summary": "2-3 sentence overview", '
            '"blockers": ["list of blockers"], '
            '"suggestions": ["list of 2-3 recommendations"]}\n\n'
            "Respond with ONLY the JSON object."
        )
        try:
            text = self._chat([{"role": "user", "content": prompt}], max_tokens=768)
            text = text.strip()
            start, end = text.find("{"), text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass
        return {
            "health": "unknown",
            "summary": "Analysis unavailable.",
            "blockers": [],
            "suggestions": [],
        }
