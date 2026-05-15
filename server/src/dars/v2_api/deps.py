"""
v2 API auth dependency.

Resolves an X-API-Key header against organizations.api_key_hash.
"""
import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from fastapi import Depends, Header, HTTPException, status

from dars.config import settings

log = logging.getLogger("v2_api.deps")


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


# A simple per-process pool. Created lazily on first request.
_POOL: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL is None:
        url = _asyncpg_url(settings.database_url)
        _POOL = await asyncpg.create_pool(url, min_size=1, max_size=10)
    return _POOL


async def get_db_conn() -> asyncpg.Connection:
    """
    FastAPI dependency that yields an asyncpg connection from the pool.
    Used by every v2 route.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn


@dataclass(frozen=True)
class OrgContext:
    """Resolved org details for the current request."""
    id: UUID
    name: str
    curriculum_id: UUID
    default_teacher_id: UUID | None


async def get_current_org(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> OrgContext:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    api_key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
    row = await conn.fetchrow(
        """
        SELECT id, name, curriculum_id, default_teacher_id
        FROM organizations
        WHERE api_key_hash = $1
        """,
        api_key_hash,
    )
    if row is None:
        log.info("get_current_org: invalid API key (prefix=%s)", x_api_key[:8])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    return OrgContext(
        id=row["id"],
        name=row["name"],
        curriculum_id=row["curriculum_id"],
        default_teacher_id=row["default_teacher_id"],
    )
