from sqlalchemy import Column, String, ForeignKey, Enum as SAEnum, DateTime, func, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid, enum
from db.base import Base, TimestampMixin

class ChannelType(str, enum.Enum):
    public = "public"
    private = "private"
    dm = "dm"

class Channel(Base, TimestampMixin):
    __tablename__ = "channels"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(SAEnum(ChannelType), default=ChannelType.public, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

class ChannelMember(Base):
    __tablename__ = "channel_members"
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    has_attachments = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    edited_at = Column(DateTime(timezone=True), nullable=True)   # set when content is edited


class MessageReaction(Base):
    """Per-user emoji reactions on messages."""
    __tablename__ = "message_reactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String(16), nullable=False)          # e.g. "👍", "❤️"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_message_reaction"),
    )


class PinnedMessage(Base):
    """Messages pinned in a channel."""
    __tablename__ = "pinned_messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    pinned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pinned_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_pinned_message"),
    )
