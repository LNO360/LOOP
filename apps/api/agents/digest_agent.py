from .base import BaseAgent
from .company_context import COMPANY_CONTEXT_SHORT
from datetime import date

class DigestAgent(BaseAgent):
    agent_type = "digest"
    system_prompt = (
        "You are the Daily Digest Agent for LNO Technology.\n"
        "You create concise, focused morning digests for the founding team.\n"
        "Format: date header, what was done, what's due today, blockers, one motivating line.\n"
        "Keep it under 200 words. Use markdown. Be direct — this is a startup, every day counts.\n"
        "Team: Ashik (CEO), Shaan (OLT/backend - June 30 deadline), Vishag (frontend), "
        "Christine (frontend/testing), Avinash (ops/marketing), Alan (legal).\n\n"
        f"## Company Context\n{COMPANY_CONTEXT_SHORT}"
    )

    def generate(
        self,
        workspace_name: str,
        overdue_tasks: list[dict],
        due_today: list[dict],
        recent_messages_count: int,
        completed_yesterday: list[dict],
    ) -> str:
        today_str = date.today().strftime("%A, %B %d")

        sections = []
        if completed_yesterday:
            completed_titles = ", ".join(t.get("title","?") for t in completed_yesterday[:3])
            sections.append(f"**Completed yesterday:** {completed_titles}")
        if due_today:
            due_titles = "\n".join(f"  - {t.get('title','?')} ({t.get('assignee_name','unassigned')})" for t in due_today[:5])
            sections.append(f"**Due today:**\n{due_titles}")
        if overdue_tasks:
            overdue_titles = "\n".join(f"  - ⚠️ {t.get('title','?')} ({t.get('assignee_name','unassigned')})" for t in overdue_tasks[:3])
            sections.append(f"**Overdue:**\n{overdue_titles}")

        workspace_ctx = "\n".join(sections) if sections else "No urgent items today."

        prompt = (
            f"Create a morning digest for {workspace_name} on {today_str}.\n\n"
            f"Workspace snapshot:\n{workspace_ctx}\n"
            f"Messages sent yesterday: {recent_messages_count}\n\n"
            "Write the digest. Start with '🌅 Good morning' and the date."
        )
        return self._chat([{"role": "user", "content": prompt}], max_tokens=512)
