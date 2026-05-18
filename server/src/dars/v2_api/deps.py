"""
v2 API auth dependencies.

- get_current_org: resolves X-API-Key against organizations.api_key_hash (per-org).
- require_admin:   guards admin-only endpoints with X-Admin-Token vs settings.admin_secret
                   (env var DARS_ADMIN_TOKEN → admin_secret); uses hmac.compare_digest
                   per CLAUDE.md Critical Rule #5.
"""
import hashlib
import hmac
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
    x_admin_session: str | None = Header(default=None, alias="X-Admin-Session"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> OrgContext:
    """
    Accept either credential and resolve to the org's OrgContext:
      - X-API-Key (per-org runtime key — teacher app)
      - X-Admin-Session (admin session UUID — dashboard)

    The dashboard never displays the raw API key after signup, so admin
    actions that need an OrgContext (curriculum/book/breakdown reads,
    today/calendar etc.) must work via the admin session too.
    """
    if x_api_key:
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
            id=row["id"], name=row["name"],
            curriculum_id=row["curriculum_id"],
            default_teacher_id=row["default_teacher_id"],
        )

    if x_admin_session:
        try:
            session_id = UUID(x_admin_session)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed admin session",
            )
        from datetime import datetime, timezone
        row = await conn.fetchrow(
            """
            SELECT o.id, o.name, o.curriculum_id, o.default_teacher_id,
                   s.expires_at, s.revoked_at
            FROM admin_sessions s
            JOIN org_admins oa ON oa.id = s.org_admin_id
            JOIN organizations o ON o.id = oa.org_id
            WHERE s.id = $1
            """,
            session_id,
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        if row["revoked_at"] is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
        return OrgContext(
            id=row["id"], name=row["name"],
            curriculum_id=row["curriculum_id"],
            default_teacher_id=row["default_teacher_id"],
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing X-API-Key or X-Admin-Session",
    )


# ---------------------------------------------------------------------------
# Operator auth (D-66): for cross-org operator actions (seed/setup scripts).
# Dashboard + per-org admin endpoints use get_current_org instead (which
# accepts X-API-Key OR X-Admin-Session). require_admin is reserved for
# the legacy shared-secret path; no v2 routers currently use it.
# Comparison uses hmac.compare_digest per Critical Rule #5.
# ---------------------------------------------------------------------------


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = settings.admin_secret
    if not expected or expected == "dev-secret":
        log.warning("require_admin: admin_secret is unset or default; denying")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin auth is not configured on this server",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token required",
        )


