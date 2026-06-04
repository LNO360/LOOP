from .base import BaseAgent
from .company_context import COMPANY_CONTEXT_SHORT

class DocsAgent(BaseAgent):
    agent_type = "docs"
    system_prompt = (
        "You are the Docs Agent for LNO Technology.\n"
        "You write clear, well-structured documents, meeting notes, and operator-facing content.\n"
        "Use markdown. Match the company's tone: direct, technical, founder-mode.\n"
        "When writing operator-facing content: frame around intelligence layer, never billing software. "
        "Use loss aversion and peer references. Never attack WhatsApp/Excel.\n\n"
        f"## Company Context\n{COMPANY_CONTEXT_SHORT}"
    )

    def draft(self, outline: str) -> str:
        """Expand a brief outline or bullet points into a full document."""
        prompt = (
            "Expand this outline into a well-structured document. "
            "Use markdown. Return ONLY the document content, no explanation.\n\n"
            f"Outline:\n{outline}"
        )
        return self._chat([{"role": "user", "content": prompt}], max_tokens=2048)

    def summarize_channel(self, channel_name: str, messages: list[dict]) -> str:
        """Summarize a list of messages into meeting notes."""
        if not messages:
            return "No messages to summarize."

        msg_text = "\n".join([
            f"{m.get('author_name', 'Unknown')} [{m.get('created_at', '')[:10]}]: {m.get('content', '')}"
            for m in messages[-50:]  # last 50 messages
        ])

        prompt = (
            f"Summarize this conversation from #{channel_name} into meeting notes.\n"
            "Include: Key decisions, action items (as checkboxes), open questions.\n"
            "Use markdown. Return ONLY the meeting notes.\n\n"
            f"Conversation:\n{msg_text}"
        )
        return self._chat([{"role": "user", "content": prompt}], max_tokens=1024)

    def improve(self, content: str) -> str:
        """Improve existing document content."""
        prompt = (
            "Improve this document for clarity, structure, and completeness. "
            "Keep the same meaning but make it more professional and well-organized. "
            "Return ONLY the improved content in markdown.\n\n"
            f"Document:\n{content}"
        )
        return self._chat([{"role": "user", "content": prompt}], max_tokens=2048)
