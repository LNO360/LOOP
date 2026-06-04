"""
Backfill embeddings for existing workspace_memories rows.

After the pgvector migration (f5a6b7c8d9e0), existing memory rows have NULL
embeddings, so they only match the keyword arm of hybrid search until re-written.
This script embeds the rows that are missing an embedding so they join the vector
arm too.

Embeddings are best-effort: rows that fail to embed are left NULL and reported,
never block the rest. Safe to re-run — it only touches rows where embedding IS NULL
(unless --all is passed to re-embed everything, e.g. after a model change).

Usage:
  cd apps/api && source .venv/bin/activate
  python scripts/backfill_memory_embeddings.py --dry-run         # count what would change
  python scripts/backfill_memory_embeddings.py --execute         # embed rows missing an embedding
  python scripts/backfill_memory_embeddings.py --execute --all   # re-embed ALL rows (model change)
  python scripts/backfill_memory_embeddings.py --execute --workspace <uuid>   # scope to one workspace
"""
import argparse
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from core.config import settings
from core.embeddings import aembed_text, memory_embedding_input
from db.session import AsyncSessionLocal
from models.other import WorkspaceMemory

BATCH_COMMIT = 25  # commit every N rows so a long run makes incremental progress


async def main(execute: bool, do_all: bool, workspace_id: str | None) -> None:
    if not settings.embedding_enabled or not settings.openrouter_api_key:
        print(
            "✗ Embeddings are disabled or OPENROUTER_API_KEY is unset "
            f"(embedding_enabled={settings.embedding_enabled}). Nothing to do."
        )
        return

    print(f"→ Model: {settings.embedding_model} (dim {settings.embedding_dim})")
    print(f"→ Mode:  {'re-embed ALL' if do_all else 'fill missing only'}"
          f"{' · workspace=' + workspace_id if workspace_id else ''}"
          f"{'' if execute else '  [DRY RUN]'}")

    async with AsyncSessionLocal() as db:
        stmt = select(WorkspaceMemory)
        if not do_all:
            stmt = stmt.where(WorkspaceMemory.embedding.is_(None))
        if workspace_id:
            stmt = stmt.where(WorkspaceMemory.workspace_id == uuid.UUID(workspace_id))
        rows = (await db.execute(stmt)).scalars().all()

        total = len(rows)
        print(f"→ {total} row(s) to process.")
        if not execute:
            for m in rows[:20]:
                print(f"    would embed: [{m.key}]")
            if total > 20:
                print(f"    … and {total - 20} more")
            print("\nDry run — no changes written. Re-run with --execute.")
            return

        done = 0
        failed = 0
        for i, m in enumerate(rows, 1):
            vec = await aembed_text(memory_embedding_input(m.key, m.content))
            if vec is None:
                failed += 1
            else:
                m.embedding = vec
                done += 1
            if i % BATCH_COMMIT == 0:
                await db.commit()
                print(f"  … {i}/{total} (embedded {done}, failed {failed})")
        await db.commit()

    print(f"\n✓ Done. Embedded {done}, failed {failed}, total {total}.")
    if failed:
        print("  Failed rows were left NULL (still keyword-searchable). Re-run to retry.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill workspace_memories embeddings")
    parser.add_argument("--execute", action="store_true", help="Write embeddings (default: dry run)")
    parser.add_argument("--dry-run", action="store_true", help="Count only (default)")
    parser.add_argument("--all", action="store_true", help="Re-embed ALL rows, not just missing ones")
    parser.add_argument("--workspace", default=None, help="Scope to a single workspace UUID")
    args = parser.parse_args()
    asyncio.run(main(execute=args.execute, do_all=args.all, workspace_id=args.workspace))
