import hashlib
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client

logger = logging.getLogger(__name__)


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_api_key() -> str:
    return f"dars_{secrets.token_urlsafe(32)}"


async def create_client(db: AsyncSession, name: str) -> tuple[Client, str]:
    """Create a new client. Returns (client, raw_api_key). Raw key shown once — not stored."""
    logger.info("create_client: name=%s", name)
    raw_key = _generate_api_key()
    client = Client(
        name=name,
        api_key_hash=_hash_key(raw_key),
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    logger.info("create_client: done client_id=%s", client.id)
    return client, raw_key


async def update_client(
    db: AsyncSession,
    client: Client,
    webhook_url: str | None,
) -> Client:
    logger.info("update_client: client_id=%s webhook_url=%s", client.id, webhook_url)
    client.webhook_url = webhook_url
    await db.commit()
    await db.refresh(client)
    logger.info("update_client: done client_id=%s", client.id)
    return client


async def get_client_by_email(db: AsyncSession, email: str) -> Client | None:
    result = await db.execute(select(Client).where(Client.email == email))
    return result.scalar_one_or_none()



async def rotate_api_key(db: AsyncSession, client: Client) -> str:
    """Generate a new API key for an existing client. Returns the new raw key (shown once)."""
    logger.info("rotate_api_key: client_id=%s", client.id)
    raw_key = _generate_api_key()
    client.api_key_hash = _hash_key(raw_key)
    await db.commit()
    await db.refresh(client)
    logger.info("rotate_api_key: done client_id=%s", client.id)
    return raw_key


async def get_client_by_api_key(db: AsyncSession, raw_key: str) -> Client | None:
    """Look up active client by raw API key. Returns None if not found or inactive."""
    key_prefix = raw_key[:12] if len(raw_key) >= 12 else raw_key[:4]
    logger.debug("get_client_by_api_key: key_prefix=%s...", key_prefix)
    key_hash = _hash_key(raw_key)
    result = await db.execute(
        select(Client).where(
            Client.api_key_hash == key_hash,
            Client.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
