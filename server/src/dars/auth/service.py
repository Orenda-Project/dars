import logging

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.clients.service import (
    create_client as create_db_client,
    get_client_by_email,
    rotate_api_key,
)

logger = logging.getLogger(__name__)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


async def signup(
    db: AsyncSession, email: str, password: str, name: str
) -> tuple[Client, str]:
    existing = await get_client_by_email(db, email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    client, raw_key = await create_db_client(db, name)
    client.email = email
    client.hashed_password = _hash_password(password)
    await db.commit()
    await db.refresh(client)

    logger.info("Signup: client_id=%s email=%s", client.id, email)
    return client, raw_key


async def login(db: AsyncSession, email: str, password: str) -> tuple[Client, str]:
    client = await get_client_by_email(db, email)

    if client is None or not client.hashed_password or not _verify_password(password, client.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client account is deactivated. Contact support.",
        )

    new_raw_key = await rotate_api_key(db, client)
    logger.info("Login: client_id=%s email=%s", client.id, email)
    return client, new_raw_key
