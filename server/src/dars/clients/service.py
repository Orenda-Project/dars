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


async def update_client(
    db: AsyncSession,
    client: Client,
    webhook_url: str | None,
) -> Client:
    client.webhook_url = webhook_url
    await db.commit()
    await db.refresh(client)
    return client


async def get_client_by_email(db: AsyncSession, email: str) -> Client | None:
    result = await db.execute(select(Client).where(Client.email == email))
    return result.scalar_one_or_none()


async def get_client_by_supabase_user_id(
    db: AsyncSession, supabase_user_id: str
) -> Client | None:
    result = await db.execute(
        select(Client).where(Client.supabase_user_id == supabase_user_id)
    )
    return result.scalar_one_or_none()


async def rotate_api_key(db: AsyncSession, client: Client) -> str:
    """Generate a new API key for an existing client. Returns the new raw key (shown once)."""
    raw_key = _generate_api_key()
    client.api_key_hash = _hash_key(raw_key)
    await db.commit()
    await db.refresh(client)
    return raw_key


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
