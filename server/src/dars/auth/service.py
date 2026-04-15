import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from supabase import Client as SupabaseClient
from supabase import create_client

from dars.clients.models import Client
from dars.clients.service import (
    create_client as create_db_client,
    get_client_by_email,
    get_client_by_supabase_user_id,
    rotate_api_key,
)
from dars.config import settings
from dars.teachers.schemas import TeacherRegisterRequest
from dars.teachers.service import register_teacher

logger = logging.getLogger(__name__)

_supabase: SupabaseClient | None = None


def get_supabase() -> SupabaseClient:
    global _supabase
    if _supabase is None:
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise RuntimeError(
                "supabase_url and supabase_anon_key must be set in .env to use auth endpoints"
            )
        _supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _supabase


async def signup(
    db: AsyncSession, email: str, password: str, name: str
) -> tuple[Client, str, uuid.UUID]:
    """
    Register a new client via Supabase Auth, then create a DB Client row.
    Returns (client, raw_api_key, teacher_id). The raw key is shown once and never stored.

    Uses a deferred FK transaction: client is flushed with default_teacher_id=None,
    teacher is flushed next, then client.default_teacher_id is set and the transaction
    is committed. The DEFERRABLE INITIALLY DEFERRED FK constraint passes at commit time.
    """
    sb = get_supabase()

    try:
        response = sb.auth.sign_up({"email": email, "password": password})
    except Exception as exc:
        logger.warning("Supabase sign_up error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Auth provider error during signup. Try again later.",
        ) from exc

    # Check for duplicate email in our DB regardless of what Supabase returned.
    # When email confirmation is disabled Supabase returns the existing user instead
    # of user=None, so we can't rely on that check alone.
    existing = await get_client_by_email(db, email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    if response.user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    supabase_user_id = str(response.user.id)
    logger.info("Signup: supabase_user_id=%s email=%s", supabase_user_id, email)

    # create_db_client commits the client row (default_teacher_id is nullable, so this is safe)
    client, raw_key = await create_db_client(db, name)
    client.email = email
    client.supabase_user_id = supabase_user_id

    # register_teacher now only flushes (not commits)
    teacher = await register_teacher(
        db,
        client_id=client.id,
        request=TeacherRegisterRequest(name=name, email=email),
    )
    logger.info("Signup: created teacher=%s for client=%s", teacher.id, client.id)

    # Wire the FK and commit everything in one shot
    client.default_teacher_id = teacher.id
    await db.commit()
    await db.refresh(client)
    await db.refresh(teacher)

    return client, raw_key, teacher.id


async def login(db: AsyncSession, email: str, password: str) -> tuple[Client, str, uuid.UUID]:
    """
    Authenticate via Supabase Auth, rotate the client's API key, and return the new raw key.

    Note: Because API keys are stored as one-way hashes, we cannot retrieve the original key.
    Each login rotates the key. Clients must update their stored key after every login call.
    """
    sb = get_supabase()

    try:
        response = sb.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        logger.warning("Supabase sign_in error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc

    if response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    supabase_user_id = str(response.user.id)
    logger.info("Login: supabase_user_id=%s email=%s", supabase_user_id, response.user.email)
    client = await get_client_by_supabase_user_id(db, supabase_user_id)
    logger.info("Login: client lookup result=%s", client)

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No client account found for this user. Contact support.",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client account is deactivated. Contact support.",
        )

    new_raw_key = await rotate_api_key(db, client)

    return client, new_raw_key, client.default_teacher_id
