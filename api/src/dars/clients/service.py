import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_api_key() -> str:
    return f"dars_{secrets.token_urlsafe(32)}"


async def create_client(db: AsyncSession, name: str) -> tuple[Client, str]:
    """Create a new client. Returns (client, raw_api_key). Raw key shown once — not stored."""
    raw_key = _generate_api_key()
    client = Client(
        name=name,
        api_key_hash=_hash_key(raw_key),
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client, raw_key


async def get_client_by_api_key(db: AsyncSession, raw_key: str) -> Client | None:
    """Look up active client by raw API key. Returns None if not found or inactive."""
    key_hash = _hash_key(raw_key)
    result = await db.execute(
        select(Client).where(
            Client.api_key_hash == key_hash,
            Client.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
