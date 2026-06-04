"""
MCP tools for Hermes self-modification.
Hermes can call these during chat to update its own personality, skills, and config.

lno_read_soul_md       — read SOUL.md (Hermes's own personality)
lno_write_soul_md      — update SOUL.md
lno_list_skills        — list available skill files
lno_read_skill         — read a skill file
lno_create_skill       — create or replace a skill file (user agents too)
lno_delete_skill       — propose removing a skill file (human approval)
lno_list_agents        — list all user-created agents
lno_list_teams         — list all agent teams in a workspace with their members
lno_remove_team_member — remove an agent from a team
"""
import os
import re
import uuid as _uuid
from pathlib import Path
from sqlalchemy import select
from db.session import AsyncSessionLocal
from models.agent import UserAgent, AgentTeam, AgentTeamMember, TeamRole
from sqlalchemy.exc import IntegrityError
from mcp_server.server import mcp, agent_broadcast
from mcp_server.helpers import propose_destructive_action

# Paths inside the Hermes container (these are called from FastAPI but the
# file system paths are on the HOST where skills are mounted via volumes)
HERMES_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "apps/hermes-skills"
USER_SKILLS_DIR   = Path(__file__).parent.parent.parent.parent / "apps/user-agent-skills"

# SOUL.md is stored in the Hermes data volume — we keep a copy in hermes/SOUL.md
SOUL_MD_PATH = Path(__file__).parent.parent.parent.parent / "hermes/SOUL.md"


def _sm_slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:60]


def _sm_write_skill(slug: str, name: str, soul_md: str,
                    schedule: str | None, model: str | None) -> None:
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    header = f"---\nname: {name}\nslug: {slug}\n"
    if schedule:
        header += f"SCHEDULE: {schedule}\n"
    if model:
        header += f"MODEL: {model}\n"
    header += "---\n\n"
    (USER_SKILLS_DIR / f"{slug}.md").write_text(header + soul_md)


@mcp.tool()
async def lno_read_soul_md() -> dict:
    """
    Read Hermes's own SOUL.md — the core personality and operating instructions.
    Call this before trying to update your personality.
    Returns: {"content": "<markdown text>"}
    """
    try:
        content = SOUL_MD_PATH.read_text()
        return {"content": content, "path": str(SOUL_MD_PATH)}
    except FileNotFoundError:
        return {"content": "", "path": str(SOUL_MD_PATH), "error": "SOUL.md not found"}


@mcp.tool()
async def lno_write_soul_md(content: str) -> dict:
    """
    Update Hermes's SOUL.md — modify your own personality, operating principles,
    or workspace discovery protocol. Changes take effect on the next run.
    content: Full new content of SOUL.md (not a patch — full replacement).
    Returns: {"ok": true}
    """
    SOUL_MD_PATH.write_text(content)
    await agent_broadcast("", "lno_write_soul_md", "done",
                          f"SOUL.md updated ({len(content)} chars)")
    return {"ok": True, "chars_written": len(content)}


@mcp.tool()
async def lno_list_skills() -> dict:
    """
    List all available Hermes skill files.
    Returns built-in LNO skills and user-created agent skills.
    """
    skills = []

    if HERMES_SKILLS_DIR.exists():
        for f in sorted(HERMES_SKILLS_DIR.glob("*.md")):
            skills.append({
                "name": f.stem,
                "type": "builtin",
                "path": f"lno/{f.stem}",
                "size": f.stat().st_size,
            })

    if USER_SKILLS_DIR.exists():
        for f in sorted(USER_SKILLS_DIR.glob("*.md")):
            skills.append({
                "name": f.stem,
                "type": "user",
                "path": f"user/{f.stem}",
                "size": f.stat().st_size,
            })

    return {"skills": skills, "total": len(skills)}


@mcp.tool()
async def lno_read_skill(skill_path: str) -> dict:
    """
    Read a skill file by path (e.g. "lno/ops-monitor" or "user/my-agent").
    Returns: {"content": "<markdown>"}
    """
    if skill_path.startswith("user/"):
        slug = skill_path.removeprefix("user/")
        path = USER_SKILLS_DIR / f"{slug}.md"
    else:
        slug = skill_path.removeprefix("lno/")
        path = HERMES_SKILLS_DIR / f"{slug}.md"

    if not path.exists():
        return {"content": "", "error": f"Skill not found: {skill_path}"}

    return {"content": path.read_text(), "path": str(path)}


@mcp.tool()
async def lno_create_skill(
    name: str,
    content: str,
    skill_type: str = "user",
) -> dict:
    """
    Create or replace a skill file.
    name: slug-style name (e.g. "research-agent", "weekly-reviewer")
    content: Full skill markdown content — personality, instructions, schedule
    skill_type: "user" (default) or "builtin"
    Returns: {"ok": true, "path": "user/<name>"}
    """
    if skill_type == "builtin":
        path = HERMES_SKILLS_DIR / f"{name}.md"
    else:
        USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        path = USER_SKILLS_DIR / f"{name}.md"

    path.write_text(content)
    await agent_broadcast("", "lno_create_skill", "done",
                          f"Skill '{skill_type}/{name}' written ({len(content)} chars)")
    return {"ok": True, "path": f"{skill_type}/{name}"}


@mcp.tool()
async def lno_delete_skill(
    skill_path: str,
    workspace_id: str = "",
    run_id: str | None = None,
) -> dict:
    """
    Propose deleting a skill file. Requires human approval.
    Only user skills can be deleted (skill_path must start with "user/").
    skill_path: e.g. "user/my-agent"
    """
    if not skill_path.startswith("user/"):
        return {"proposed": False, "error": "Cannot delete built-in skills"}

    slug = skill_path.removeprefix("user/")
    path = USER_SKILLS_DIR / f"{slug}.md"
    if not path.exists():
        return {"proposed": False, "error": "Skill file not found"}

    ws = workspace_id or os.environ.get("DEFAULT_WORKSPACE_ID", "")
    if not ws:
        return {"proposed": False, "error": "workspace_id required (or set DEFAULT_WORKSPACE_ID)"}

    return await propose_destructive_action(
        ws,
        "delete_skill",
        {"skill_path": skill_path, "workspace_id": ws},
        run_id=run_id,
        summary=f"Skill deletion '{skill_path}' queued for human approval.",
    )


@mcp.tool()
async def lno_create_agent(
    workspace_id: str,
    name: str,
    soul_md: str,
    description: str = "",
    avatar_emoji: str = "🤖",
    schedule: str = "",
    model: str = "",
) -> dict:
    """
    Create a new custom Hermes agent and register it in the dashboard.
    Use this when the user asks you to create a new agent with a specific personality.

    workspace_id: Active workspace ID (from [CONTEXT] header).
    name: Display name for the agent (e.g. "Research Scout").
    soul_md: Full personality/instruction markdown for the agent.
    description: One-line description of what the agent does.
    avatar_emoji: Single emoji for the agent avatar (default 🤖).
    schedule: Cron schedule or human schedule (e.g. "every 2 hours", "0 9 * * 1").
              Leave empty for manual-only.
    model: OpenRouter model ID override (e.g. "deepseek/deepseek-v4-flash:free").
           Leave empty to use Hermes default.

    Returns: {"ok": true, "agent_id": "...", "slug": "..."}
    """
    slug = _sm_slugify(name)

    async with AsyncSessionLocal() as db:
        # Ensure unique slug within workspace
        existing = await db.execute(
            select(UserAgent).where(
                UserAgent.workspace_id == _uuid.UUID(workspace_id),
                UserAgent.slug == slug,
            )
        )
        if existing.scalar_one_or_none():
            slug = f"{slug}-{_uuid.uuid4().hex[:4]}"

        agent = UserAgent(
            workspace_id=_uuid.UUID(workspace_id),
            created_by=None,  # system-created by Hermes
            name=name,
            slug=slug,
            avatar_emoji=avatar_emoji,
            description=description or None,
            soul_md=soul_md,
            schedule=schedule or None,
            model=model or None,
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        agent_id = str(agent.id)

    # Write skill file
    _sm_write_skill(slug, name, soul_md, schedule or None, model or None)

    # Register cron in Hermes container (non-fatal if Hermes isn't running)
    if schedule:
        from core.hermes_actions import register_agent_cron
        try:
            await register_agent_cron(slug, schedule)
        except Exception:
            pass  # Non-fatal

    await agent_broadcast("", "lno_create_agent", "done",
                          f"Agent '{name}' created (slug: {slug})")

    return {"ok": True, "agent_id": agent_id, "slug": slug, "name": name}


@mcp.tool()
async def lno_list_agents(workspace_id: str) -> dict:
    """
    List all custom agents in a workspace.
    Use this to see what specialists exist before forming a team or delegating.
    Returns: {"agents": [{"agent_id", "name", "slug", "schedule", "description", "active"}]}
    """
    try:
        ws_uuid = _uuid.UUID(workspace_id)
    except ValueError:
        return {"ok": False, "error": f"Invalid workspace_id: {workspace_id}"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserAgent)
            .where(UserAgent.workspace_id == ws_uuid)
            .order_by(UserAgent.created_at.asc())
        )
        agents = result.scalars().all()
    return {"agents": [
        {
            "agent_id": str(a.id),
            "name": a.name,
            "slug": a.slug,
            "schedule": a.schedule,
            "description": a.description,
            "active": a.active,
        }
        for a in agents
    ], "total": len(agents)}


@mcp.tool()
async def lno_create_team(
    workspace_id: str,
    name: str,
    goal: str = "",
    description: str = "",
    coordinator_agent_id: str = "",
) -> dict:
    """
    Create a new agent team. Optionally assign a coordinator in the same call.
    workspace_id: Active workspace ID.
    name: Team name (e.g. "Finance Team").
    goal: What this team is working toward.
    coordinator_agent_id: agent_id to assign as coordinator (optional).
    Returns: {"ok": true, "team_id": "...", "name": "..."}
    """
    try:
        ws_uuid = _uuid.UUID(workspace_id)
    except ValueError:
        return {"ok": False, "error": f"Invalid workspace_id: {workspace_id}"}

    async with AsyncSessionLocal() as db:
        team = AgentTeam(
            workspace_id=ws_uuid,
            name=name,
            goal=goal or None,
            description=description or None,
        )
        db.add(team)
        await db.flush()
        if coordinator_agent_id:
            try:
                coord_uuid = _uuid.UUID(coordinator_agent_id)
            except ValueError:
                await db.rollback()
                return {"ok": False, "error": f"Invalid coordinator_agent_id: {coordinator_agent_id}"}
            coord = await db.get(UserAgent, coord_uuid)
            if not coord or coord.workspace_id != team.workspace_id:
                await db.rollback()
                return {"ok": False, "error": "Coordinator agent not found in workspace"}
            db.add(AgentTeamMember(
                team_id=team.id,
                agent_id=coord_uuid,
                team_role=TeamRole.coordinator,
            ))
        await db.commit()
        await db.refresh(team)
        team_id = str(team.id)
    await agent_broadcast("", "lno_create_team", "done", f"Team '{name}' created")
    return {"ok": True, "team_id": team_id, "name": name}


@mcp.tool()
async def lno_assign_agent_to_team(
    workspace_id: str,
    team_id: str,
    agent_id: str,
    team_role: str = "specialist",
) -> dict:
    """
    Assign an existing agent to a team.
    team_role: "coordinator" or "specialist" (default: specialist)
    Returns: {"ok": true} or {"ok": false, "error": "..."}
    """
    try:
        team_uuid = _uuid.UUID(team_id)
    except ValueError:
        return {"ok": False, "error": f"Invalid team_id: {team_id}"}
    try:
        agent_uuid = _uuid.UUID(agent_id)
    except ValueError:
        return {"ok": False, "error": f"Invalid agent_id: {agent_id}"}
    try:
        role = TeamRole(team_role)
    except ValueError:
        return {"ok": False, "error": f"Invalid team_role: '{team_role}'. Must be 'coordinator' or 'specialist'"}

    async with AsyncSessionLocal() as db:
        team = await db.get(AgentTeam, team_uuid)
        if not team or str(team.workspace_id) != workspace_id:
            return {"ok": False, "error": "Team not found in workspace"}
        agent = await db.get(UserAgent, agent_uuid)
        if not agent:
            return {"ok": False, "error": "Agent not found"}
        if agent.workspace_id != team.workspace_id:
            return {"ok": False, "error": "Agent belongs to a different workspace"}
        db.add(AgentTeamMember(
            team_id=team_uuid,
            agent_id=agent_uuid,
            team_role=role,
        ))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return {"ok": False, "error": "Agent already in this team"}
    await agent_broadcast("", "lno_assign_agent_to_team", "done",
                          f"Agent assigned to team with role={team_role}")
    return {"ok": True}


@mcp.tool()
async def lno_list_teams(workspace_id: str) -> dict:
    """
    List all agent teams in a workspace, with their members.
    Use this to see what teams exist before assigning agents or running a swarm.
    Returns: {"teams": [{"team_id", "name", "goal", "description", "members": [...]}]}
    """
    try:
        ws_uuid = _uuid.UUID(workspace_id)
    except ValueError:
        return {"ok": False, "error": f"Invalid workspace_id: {workspace_id}"}

    async with AsyncSessionLocal() as db:
        teams_result = await db.execute(
            select(AgentTeam)
            .where(AgentTeam.workspace_id == ws_uuid)
            .order_by(AgentTeam.created_at.asc())
        )
        teams = teams_result.scalars().all()

        result = []
        for team in teams:
            members_result = await db.execute(
                select(AgentTeamMember, UserAgent)
                .join(UserAgent, AgentTeamMember.agent_id == UserAgent.id)
                .where(AgentTeamMember.team_id == team.id)
            )
            members = [
                {
                    "agent_id": str(m.agent_id),
                    "agent_name": a.name,
                    "agent_slug": a.slug,
                    "team_role": m.team_role.value,
                }
                for m, a in members_result.all()
            ]
            result.append({
                "team_id": str(team.id),
                "name": team.name,
                "goal": team.goal,
                "description": team.description,
                "members": members,
            })

    return {"teams": result, "total": len(result)}


@mcp.tool()
async def lno_remove_team_member(
    workspace_id: str,
    team_id: str,
    agent_id: str,
) -> dict:
    """
    Remove an agent from a team.
    workspace_id: Active workspace ID.
    team_id: UUID of the team.
    agent_id: UUID of the agent to remove.
    Returns: {"ok": true} or {"ok": false, "error": "..."}
    """
    try:
        ws_uuid = _uuid.UUID(workspace_id)
        team_uuid = _uuid.UUID(team_id)
        agent_uuid = _uuid.UUID(agent_id)
    except ValueError as e:
        return {"ok": False, "error": f"Invalid UUID: {e}"}

    async with AsyncSessionLocal() as db:
        team = await db.get(AgentTeam, team_uuid)
        if not team or team.workspace_id != ws_uuid:
            return {"ok": False, "error": "Team not found in workspace"}

        member_result = await db.execute(
            select(AgentTeamMember).where(
                AgentTeamMember.team_id == team_uuid,
                AgentTeamMember.agent_id == agent_uuid,
            )
        )
        member = member_result.scalar_one_or_none()
        if not member:
            return {"ok": False, "error": "Agent is not a member of this team"}

        await db.delete(member)
        await db.commit()

    return {"ok": True}
