from .base import BaseAgent
from .company_context import COMPANY_CONTEXT

class KnowledgeAgent(BaseAgent):
    agent_type = "knowledge"
    system_prompt = (
        "You are the Knowledge Agent for LNO Technology's internal workspace.\n"
        "You answer questions using workspace messages and documents as your primary source, "
        "and use company context below as background knowledge.\n"
        "Always cite your sources (e.g. 'Based on a message from Shaan on Jan 5...'). "
        "If workspace context is insufficient, answer from company context and say so. "
        "Be concise. Use bullet points for lists.\n\n"
        f"## Company Context\n{COMPANY_CONTEXT}"
    )

    def answer(self, question: str, context_messages: list[dict], context_docs: list[dict]) -> dict:
        context_parts = []

        if context_messages:
            msg_ctx = "\n".join([
                f"[Message from {m.get('author_name','?')} on {m.get('created_at','')[:10]}]: {m.get('content','')}"
                for m in context_messages[:20]
            ])
            context_parts.append(f"Recent messages:\n{msg_ctx}")

        if context_docs:
            doc_ctx = "\n".join([
                f"[Doc: {d.get('title','?')}]: {str(d.get('content',''))[:500]}"
                for d in context_docs[:5]
            ])
            context_parts.append(f"Documents:\n{doc_ctx}")

        context_str = "\n\n".join(context_parts) if context_parts else "No context available."

        prompt = (
            f"Context from workspace:\n{context_str}\n\n"
            f"Question: {question}\n\n"
            "Answer based on the context above. Cite sources. If context is insufficient, say so."
        )
        answer = self._chat([{"role": "user", "content": prompt}], max_tokens=768)
        return {"answer": answer, "sources_used": len(context_messages) + len(context_docs)}
