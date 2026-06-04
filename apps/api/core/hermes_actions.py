"""Shared helpers for executing commands in the Hermes Docker container."""
import asyncio
import os

# Default matches `docker compose -p lno-os` → container `lno-os-hermes-1`.
HERMES_CONTAINER = os.getenv("HERMES_CONTAINER", "lno-os-hermes-1")


async def docker_exec(args: list[str], timeout: int = 300) -> asyncio.subprocess.Process:
    """Run a command in the Hermes Docker container."""
    return await asyncio.create_subprocess_exec(
        "docker", "exec", HERMES_CONTAINER, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )


async def register_agent_cron(slug: str, schedule: str) -> None:
    """Register a cron job for a user agent in the Hermes container."""
    prompt = (
        f"[CONTEXT] Use DEFAULT_WORKSPACE_ID env directly — do NOT call lno_list_workspaces. "
        f"Use the user/{slug} skill. Read team.handoff.{slug} if present."
    )
    name = f"user-{slug}"
    try:
        proc = await docker_exec(
            ["hermes", "cron", "create", schedule, prompt, "--name", name, "--profile", "cron"]
        )
        await proc.communicate()
    except Exception:
        pass  # Non-fatal — cron will be registered on next Hermes restart


async def remove_agent_cron(slug: str) -> None:
    """Remove the cron job for a user agent from the Hermes container."""
    name = f"user-{slug}"
    try:
        proc = await docker_exec(["hermes", "cron", "remove", name])
        await proc.communicate()
    except Exception:
        pass  # Non-fatal
