import logging

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
) -> tuple[Client, str]:
    """
    Register a new client via Supabase Auth, then create a DB Client row.
    Returns (client, raw_api_key). The raw key is shown once and never stored.
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

    client, raw_key = await create_db_client(db, name)
    client.email = email
    client.supabase_user_id = supabase_user_id
    await db.commit()
    await db.refresh(client)
    logger.info("Signup: stored supabase_user_id=%s on client=%s", client.supabase_user_id, client.id)

    return client, raw_key


async def login(db: AsyncSession, email: str, password: str) -> tuple[Client, str]:
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
    return client, new_raw_key
