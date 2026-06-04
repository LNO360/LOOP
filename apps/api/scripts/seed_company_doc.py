"""
Run once to seed the LNO Technology company context as a searchable doc in all workspaces.
Usage: cd apps/api && source .venv/bin/activate && python scripts/seed_company_doc.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from db.session import AsyncSessionLocal
from models import Workspace, WorkspaceMember, Document
from agents.company_context import COMPANY_CONTEXT
import uuid

TITLE = "LNO Technology — Company Context"

async def seed():
    async with AsyncSessionLocal() as db:
        ws_result = await db.execute(select(Workspace))
        workspaces = ws_result.scalars().all()
        if not workspaces:
            print("No workspaces found. Start the app and create a workspace first.")
            return

        for ws in workspaces:
            # Check if doc already exists
            existing = await db.execute(
                select(Document).where(
                    Document.workspace_id == ws.id,
                    Document.title == TITLE,
                )
            )
            if existing.scalar_one_or_none():
                print(f"[{ws.name}] Company doc already exists — skipping.")
                continue

            # Get first member as author
            m_result = await db.execute(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id).limit(1)
            )
            member = m_result.scalar_one_or_none()
            if not member:
                print(f"[{ws.name}] No members — skipping.")
                continue

            doc = Document(
                workspace_id=ws.id,
                title=TITLE,
                content=COMPANY_CONTEXT,  # plain text, Knowledge Agent searches this
                author_id=member.user_id,
            )
            db.add(doc)
            print(f"[{ws.name}] ✅ Seeded company context doc.")

        await db.commit()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(seed())
