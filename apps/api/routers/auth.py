from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models import User, Workspace, WorkspaceMember, MemberRole
from pydantic import BaseModel, EmailStr
from typing import Optional
import bcrypt as _bcrypt
from jose import jwt
from core.config import settings
from core.auth import get_current_user
import uuid, datetime, secrets, redis.asyncio as aioredis, hashlib, hmac
from time import time

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Redis (lazy singleton) ─────────────────────────────────────────────────
_redis: Optional[aioredis.Redis] = None

async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


# ── Helpers ────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")

def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def make_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30),
    }
    return jwt.encode(payload, settings.better_auth_secret, algorithm="HS256")


# ── Schemas ────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    workspace_name: Optional[str] = None   # None → member joining via invite

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    telegram_username: Optional[str] = None   # @handle or plain handle

class TelegramWidgetData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


# ── Auth endpoints ─────────────────────────────────────────────────────────

@router.post("/signup")
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(email=body.email, name=body.name, hashed_password=_hash_password(body.password))
    db.add(user)
    await db.flush()

    workspace_id = None
    if body.workspace_name:
        slug = body.workspace_name.lower().replace(" ", "-") + "-" + str(uuid.uuid4())[:8]
        workspace = Workspace(name=body.workspace_name, slug=slug, owner_id=user.id, emoji="🚀")
        db.add(workspace)
        await db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=MemberRole.admin))
        workspace_id = str(workspace.id)

    await db.commit()
    return {"token": make_token(str(user.id)), "user_id": str(user.id), "workspace_id": workspace_id}


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not _verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    ws_result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(1)
    )
    member = ws_result.scalar_one_or_none()
    workspace_id = str(member.workspace_id) if member else None
    return {"token": make_token(str(user.id)), "user_id": str(user.id), "workspace_id": workspace_id}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id":                 str(current_user.id),
        "email":              current_user.email,
        "name":               current_user.name,
        "avatar_url":         current_user.avatar_url,
        "phone":              current_user.phone,
        "telegram_username":  current_user.telegram_username,
        "telegram_connected": current_user.telegram_user_id is not None,
    }


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update name, phone, and/or Telegram username."""
    if body.name is not None:
        current_user.name = body.name.strip()
    if body.phone is not None:
        current_user.phone = body.phone.strip() or None
    if body.telegram_username is not None:
        handle = body.telegram_username.strip().lstrip("@") or None
        current_user.telegram_username = handle
    await db.commit()
    return {
        "id":                 str(current_user.id),
        "name":               current_user.name,
        "phone":              current_user.phone,
        "telegram_username":  current_user.telegram_username,
        "telegram_connected": current_user.telegram_user_id is not None,
    }


# ── Telegram connect OTP ───────────────────────────────────────────────────

@router.post("/telegram-connect/init")
async def telegram_connect_init(
    current_user: User = Depends(get_current_user),
):
    """
    Generate a short-lived 6-char OTP.
    The user sends /connect <CODE> to the configured Telegram bot.
    The bot calls /telegram-connect/verify to link the Telegram user.
    """
    r = await _get_redis()
    code = secrets.token_hex(3).upper()           # e.g. "A3F7B2"
    await r.setex(f"tg_connect:{code}", 600, str(current_user.id))  # 10 min TTL
    bot_name = settings.telegram_bot_name or ""
    return {
        "code":     code,
        "deeplink": f"https://t.me/{bot_name}?start=connect_{code}",
        "expires_in": 600,
    }


@router.get("/telegram-connect/status")
async def telegram_connect_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll this to check if the user has connected Telegram."""
    # Refresh from DB
    await db.refresh(current_user)
    return {"connected": current_user.telegram_user_id is not None}


@router.post("/telegram-connect/verify")
async def telegram_connect_verify(
    code: str,
    telegram_user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Called by the Telegram bot when user sends /start connect_<CODE>.
    Links the Telegram user_id to the LNO user account.
    This endpoint is internal — protected by HERMES_SERVICE_TOKEN in a real deploy.
    """
    r = await _get_redis()
    user_id = await r.get(f"tg_connect:{code}")
    if not user_id:
        raise HTTPException(404, "Code expired or invalid")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    user.telegram_user_id = telegram_user_id
    await db.commit()
    await r.delete(f"tg_connect:{code}")
    return {"ok": True, "user_id": str(user.id), "name": user.name}


@router.post("/telegram-connect/widget")
async def telegram_connect_widget(
    body: TelegramWidgetData,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify Telegram Login Widget auth data and link the Telegram account.
    Called from the onboarding UI after the user authenticates via the widget.
    """
    if int(time()) - body.auth_date > 3600:
        raise HTTPException(status_code=400, detail="Auth data expired")

    # Build the check string: sorted key=value pairs (excluding hash), joined by newline
    data = {k: v for k, v in body.model_dump(exclude={"hash"}).items() if v is not None}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    # Verify HMAC-SHA256 signature using SHA256(bot_token) as secret key
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, body.hash):
        raise HTTPException(status_code=400, detail="Invalid Telegram auth signature")

    current_user.telegram_user_id = str(body.id)
    if not current_user.telegram_username and body.username:
        current_user.telegram_username = body.username
    await db.commit()
    return {"ok": True}
