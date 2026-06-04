"""
AgentRun      — every autonomous Hermes session run is recorded here.
ProposedAction — write operations Hermes wants to perform; humans approve/reject.
UserAgent     — custom agents created by workspace members with their own personality.
"""
from sqlalchemy import Column, String, ForeignKey, Text, DateTime, Boolean, Integer, func, UniqueConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid, enum
from db.base import Base, TimestampMixin


class AgentRun(Base):
    """One row per autonomous agent execution (cron tick, event trigger, @hermes mention)."""
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)
    trigger_type = Column(String, nullable=False)
    trigger_payload = Column(JSONB, default={})
    agent_name = Column(String, nullable=False)
    status = Column(String, default="running", nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    tool_calls_json = Column(JSONB, default=[])
    result_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)


class ProposedAction(Base):
    """
    A write operation Hermes wants to perform, gated on human approval.

    Flow: Hermes calls an MCP write tool → we create a ProposedAction (status=pending)
          → return {"proposed": true} to Hermes
          → human sees it in settings UI → approves/rejects
          → approved: our API executes the actual operation → status=executed
    """
    __tablename__ = "proposed_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)
    action_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    risk_level = Column(String, default="medium")
    status = Column(String, default="pending", nullable=False, index=True)
    proposed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    execution_result = Column(JSONB, nullable=True)


class UserAgent(Base):
    """
    A custom agent created by a workspace member.
    Each agent has its own personality (soul_md), optional schedule, and model.

    Hermes loads the skill file at /user-agent-skills/{slug}.md and runs it.
    """
    __tablename__ = "user_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    name = Column(String(120), nullable=False)
    slug = Column(String(80), nullable=False)
    avatar_emoji = Column(String(8), default="🤖", nullable=False)
    description = Column(Text, nullable=True)

    # Full personality/instruction set (written as skill file to Hermes)
    soul_md = Column(Text, nullable=False)

    # Cron schedule — e.g. "every 2 hours" or "0 9 * * 1"
    schedule = Column(String(100), nullable=True)

    # Model override — e.g. "anthropic/claude-opus-4"
    model = Column(String(120), nullable=True)

    # Comma-separated extra toolsets to enable for this agent
    extra_skills = Column(Text, nullable=True)

    active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AgentTeam(Base, TimestampMixin):
    __tablename__ = "agent_teams"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    goal = Column(Text, nullable=True)


class TeamRole(str, enum.Enum):
    coordinator = "coordinator"
    specialist = "specialist"


class AgentTeamMember(Base):
    __tablename__ = "agent_team_members"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("agent_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("user_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    team_role = Column(SAEnum(TeamRole), nullable=False, default=TeamRole.specialist)
    __table_args__ = (UniqueConstraint("team_id", "agent_id", name="uq_team_member"),)
