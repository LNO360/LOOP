"""
Delete all workspaces except one (by id or name).

Usage (local):
  cd apps/api && source .venv/bin/activate
  python scripts/cleanup_workspaces.py --list
  python scripts/cleanup_workspaces.py --dry-run
  python scripts/cleanup_workspaces.py --execute

Usage (production VPS):
  docker exec -it lno-os-api-1 python scripts/cleanup_workspaces.py --list
  docker exec -it lno-os-api-1 python scripts/cleanup_workspaces.py --dry-run
  docker exec -it lno-os-api-1 python scripts/cleanup_workspaces.py --execute

Default keep: your-workspace-name (your-workspace-uuid)
"""
import argparse
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select, update, text
from sqlalchemy.exc import ProgrammingError
from db.session import AsyncSessionLocal
from models import (
    Workspace,
    WorkspaceMember,
    Channel,
    ChannelMember,
    Message,
    MessageReaction,
    PinnedMessage,
    Task,
    Project,
    Document,
    File,
    Event,
    TaskComment,
    WorkspaceMemory,
    Notification,
)
from models.agent import (
    AgentRun,
    ProposedAction,
    UserAgent,
    AgentTeam,
    AgentTeamMember,
)
from models.ai_chat import AiConversation, ChannelAgentSession
from models.boardroom import BoardroomSession, BoardroomAgent
from models.finance import (
    FinanceInvoice,
    FinanceTransaction,
    FinanceCategory,
    FinanceAccount,
    FinanceSnapshot,
    WorkspaceFinanceSettings,
)
from models.invite import WorkspaceInvite
from models.integration import WorkspaceIntegration
from models.github_webhook import GithubWebhookEvent, GithubAppInstallation

DEFAULT_KEEP_ID = ""  # Set to your workspace UUID
DEFAULT_KEEP_NAME = "LNO Technologies"


async def load_public_tables(db) -> set[str]:
    """Tables present in DB (prod may lag migrations — e.g. no finance_* yet)."""
    rows = await db.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    return {r[0] for r in rows.all()}


def _has(tables: set[str], model) -> bool:
    return model.__tablename__ in tables


async def _delete_ws(db, tables: set[str], model, ws_id: uuid.UUID) -> None:
    if _has(tables, model):
        await db.execute(delete(model).where(model.workspace_id == ws_id))


async def delete_workspace(db, ws_id: uuid.UUID, tables: set[str]) -> None:
    """Delete one workspace and dependent rows (FK-safe order)."""
    channel_ids = (
        await db.execute(select(Channel.id).where(Channel.workspace_id == ws_id))
    ).scalars().all()

    message_ids: list[uuid.UUID] = []
    if channel_ids:
        message_ids = list(
            (
                await db.execute(
                    select(Message.id).where(Message.channel_id.in_(channel_ids))
                )
            ).scalars().all()
        )

    if message_ids:
        await db.execute(delete(PinnedMessage).where(PinnedMessage.message_id.in_(message_ids)))
        await db.execute(
            delete(MessageReaction).where(MessageReaction.message_id.in_(message_ids))
        )
        await db.execute(
            delete(Notification).where(
                Notification.entity_id.in_(message_ids + list(channel_ids))
            )
        )
        await db.execute(delete(File).where(File.message_id.in_(message_ids)))

    await db.execute(
        update(Task)
        .where(Task.workspace_id == ws_id)
        .values(source_message_id=None)
    )

    task_ids = list(
        (await db.execute(select(Task.id).where(Task.workspace_id == ws_id))).scalars().all()
    )
    if task_ids:
        await db.execute(delete(TaskComment).where(TaskComment.task_id.in_(task_ids)))
        await db.execute(
            delete(Notification).where(Notification.entity_id.in_(task_ids))
        )

    # Boardroom (optional migration)
    if _has(tables, BoardroomSession):
        session_ids = list(
            (
                await db.execute(
                    select(BoardroomSession.id).where(BoardroomSession.workspace_id == ws_id)
                )
            ).scalars().all()
        )
        if session_ids and _has(tables, BoardroomAgent):
            await db.execute(
                delete(BoardroomAgent).where(BoardroomAgent.session_id.in_(session_ids))
            )
            await db.execute(
                delete(BoardroomSession).where(BoardroomSession.id.in_(session_ids))
            )

    # Finance (optional migration)
    if _has(tables, FinanceInvoice):
        await db.execute(delete(FinanceInvoice).where(FinanceInvoice.workspace_id == ws_id))
    if _has(tables, FinanceTransaction):
        await db.execute(
            delete(FinanceTransaction).where(FinanceTransaction.workspace_id == ws_id)
        )
    if _has(tables, FinanceCategory):
        await db.execute(delete(FinanceCategory).where(FinanceCategory.workspace_id == ws_id))
    if _has(tables, FinanceAccount):
        await db.execute(delete(FinanceAccount).where(FinanceAccount.workspace_id == ws_id))
    if _has(tables, FinanceSnapshot):
        await db.execute(delete(FinanceSnapshot).where(FinanceSnapshot.workspace_id == ws_id))
    if _has(tables, WorkspaceFinanceSettings):
        await db.execute(
            delete(WorkspaceFinanceSettings).where(
                WorkspaceFinanceSettings.workspace_id == ws_id
            )
        )

    await db.execute(delete(ProposedAction).where(ProposedAction.workspace_id == ws_id))
    await db.execute(delete(AgentRun).where(AgentRun.workspace_id == ws_id))

    if _has(tables, AgentTeam):
        team_ids = list(
            (
                await db.execute(
                    select(AgentTeam.id).where(AgentTeam.workspace_id == ws_id)
                )
            ).scalars().all()
        )
        if team_ids and _has(tables, AgentTeamMember):
            await db.execute(
                delete(AgentTeamMember).where(AgentTeamMember.team_id.in_(team_ids))
            )
            await db.execute(delete(AgentTeam).where(AgentTeam.id.in_(team_ids)))

    await _delete_ws(db, tables, AiConversation, ws_id)
    await _delete_ws(db, tables, WorkspaceInvite, ws_id)
    await _delete_ws(db, tables, WorkspaceIntegration, ws_id)
    if _has(tables, GithubAppInstallation):
        await db.execute(
            delete(GithubAppInstallation).where(GithubAppInstallation.workspace_id == ws_id)
        )
    if _has(tables, GithubWebhookEvent):
        await db.execute(
            update(GithubWebhookEvent)
            .where(GithubWebhookEvent.workspace_id == ws_id)
            .values(workspace_id=None)
        )

    await db.execute(
        update(Document)
        .where(Document.workspace_id == ws_id)
        .values(linked_channel_id=None, linked_task_id=None)
    )

    await db.execute(delete(Task).where(Task.workspace_id == ws_id))
    await db.execute(delete(Project).where(Project.workspace_id == ws_id))
    await db.execute(delete(Document).where(Document.workspace_id == ws_id))

    if channel_ids and _has(tables, ChannelAgentSession):
        await db.execute(
            delete(ChannelAgentSession).where(ChannelAgentSession.channel_id.in_(channel_ids))
        )
        await db.execute(delete(Message).where(Message.channel_id.in_(channel_ids)))
        await db.execute(delete(ChannelMember).where(ChannelMember.channel_id.in_(channel_ids)))
        await db.execute(delete(Channel).where(Channel.id.in_(channel_ids)))

    await db.execute(delete(File).where(File.workspace_id == ws_id))
    await db.execute(delete(WorkspaceMemory).where(WorkspaceMemory.workspace_id == ws_id))
    await db.execute(delete(Event).where(Event.workspace_id == ws_id))
    await db.execute(delete(WorkspaceMember).where(WorkspaceMember.workspace_id == ws_id))
    await db.execute(delete(UserAgent).where(UserAgent.workspace_id == ws_id))
    await db.execute(delete(Workspace).where(Workspace.id == ws_id))


async def list_workspaces() -> None:
    async with AsyncSessionLocal() as db:
        all_ws = (await db.execute(select(Workspace).order_by(Workspace.name))).scalars().all()
        print(f"Workspaces ({len(all_ws)}):")
        for w in all_ws:
            members = (
                await db.execute(
                    select(WorkspaceMember).where(WorkspaceMember.workspace_id == w.id)
                )
            ).scalars().all()
            print(f"  {w.name!r}  {w.id}  members={len(members)}  slug={w.slug}")


async def main(keep_id: str, execute: bool) -> None:
    keep_uuid = uuid.UUID(keep_id)
    async with AsyncSessionLocal() as db:
        all_ws = (await db.execute(select(Workspace).order_by(Workspace.name))).scalars().all()
        keep = next((w for w in all_ws if w.id == keep_uuid), None)
        if not keep:
            by_name = next(
                (w for w in all_ws if w.name.strip().lower() == DEFAULT_KEEP_NAME.lower()),
                None,
            )
            if by_name:
                keep = by_name
                keep_uuid = by_name.id
                print(f"Resolved keep workspace by name: {keep.name} ({keep.id})")
            else:
                print(f"ERROR: keep workspace {keep_id} not found.")
                return

        to_delete = [w for w in all_ws if w.id != keep_uuid]
        print(f"Keeping: {keep.name} ({keep.id})")
        print(f"Will delete {len(to_delete)} workspace(s):")
        for w in to_delete:
            print(f"  - {w.name} ({w.id})")

        if not execute:
            print("\nDry run only. Re-run with --execute to apply.")
            return

        confirm = os.getenv("CLEANUP_CONFIRM", "")
        if confirm != "yes-delete-workspaces":
            print(
                "\nSet CLEANUP_CONFIRM=yes-delete-workspaces to proceed with --execute "
                "(safety guard for production)."
            )
            return

        existing_tables = await load_public_tables(db)
        skipped = [
            t
            for t in (
                "finance_invoices",
                "boardroom_sessions",
                "ai_conversations",
                "workspace_invites",
            )
            if t not in existing_tables
        ]
        if skipped:
            print(f"Note: skipping optional tables not in DB: {', '.join(skipped)}")

        deleted = 0
        errors = 0
        for w in to_delete:
            print(f"Deleting {w.name}...")
            try:
                await delete_workspace(db, w.id, existing_tables)
                await db.commit()
                deleted += 1
            except ProgrammingError as e:
                await db.rollback()
                errors += 1
                print(f"  FAILED: {e}")

        remaining = (await db.execute(select(Workspace))).scalars().all()
        print(f"\nDone. Deleted {deleted}, failed {errors}, {len(remaining)} workspace(s) remain.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete all workspaces except one")
    parser.add_argument(
        "--keep-id",
        default=os.getenv("KEEP_WORKSPACE_ID", DEFAULT_KEEP_ID),
        help="Workspace UUID to keep",
    )
    parser.add_argument("--list", action="store_true", help="List workspaces and exit")
    parser.add_argument("--execute", action="store_true", help="Actually delete (default: dry run)")
    args = parser.parse_args()
    if args.list:
        asyncio.run(list_workspaces())
    else:
        asyncio.run(main(args.keep_id, execute=args.execute))
