"""
AiConversation / AiChatMessage — persistent 1:1 AI chat (Claude-style history).
ChannelAgentSession — maps (channel, agent) → a Hermes ACP session for in-channel agents.

Each conversation is backed by a Hermes ACP session (hermes_session_id); we resume it
to keep server-side memory instead of re-sending history from the client.
"""
from sqlalchemy import Column, String, ForeignKey, Text, DateTime, func, UniqueConstraint, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from db.base import Base, TimestampMixin


class AiConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    hermes_session_id = Column(String, nullable=True)   # ACP sessionId; set after first prompt
    agent_slug = Column(String(80), nullable=True)      # if chatting as a specific agent
    title = Column(String, nullable=True)               # auto-filled from session_info_update
    archived_at = Column(DateTime(timezone=True), nullable=True)


class AiChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)               # "user" | "assistant"
    content = Column(Text, nullable=False, default="")
    tool_calls = Column(JSONB, nullable=True)           # [{id,name,status,detail}]
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChannelAgentSession(Base):
    """One Hermes ACP session per (channel, agent) so an agent keeps context across mentions."""
    __tablename__ = "channel_agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_slug = Column(String(80), nullable=False)
    hermes_session_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("channel_id", "agent_slug", name="uq_channel_agent"),
    )


class HermesChatSession(Base):
    """Rolling conversation memory for direct Hermes chat (one per workspace+user+agent)."""
    __tablename__ = "hermes_chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_slug = Column(String(80), nullable=True)          # NULL = base Hermes
    summary = Column(Text, nullable=True)                   # rolling compressed summary
    raw_tail = Column(JSONB, nullable=True)                 # last 3 full [{user, hermes}] exchanges
    message_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", "agent_slug", name="uq_hermes_chat_session"),
    )
