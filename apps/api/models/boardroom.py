from sqlalchemy import Column, String, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from db.base import Base, TimestampMixin


class BoardroomSession(Base, TimestampMixin):
    __tablename__ = "boardroom_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic = Column(Text, nullable=False)
    status = Column(String(20), default="setup", nullable=False)
    rounds_config = Column(Integer, default=2, nullable=False)
    # round_robin | structured | dynamic
    debate_mode = Column(String(20), default="round_robin", nullable=False)
    # Tool names every agent inherits unless they have a per-agent override.
    default_tools = Column(JSONB, default=list, nullable=False)
    transcript = Column(JSONB, default=list)
    output = Column(JSONB, nullable=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class BoardroomAgent(Base):
    __tablename__ = "boardroom_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("boardroom_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)
    emoji = Column(String(8), default="🤖", nullable=False)
    persona_type = Column(String(20), nullable=False)  # builtin | custom | adhoc
    agent_ref = Column(UUID(as_uuid=True), nullable=True)  # no FK: adhoc agents have no user_agents row
    system_prompt = Column(Text, nullable=False)
    turn_order = Column(Integer, default=0, nullable=False)
    # Per-agent tool override; NULL = inherit session.default_tools.
    tools = Column(JSONB, nullable=True)
