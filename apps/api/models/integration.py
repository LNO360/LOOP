"""WorkspaceIntegration — stores OAuth tokens and API keys per workspace per provider."""
from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from db.base import Base


class WorkspaceIntegration(Base):
    __tablename__ = "workspace_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    provider = Column(String(32), nullable=False)        # 'google' | 'brave'

    # Encrypted tokens (Fernet encrypted, base64 encoded)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    scopes = Column(Text, nullable=True)                # space-separated
    account_email = Column(String(255), nullable=True)  # display name
    api_key = Column(Text, nullable=True)               # for non-OAuth providers (Brave)

    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
