from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
import uuid
from db.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    # Contact & Telegram
    phone = Column(String(32), nullable=True)
    telegram_username = Column(String(64), nullable=True)   # @handle without @
    telegram_user_id  = Column(String(32), nullable=True, index=True)  # set when user /connects bot
